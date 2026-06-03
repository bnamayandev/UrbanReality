"""
POST /trellis/generate-3d   — kick off a TRELLIS.2 job
GET  /trellis/status/{id}   — poll job state
GET  /trellis/download/{id} — download the finished GLB
"""
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from jobs import create_job, get_job, update_job, JobStatus
from trellis_runner import run_trellis

router = APIRouter(prefix="/trellis", tags=["trellis"])


class Generate3DRequest(BaseModel):
    image_b64: str               # raw base64, no data-URL prefix


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    glb_url: Optional[str] = None
    error: Optional[str] = None


# ── background task ────────────────────────────────────────────────────────────

def _trellis_task(job_id: str, image_b64: str) -> None:
    try:
        update_job(job_id, status=JobStatus.RUNNING)
        glb_path = run_trellis(image_b64, job_id)
        update_job(job_id, status=JobStatus.DONE, glb_path=glb_path)
    except Exception as exc:
        update_job(job_id, status=JobStatus.ERROR, error=str(exc))


# ── routes ─────────────────────────────────────────────────────────────────────

@router.post("/generate-3d")
def generate_3d(req: Generate3DRequest):
    b64 = req.image_b64
    if "," in b64:
        b64 = b64.split(",", 1)[1]

    job = create_job()
    threading.Thread(target=_trellis_task, args=(job.id, b64), daemon=True).start()
    return {"job_id": job.id, "status": "pending"}


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def get_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    glb_url = f"/trellis/download/{job_id}" if job.status == JobStatus.DONE else None
    return JobStatusResponse(
        job_id=job_id,
        status=job.status,
        glb_url=glb_url,
        error=job.error,
    )


@router.get("/download/{job_id}")
def download_glb(job_id: str):
    job = get_job(job_id)
    if not job or job.status != JobStatus.DONE:
        raise HTTPException(status_code=404, detail="GLB not ready")
    if not job.glb_path:
        raise HTTPException(status_code=404, detail="GLB file missing")

    return FileResponse(
        job.glb_path,
        media_type="model/gltf-binary",
        filename=f"building_{job_id[:8]}.glb",
        headers={"Access-Control-Allow-Origin": "*"},
    )
