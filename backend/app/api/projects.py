from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db import Project, SessionLocal

router = APIRouter(tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1)
    repository_url: str = Field(min_length=1)
    base_branch: str = Field(default="main", min_length=1)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    repository_url: str
    base_branch: str


def to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        repository_url=project.repository_url,
        base_branch=project.base_branch,
    )


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects() -> list[ProjectResponse]:
    with SessionLocal() as db:
        projects = db.scalars(select(Project).order_by(Project.updated_at.desc())).all()
        return [to_response(project) for project in projects]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(request: CreateProjectRequest) -> ProjectResponse:
    with SessionLocal() as db:
        project = Project(
            name=request.name.strip(),
            repository_url=request.repository_url.strip(),
            base_branch=request.base_branch.strip(),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return to_response(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: UUID) -> ProjectResponse:
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return to_response(project)
