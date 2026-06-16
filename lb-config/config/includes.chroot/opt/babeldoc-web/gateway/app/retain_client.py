"""Route scanned PDFs to the RetainPDF stack.

babeldoc re-typesets from text geometry, so scanned PDFs come out garbled.
RetainPDF is OCR-first (Paddle/MinerU) + Typst rendering, which handles scans
cleanly. This module decides whether a PDF is scanned and, if so, drives the
RetainPDF HTTP API (upload -> book job -> poll -> download) on the job's behalf.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import httpx

from .config import settings

# RetainPDF stage name -> BabelDOCWeb coarse phase the UI renders.
_STAGE_GROUPS = {
    "queued": "analyze",
    "ocr_upload": "analyze",
    "ocr": "analyze",
    "ocr_processing": "analyze",
    "normalize": "analyze",
    "normalizing": "analyze",
    "translating": "translate",
    "translate": "translate",
    "rendering": "render",
    "render": "render",
    "finished": "render",
}


def scanned_fraction(pdf_path: Path) -> float:
    """Fraction of pages that carry no extractable text layer."""
    import fitz  # pymupdf

    doc = fitz.open(str(pdf_path))
    try:
        total = len(doc)
        if total == 0:
            return 0.0
        blank = sum(1 for page in doc if not page.get_text("text").strip())
        return blank / total
    finally:
        doc.close()


def should_route_to_retain(pdf_path: Path) -> bool:
    """True if RetainPDF is configured and the PDF looks mostly scanned."""
    if not (settings.retain_enabled and settings.retain_api_key):
        return False
    try:
        return scanned_fraction(pdf_path) >= settings.scanned_route_threshold
    except Exception:  # noqa: BLE001 — never block the babeldoc fallback
        return False


def _headers() -> dict:
    return {"X-API-Key": settings.retain_api_key}


def _check(resp: httpx.Response) -> dict:
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 0:
        raise RuntimeError(body.get("message") or "RetainPDF returned an error")
    return body.get("data") or {}


def translate_via_retain(
    input_pdf: Path,
    target_language: str,
    model: str,
    progress_cb: Callable[[str, float], None],
) -> Path:
    """Translate *input_pdf* through RetainPDF and return the result PDF path.

    *target_language* is the ISO code (e.g. ``en``/``vi``); it is passed to
    RetainPDF via the ``@@RETAIN_TARGET:<code>`` custom-rules directive. The
    source language is auto-detected by the model. Raises on failure.
    """
    base = settings.retain_base_url.rstrip("/")

    ocr: dict = {"provider": settings.retain_ocr_provider}
    if settings.retain_ocr_provider == "paddle":
        ocr["paddle_token"] = settings.retain_paddle_token
    else:
        ocr["mineru_token"] = settings.retain_mineru_token

    with httpx.Client(timeout=180) as client:
        # 1. upload the source PDF
        with open(input_pdf, "rb") as fh:
            up = _check(
                client.post(
                    f"{base}/api/v1/uploads",
                    headers=_headers(),
                    files={"file": (input_pdf.name, fh, "application/pdf")},
                    data={"developer_mode": "false"},
                )
            )
        progress_cb("analyze", 5)

        # 2. create the full (book) job
        payload = {
            "workflow": "book",
            "source": {"upload_id": up["upload_id"]},
            "ocr": ocr,
            "translation": {
                "base_url": settings.translation_base_url,
                "api_key": settings.translation_api_key,
                "model": model,
                "mode": "precise",
                "math_mode": "direct_typst",
                "workers": max(settings.qps, 1),
                "batch_size": 1,
                "custom_rules_text": f"@@RETAIN_TARGET:{target_language}",
            },
            "render": {"render_mode": "auto"},
        }
        job = _check(client.post(f"{base}/api/v1/jobs", headers=_headers(), json=payload))
        job_id = job["job_id"]

        # 3. poll until terminal
        status = "queued"
        detail = {}
        while True:
            detail = _check(client.get(f"{base}/api/v1/jobs/{job_id}", headers=_headers()))
            status = detail.get("status")
            stage = detail.get("stage") or ""
            pct = (detail.get("progress") or {}).get("percent") or 0
            progress_cb(_STAGE_GROUPS.get(stage, "translate"), float(pct))
            if status in ("succeeded", "failed", "canceled"):
                break
            time.sleep(3)

        if status != "succeeded":
            raise RuntimeError(detail.get("error") or f"RetainPDF job {status}")

        # 4. download the rendered PDF
        out = input_pdf.with_suffix(".retain.pdf")
        with client.stream(
            "GET", f"{base}/api/v1/jobs/{job_id}/pdf", headers=_headers()
        ) as r:
            r.raise_for_status()
            with open(out, "wb") as fh:
                for chunk in r.iter_bytes():
                    fh.write(chunk)
        return out
