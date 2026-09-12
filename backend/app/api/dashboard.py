from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.productivity_service import productivity_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class StageMetricResponse(BaseModel):
    stage: str
    attempts: int
    completed_attempts: int
    failed_attempts: int
    total_duration_ms: float
    last_duration_ms: float | None


class JobProductivityResponse(BaseModel):
    job_id: UUID
    title: str
    status: str
    stage: str
    created_at: datetime
    completed_at: datetime | None
    cycle_time_ms: float
    queue_wait_ms: float | None
    execution_time_ms: float
    retry_overhead_ms: float
    retry_count: int
    failed_stage_count: int
    stage_metrics: list[StageMetricResponse]


class DashboardSummaryResponse(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    active_jobs: int
    success_rate_percent: float | None
    average_cycle_time_ms: float | None
    average_queue_wait_ms: float | None
    total_execution_time_ms: float
    total_retry_overhead_ms: float
    total_retries: int
    total_failed_stages: int
    jobs: list[JobProductivityResponse]


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary() -> DashboardSummaryResponse:
    return DashboardSummaryResponse(**productivity_service.dashboard_summary())


@router.get("/jobs/{job_id}", response_model=JobProductivityResponse)
def job_productivity(job_id: UUID) -> JobProductivityResponse:
    try:
        metrics = productivity_service.job_metrics(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    return JobProductivityResponse(**metrics)
