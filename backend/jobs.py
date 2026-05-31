import uuid
from dataclasses import dataclass, field
from typing import Optional

class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    ERROR   = "error"

@dataclass
class Job:
    id: str
    status: str = JobStatus.PENDING
    glb_path: Optional[str] = None
    error: Optional[str] = None

_jobs: dict[str, Job] = {}


def create_job() -> Job:
    job = Job(id=str(uuid.uuid4()))
    _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs) -> None:
    job = _jobs.get(job_id)
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)
