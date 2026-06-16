"""Drive BabelDOC's Python API and emit newline-delimited JSON progress.

Spawned as a subprocess by the gateway. Reads no stdin; writes one JSON
object per line to stdout:

    {"type": "progress", "stage": "...", "progress": 0-100}
    {"type": "finish", "mono": "<path>", "dual": "<path>"}
    {"type": "error", "error": "..."}
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import sys
from pathlib import Path


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# ISO-639 (babeldoc) -> Tesseract language code. Keep in sync with the
# language packs installed in the gateway Dockerfile.
LANG_MAP = {
    "en": "eng", "vi": "vie", "zh": "chi_sim",
    "ja": "jpn", "ko": "kor", "fr": "fra",
    "de": "deu", "es": "spa", "pt": "por",
}


def _page_has_text(page) -> bool:
    """True if the page already carries an extractable text layer."""
    return bool(page.get_text("text").strip())


# DeepSeek-OCR grounding emits blocks like ``text[[x1, y1, x2, y2]]\n<content>``
# with coordinates normalized to 0-1000 relative to the page dimensions.
_GROUNDING_RE = re.compile(
    r"[A-Za-z_|<>/]*\[\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]\]"
    r"\s*\n?(.*?)(?=[A-Za-z_|<>/]*\[\[|\Z)",
    re.DOTALL,
)
_MD_NOISE_RE = re.compile(r"^[#>*`\-\s]+|[*`]+$")


def _ocr_page_vision(page, base_url, api_key, model, max_px=1024):
    """OCR a single page through a vision/OCR model on the LLM gateway.

    Uses DeepSeek-OCR-style grounding so we get text *and* bounding boxes,
    which lets us place an invisible text layer in the right spot for babeldoc
    to typeset translations over. Returns a list of
    ``(text, x0, y0, x1, y1)`` spans in PDF points, or None on failure/empty.

    The page is rendered with its long side capped at *max_px* — the vision
    token count scales with image area, and a full-resolution A4 page would
    overflow the model's context window.
    """
    import fitz  # pymupdf
    import httpx

    zoom = max_px / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    b64 = base64.b64encode(pix.tobytes("png")).decode()
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text",
             "text": "<image>\n<|grounding|>Convert the document to markdown."},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64," + b64}},
        ]}],
        "max_tokens": 4096,
        "temperature": 0,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    try:
        resp = httpx.post(
            url, json=body,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=240,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001 — any failure -> let caller fall back
        return None

    w, h = page.rect.width, page.rect.height
    spans = []
    for m in _GROUNDING_RE.finditer(content):
        x1, y1, x2, y2 = (int(m.group(i)) for i in range(1, 5))
        block = m.group(5).strip()
        if not block:
            continue
        px0, px1 = x1 / 1000.0 * w, x2 / 1000.0 * w
        py0, py1 = y1 / 1000.0 * h, y2 / 1000.0 * h
        spans.append((block, px0, py0, px1, py1))
    return spans or None


def _place_spans(new_page, spans, fitz) -> None:
    """Lay invisible (render_mode=3) text into *new_page* from OCR spans.

    Multi-line blocks are distributed vertically across their bounding box so
    babeldoc's paragraph finder sees a sensible layout.
    """
    for block, x0, y0, x1, y1 in spans:
        lines = [_MD_NOISE_RE.sub("", ln).strip() for ln in block.split("\n")]
        lines = [ln for ln in lines if ln]
        if not lines:
            continue
        line_h = max((y1 - y0) / len(lines), 1.0)
        size = max(line_h * 0.8, 6)
        for j, ln in enumerate(lines):
            baseline = y0 + line_h * (j + 1)
            new_page.insert_text(
                fitz.Point(x0, baseline),
                ln,
                fontsize=size,
                render_mode=3,  # invisible — text only, not painted
                color=(0, 0, 0),
            )


def _ocr_page_tesseract(page, new_page, tess_lang, fitz) -> None:
    """Fallback: OCR a page with Tesseract via PyMuPDF and overlay text."""
    tp = page.get_textpage_ocr(language=tess_lang, dpi=300, full=True)
    for blk in tp.extractDICT().get("blocks", []):
        if blk.get("type") != 0:
            continue
        for line in blk.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                x0, y0, x1, y1 = span["bbox"]
                new_page.insert_text(
                    fitz.Point(x0, y1),
                    text,
                    fontsize=max(span.get("size", 10), 6),
                    render_mode=3,
                    color=(0, 0, 0),
                )


def ensure_text_layer(
    input_path: str,
    lang_in: str = "en",
    ocr_model: str = "",
    base_url: str = "",
    api_key: str = "",
) -> str:
    """Guarantee every page has an extractable text layer.

    babeldoc only auto-OCRs when >=80% of pages are scanned, and it silently
    skips translating individual scanned pages in mostly-text PDFs. To close
    that gap we OCR *only* the pages that lack text and overlay an invisible
    text layer, leaving text pages untouched.

    OCR is done with a vision/OCR model on the gateway (high quality, with
    layout grounding) when *ocr_model* is set, falling back to Tesseract.

    Returns the original path when no page needs OCR (fast path), otherwise the
    path to a new PDF that babeldoc can fully parse.
    """
    import fitz  # pymupdf

    src = fitz.open(input_path)
    scanned = [i for i, page in enumerate(src) if not _page_has_text(page)]

    if not scanned:
        src.close()
        return input_path  # every page already has text — nothing to do

    tess_lang = LANG_MAP.get(lang_in, "eng")
    out = fitz.open()
    out_path = str(Path(input_path).with_suffix(".ocr.pdf"))
    done = 0

    for i, page in enumerate(src):
        if i not in scanned:
            # Copy text pages verbatim to preserve original vectors/fonts.
            out.insert_pdf(src, from_page=i, to_page=i)
            continue

        done += 1
        emit({
            "type": "progress",
            "stage": "analyze",
            "progress": round(done / len(scanned) * 25, 2),
        })

        # New page same size as source, with the original visual content on it.
        new_page = out.new_page(width=page.rect.width, height=page.rect.height)
        new_page.show_pdf_page(page.rect, src, i)

        spans = None
        if ocr_model and base_url:
            spans = _ocr_page_vision(page, base_url, api_key, ocr_model)
        if spans is not None:
            _place_spans(new_page, spans, fitz)
        else:
            _ocr_page_tesseract(page, new_page, tess_lang, fitz)

    out.save(out_path)
    out.close()
    src.close()
    return out_path


async def _translate(input_path: str, args: argparse.Namespace) -> int:
    """Run babeldoc translation on *input_path* and stream progress/finish."""
    import babeldoc.format.pdf.high_level as high_level
    from babeldoc.docvision.doclayout import DocLayoutModel
    from babeldoc.format.pdf.translation_config import TranslationConfig
    from babeldoc.format.pdf.translation_config import WatermarkOutputMode
    from babeldoc.translator.translator import OpenAITranslator
    from babeldoc.translator.translator import set_translate_rate_limiter

    api_key = args.api_key or "placeholder"

    translator = OpenAITranslator(
        lang_in=args.lang_in,
        lang_out=args.lang_out,
        model=args.model,
        base_url=args.base_url,
        api_key=api_key,
        ignore_cache=args.ignore_cache,
    )
    set_translate_rate_limiter(args.qps)
    doc_layout_model = DocLayoutModel.load_onnx()

    config = TranslationConfig(
        input_file=input_path,
        font=None,
        translator=translator,
        term_extraction_translator=translator,
        lang_in=args.lang_in,
        lang_out=args.lang_out,
        output_dir=args.output,
        doc_layout_model=doc_layout_model,
        qps=args.qps,
        custom_system_prompt=args.custom_system_prompt or None,
        watermark_output_mode=WatermarkOutputMode.NoWatermark,
        split_short_lines=args.split_short_lines,
        min_text_length=args.min_text_length,
        auto_enable_ocr_workaround=True,
    )

    nop = lambda _x: None  # noqa: E731
    getattr(doc_layout_model, "init_font_mapper", nop)(config)

    async for event in high_level.async_translate(config):
        etype = event.get("type")
        if etype in ("progress_start", "progress_update", "progress_end"):
            emit({
                "type": "progress",
                "stage": event.get("stage", ""),
                "progress": round(float(event.get("overall_progress", 0.0)), 2),
            })
        elif etype == "error":
            raise RuntimeError(str(event.get("error", "unknown error")))
        elif etype == "finish":
            result = event["translate_result"]
            mono = getattr(result, "no_watermark_mono_pdf_path", None) or getattr(
                result, "mono_pdf_path", None
            )
            dual = getattr(result, "no_watermark_dual_pdf_path", None) or getattr(
                result, "dual_pdf_path", None
            )
            emit({
                "type": "finish",
                "mono": str(mono) if mono else None,
                "dual": str(dual) if dual else None,
            })
            return 0
    raise RuntimeError("translation ended without a finish event")


async def run(args: argparse.Namespace) -> int:
    # Proactively OCR any scanned pages (incl. partially-scanned PDFs) so
    # babeldoc never silently skips a page that lacks a text layer.
    try:
        prepared = ensure_text_layer(
            args.input,
            lang_in=args.lang_in,
            ocr_model=args.ocr_model,
            base_url=args.base_url,
            api_key=args.api_key,
        )
    except Exception as ocr_exc:  # noqa: BLE001
        emit({"type": "error", "error": f"OCR preprocessing failed: {ocr_exc}"})
        return 1

    try:
        return await _translate(prepared, args)
    except RuntimeError as exc:
        emit({"type": "error", "error": str(exc)})
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lang-in", default="en")
    parser.add_argument("--lang-out", default="vi")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--qps", type=int, default=4)
    parser.add_argument("--custom-system-prompt", default="")
    parser.add_argument("--split-short-lines", action="store_true", default=False)
    parser.add_argument("--ignore-cache", action="store_true", default=False)
    parser.add_argument("--min-text-length", type=int, default=5)
    parser.add_argument("--ocr-model", default="")
    args = parser.parse_args()

    import babeldoc.format.pdf.high_level as high_level

    high_level.init()
    try:
        return asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001
        emit({"type": "error", "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
