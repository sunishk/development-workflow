from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.filesystem_service import filesystem_service
from app.services.git_service import git_service
from app.services.repository_service import repository_service
from app.services.workflow_service import workflow_service

router = APIRouter(tags=["repositories"])


class WorkspaceResponse(BaseModel):
    job_id: UUID
    repository_url: str
    base_branch: str
    workspace_path: str
    workspace_branch: str


class GitStatusResponse(BaseModel):
    branch: str
    changed_files: list[str]
    clean: bool


class FileContentResponse(BaseModel):
    path: str
    content: str


@router.get("/jobs/{job_id}/workspace", response_model=WorkspaceResponse)
def get_workspace(job_id: UUID) -> WorkspaceResponse:
    if workflow_service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    workspace = repository_service.workspace_for_job(job_id)
    if workspace is None:
        raise HTTPException(status_code=409, detail="Workspace is not prepared")

    return WorkspaceResponse(
        job_id=workspace.job_id,
        repository_url=workspace.repository_url,
        base_branch=workspace.base_branch,
        workspace_path=str(workspace.path),
        workspace_branch=workspace.branch,
    )


@router.get("/jobs/{job_id}/workspace/status", response_model=GitStatusResponse)
def get_workspace_status(job_id: UUID) -> GitStatusResponse:
    try:
        result = git_service.status(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return GitStatusResponse(
        branch=result.branch,
        changed_files=result.changed_files,
        clean=result.clean,
    )


@router.get("/jobs/{job_id}/workspace/files", response_model=list[str])
def list_workspace_files(job_id: UUID, path: str = ".") -> list[str]:
    try:
        return filesystem_service.list_files(job_id, path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/workspace/file", response_model=FileContentResponse)
def read_workspace_file(job_id: UUID, path: str) -> FileContentResponse:
    try:
        content = filesystem_service.read_text(job_id, path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileContentResponse(path=path, content=content)


@router.get("/jobs/{job_id}/workspace/diff")
def get_workspace_diff(job_id: UUID) -> dict[str, str]:
    try:
        return {"diff": git_service.diff(job_id)}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/jobs/{job_id}/workspace", status_code=204)
def cleanup_workspace(job_id: UUID) -> None:
    if workflow_service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    repository_service.cleanup_workspace(job_id)
