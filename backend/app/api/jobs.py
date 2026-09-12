from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import Job, SessionLocal
from app.services.workflow_service import workflow_service

router = APIRouter(tags=["jobs"])


class CreateJobRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class JobResponse(BaseModel):
    job_id: UUID
    title: str
    description: str
    status: str
    stage: str
    error: str | None


def to_response(job: Job) -> JobResponse:
    return JobResponse(
        job_id=job.id,
        title=job.title,
        description=job.description,
        status=job.status,
        stage=job.stage,
        error=job.error,
    )


@router.post("/jobs", response_model=JobResponse)
def create_job(request: CreateJobRequest) -> JobResponse:
    job_id = uuid4()
    with SessionLocal() as db:
        job = Job(
            id=job_id,
            title=request.title,
            description=request.description,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    return to_response(workflow_service.create_and_run(job_id))


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID) -> JobResponse:
    job = workflow_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return to_response(job)


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: UUID) -> JobResponse:
    job = workflow_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "FAILED":
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")

    return to_response(workflow_service.retry(job_id))
