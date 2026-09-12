from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.graph.factory_graph import run_workflow

router = APIRouter(tags=["jobs"])


class CreateJobRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class CreateJobResponse(BaseModel):
    job_id: UUID
    status: str
    stage: str


@router.post("/jobs", response_model=CreateJobResponse)
def create_job(request: CreateJobRequest) -> CreateJobResponse:
    job_id = uuid4()
    result = run_workflow(job_id, request.title, request.description)

    return CreateJobResponse(
        job_id=job_id,
        status=result["status"],
        stage=result["stage"],
    )
