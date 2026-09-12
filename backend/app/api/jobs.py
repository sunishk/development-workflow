from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.db import Job, SessionLocal
from app.services.event_service import event_service
from app.services.workflow_service import workflow_service

router = APIRouter(tags=["jobs"])


class CreateJobRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    repository_url: str | None = None
    base_branch: str = "main"


class JobResponse(BaseModel):
    job_id: UUID
    title: str
    description: str
    status: str
    stage: str
    error: str | None
    repository_url: str | None
    base_branch: str | None
    workspace_path: str | None
    workspace_branch: str | None


class WorkflowEventResponse(BaseModel):
    id: int
    event_type: str
    stage: str | None
    message: str | None
    worker_id: str | None
    duration_ms: float | None
    created_at: datetime


class StageMetricResponse(BaseModel):
    stage: str
    attempts: int
    completed_attempts: int
    failed_attempts: int
    total_duration_ms: float
    last_duration_ms: float | None


def to_response(job: Job) -> JobResponse:
    return JobResponse(
        job_id=job.id,
        title=job.title,
        description=job.description,
        status=job.status,
        stage=job.stage,
        error=job.error,
        repository_url=job.repository_url,
        base_branch=job.base_branch,
        workspace_path=job.workspace_path,
        workspace_branch=job.workspace_branch,
    )


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(request: CreateJobRequest) -> JobResponse:
    job_id = uuid4()
    with SessionLocal() as db:
        job = Job(
            id=job_id,
            title=request.title,
            description=request.description,
            status="QUEUED",
            stage="CREATED",
            repository_url=request.repository_url,
            base_branch=request.base_branch if request.repository_url else None,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    event_service.record(job_id, "JOB_CREATED", stage="CREATED")
    event_service.record(job_id, "JOB_QUEUED", stage="CREATED")
    return to_response(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID) -> JobResponse:
    job = workflow_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return to_response(job)


@router.get("/jobs/{job_id}/events", response_model=list[WorkflowEventResponse])
def get_job_events(job_id: UUID) -> list[WorkflowEventResponse]:
    job = workflow_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return [
        WorkflowEventResponse(
            id=event.id,
            event_type=event.event_type,
            stage=event.stage,
            message=event.message,
            worker_id=event.worker_id,
            duration_ms=event.duration_ms,
            created_at=event.created_at,
        )
        for event in event_service.list_for_job(job_id)
    ]


@router.get("/jobs/{job_id}/metrics", response_model=list[StageMetricResponse])
def get_job_metrics(job_id: UUID) -> list[StageMetricResponse]:
    job = workflow_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return [StageMetricResponse(**metric) for metric in event_service.stage_metrics(job_id)]


@router.post("/jobs/{job_id}/retry", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: UUID) -> JobResponse:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status != "FAILED":
            raise HTTPException(status_code=409, detail="Only failed jobs can be retried")

        job.status = "QUEUED"
        job.error = None
        db.commit()
        db.refresh(job)

    event_service.record(job_id, "RETRY_QUEUED", stage=job.stage)
    return to_response(job)
