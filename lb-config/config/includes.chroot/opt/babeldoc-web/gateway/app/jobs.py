from __future__ import annotations

import json
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .config import settings

# Map babeldoc stage names to the 4 coarse phases the UI renders.
STAGE_GROUPS = {
    "ParseIL": "analyze",
    "Parse PDF": "analyze",
    "DetectScannedFile": "analyze",
    "LayoutParser": "analyze",
    "TableParser": "analyze",
    "ParagraphFinder": "analyze",
    "StylesAndFormulas": "analyze",
    "Automatic Term Extraction": "translate",
    "ILTranslator": "translate",
    "Typesetting": "render",
    "FontMapper": "render",
    "Add Watermark": "render",
    "Save PDF": "render",
}

RUNNER_PATH = str(Path(__file__).resolve().parent.parent / "runner.py")

_db_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    settings.ensure_dirs()
    with _db_lock, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                stage TEXT,
                progress REAL DEFAULT 0,
                source_file_name TEXT,
                target_language TEXT,
                model TEXT,
                error TEXT,
                created_at REAL,
                updated_at REAL,
                split_short_lines INTEGER DEFAULT 0,
                ignore_cache INTEGER DEFAULT 0
            )
            """
        )


def _row_to_job(row: sqlite3.Row) -> dict:
    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "stage": row["stage"],
        "progress": row["progress"],
        "source_file_name": row["source_file_name"],
        "target_language": row["target_language"],
        "model": row["model"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_job(
    source_file_name: str,
    target_language: str,
    model: str,
    split_short_lines: bool = False,
    ignore_cache: bool = False,
) -> dict:
    job_id = uuid.uuid4().hex
    now = time.time()
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, status, stage, progress, source_file_name,"
            " target_language, model, split_short_lines, ignore_cache, created_at, updated_at)"
            " VALUES (?, 'pending', NULL, 0, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, source_file_name, target_language, model,
             int(split_short_lines), int(ignore_cache), now, now),
        )
    return get_job(job_id)


def get_job(job_id: str) -> dict | None:
    with _db_lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    return _row_to_job(row) if row else None


def list_jobs(limit: int = 50) -> list[dict]:
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def _update(job_id: str, **fields) -> None:
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _db_lock, _connect() as conn:
        conn.execute(
            f"UPDATE jobs SET {cols} WHERE job_id = ?",
            (*fields.values(), job_id),
        )


def delete_job(job_id: str) -> bool:
    job = get_job(job_id)
    if not job:
        return False
    with _db_lock, _connect() as conn:
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
    out_dir = settings.jobs_dir / job_id
    if out_dir.exists():
        for f in out_dir.glob("*"):
            f.unlink()
        out_dir.rmdir()
    return True


def job_output_dir(job_id: str) -> Path:
    return settings.jobs_dir / job_id


def list_artifacts(job_id: str) -> list[str]:
    out_dir = job_output_dir(job_id)
    names = []
    if (out_dir / "dual.pdf").exists():
        names.append("dual")
    if (out_dir / "mono.pdf").exists():
        names.append("mono")
    if (out_dir / "source.pdf").exists():
        names.append("source")
    return names


def artifact_path(job_id: str, name: str) -> Path | None:
    candidate = job_output_dir(job_id) / f"{name}.pdf"
    return candidate if candidate.exists() else None


def start_job(
    job_id: str,
    input_pdf: Path,
    target_language: str,
    model: str,
    split_short_lines: bool = False,
    ignore_cache: bool = False,
) -> None:
    thread = threading.Thread(
        target=_run_job,
        args=(job_id, input_pdf, target_language, model, split_short_lines, ignore_cache),
        daemon=True,
    )
    thread.start()


def _run_job(
    job_id: str,
    input_pdf: Path,
    target_language: str,
    model: str,
    split_short_lines: bool = False,
    ignore_cache: bool = False,
) -> None:
    out_dir = job_output_dir(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Keep a copy of the source for side-by-side comparison.
    (out_dir / "source.pdf").write_bytes(input_pdf.read_bytes())

    # Scanned PDFs translate poorly through babeldoc; hand them to RetainPDF.
    from . import retain_client

    if retain_client.should_route_to_retain(input_pdf):
        _update(job_id, status="running", stage="analyze", progress=0)

        def _cb(group: str, pct: float) -> None:
            _update(job_id, status="running", stage=group, progress=round(pct, 2))

        try:
            result_pdf = retain_client.translate_via_retain(
                input_pdf, target_language, model, _cb
            )
        except Exception as exc:  # noqa: BLE001
            _update(job_id, status="failed", error=f"RetainPDF: {exc}".strip()[-2000:])
            return

        (out_dir / "mono.pdf").write_bytes(result_pdf.read_bytes())
        _update(job_id, status="done", stage="render", progress=100)
        return

    cmd = [
        *settings.babeldoc_run_cmd,
        RUNNER_PATH,
        "--input", str(input_pdf),
        "--output", str(out_dir),
        "--lang-in", settings.default_lang_in,
        "--lang-out", target_language,
        "--model", model,
        "--base-url", settings.translation_base_url,
        "--api-key", settings.translation_api_key,
        "--qps", str(settings.qps),
        "--custom-system-prompt", settings.custom_system_prompt,
        *(["--split-short-lines"] if split_short_lines else []),
        *(["--ignore-cache"] if ignore_cache else []),
        # When split_short_lines is active, short lines become tiny standalone paragraphs.
        # BabelDOC's default min_text_length=5 would silently skip them, causing missing
        # content. Lower the threshold to 1 so every paragraph gets translated.
        "--min-text-length", "1" if split_short_lines else "5",
        "--ocr-model", settings.ocr_model,
    ]

    _update(job_id, status="running", stage="analyze", progress=0)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as exc:  # noqa: BLE001
        _update(job_id, status="failed", error=f"failed to launch runner: {exc}")
        return

    mono_src = dual_src = None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        if etype == "progress":
            stage = event.get("stage", "")
            group = STAGE_GROUPS.get(stage, "analyze")
            _update(
                job_id,
                status="running",
                stage=group,
                progress=event.get("progress", 0),
            )
        elif etype == "finish":
            mono_src = event.get("mono")
            dual_src = event.get("dual")
        elif etype == "error":
            _update(job_id, status="failed", error=event.get("error", "unknown"))
            proc.wait()
            return

    proc.wait()
    if proc.returncode != 0 and not (mono_src or dual_src):
        stderr = proc.stderr.read() if proc.stderr else ""
        _update(
            job_id,
            status="failed",
            error=(stderr or "runner exited with non-zero status").strip()[-2000:],
        )
        return

    # Normalize output filenames so the API/UI use stable names.
    if mono_src and Path(mono_src).exists():
        (out_dir / "mono.pdf").write_bytes(Path(mono_src).read_bytes())
    if dual_src and Path(dual_src).exists():
        (out_dir / "dual.pdf").write_bytes(Path(dual_src).read_bytes())

    if not list_artifacts(job_id):
        _update(job_id, status="failed", error="no output produced")
        return

    _update(job_id, status="done", stage="render", progress=100)
