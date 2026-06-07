"""
POST /render3d/generate-3d   — kick off a Stable Fast 3D job
GET  /render3d/status/{id}   — poll job state
GET  /render3d/download/{id} — download the finished GLB
"""
import logging
import os
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from jobs import create_job, get_job, update_job, JobStatus
from gpu_coordinator import gpu_lock_sync, unload_llm
from sf3d_runner import run_sf3d
from hunyuan_runner import run_hunyuan

log = logging.getLogger("render3d")

# Which local image->3D backend to use. "hunyuan" = high-detail Hunyuan3D-2mini
# (~4GB peak, ~17x SF3D geometry, untextured for now); "sf3d" = the lighter,
# textured low-poly fallback. Default to hunyuan; fall back to sf3d if its venv
# isn't set up so the endpoint never hard-fails on a fresh checkout.
RENDERER_3D = os.getenv("RENDERER_3D", "hunyuan").strip().lower()
_RUNNERS = {"hunyuan": run_hunyuan, "sf3d": run_sf3d}

router = APIRouter(prefix="/render3d", tags=["render3d"])


def _select_runner():
    runner = _RUNNERS.get(RENDERER_3D)
    if runner is None:
        log.warning("Unknown RENDERER_3D=%r; falling back to sf3d", RENDERER_3D)
        return run_sf3d
    return runner


class Generate3DRequest(BaseModel):
    image_b64: str               # raw base64, no data-URL prefix


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    glb_url: Optional[str] = None
    error: Optional[str] = None


# ── background task ────────────────────────────────────────────────────────────

def _render_task(job_id: str, image_b64: str) -> None:
    try:
        update_job(job_id, status=JobStatus.RUNNING)
        runner = _select_runner()
        # One 8GB GPU: hold the GPU lock and evict the LLM so the renderer has room.
        with gpu_lock_sync():
            unload_llm()
            glb_path = runner(image_b64, job_id)
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
    threading.Thread(target=_render_task, args=(job.id, b64), daemon=True).start()
    return {"job_id": job.id, "status": "pending"}


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def get_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    glb_url = f"/render3d/download/{job_id}" if job.status == JobStatus.DONE else None
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
