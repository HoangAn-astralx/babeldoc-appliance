import uuid
from pathlib import Path

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import jobs
from ..auth import require_api_key
from ..config import settings

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


class CreateJobBody(BaseModel):
    upload_id: str
    target_language: str | None = None
    model: str | None = None
    split_short_lines: bool = False
    ignore_cache: bool = False


class RerunJobBody(BaseModel):
    ignore_cache: bool = True
    model: str | None = None


def _status_payload(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "stage": job["stage"],
        "progress": job["progress"],
        "source_file_name": job["source_file_name"],
        "target_language": job["target_language"],
        "model": job["model"],
        "error": job["error"],
    }


@router.post("/uploads")
async def create_upload(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    upload_id = uuid.uuid4().hex
    dest = settings.upload_dir / f"{upload_id}.pdf"
    dest.write_bytes(data)
    # remember original filename next to the upload
    (settings.upload_dir / f"{upload_id}.name").write_text(file.filename)
    return {"upload_id": upload_id, "file_name": file.filename}


@router.post("/jobs")
def create_job(body: CreateJobBody):
    upload_pdf = settings.upload_dir / f"{body.upload_id}.pdf"
    if not upload_pdf.exists():
        raise HTTPException(status_code=404, detail="upload_id not found")
    name_file = settings.upload_dir / f"{body.upload_id}.name"
    source_name = name_file.read_text() if name_file.exists() else "document.pdf"

    target_language = body.target_language or settings.default_lang_out
    model = body.model or settings.translation_model

    job = jobs.create_job(source_name, target_language, model, body.split_short_lines, body.ignore_cache)
    jobs.start_job(job["job_id"], upload_pdf, target_language, model, body.split_short_lines, body.ignore_cache)
    return _status_payload(job)


@router.get("/jobs")
def get_jobs(limit: int = 50):
    return {"jobs": [_status_payload(j) for j in jobs.list_jobs(limit)]}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return _status_payload(job)


@router.post("/jobs/{job_id}/rerun")
def rerun_job(job_id: str, body: RerunJobBody = RerunJobBody()):
    """Create a new job using the stored source PDF of an existing job."""
    orig = jobs.get_job(job_id)
    if not orig:
        raise HTTPException(status_code=404, detail="job not found")
    source_pdf = jobs.artifact_path(job_id, "source")
    if not source_pdf:
        raise HTTPException(status_code=409, detail="source artifact not available for rerun")
    model = body.model or orig["model"] or settings.translation_model
    target_language = orig["target_language"] or settings.default_lang_out
    split_short_lines = bool(orig.get("split_short_lines", False))
    new_job = jobs.create_job(
        orig["source_file_name"] or "document.pdf",
        target_language,
        model,
        split_short_lines,
        body.ignore_cache,
    )
    jobs.start_job(new_job["job_id"], source_pdf, target_language, model, split_short_lines, body.ignore_cache)
    return _status_payload(new_job)


@router.delete("/jobs/{job_id}")
def remove_job(job_id: str):
    if not jobs.delete_job(job_id):
        raise HTTPException(status_code=404, detail="job not found")
    return {"deleted": True}


@router.get("/jobs/{job_id}/artifacts")
def get_artifacts(job_id: str):
    if not jobs.get_job(job_id):
        raise HTTPException(status_code=404, detail="job not found")
    return {"artifacts": jobs.list_artifacts(job_id)}


@router.get("/jobs/{job_id}/artifacts/{name}")
def get_artifact(job_id: str, name: str):
    if name not in ("dual", "mono", "source"):
        raise HTTPException(status_code=400, detail="invalid artifact name")
    path: Path | None = jobs.artifact_path(job_id, name)
    if not path:
        raise HTTPException(status_code=404, detail="artifact not found")
    job = jobs.get_job(job_id)
    base = (job["source_file_name"] or "document").rsplit(".pdf", 1)[0]
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{base}.{name}.pdf",
    )
