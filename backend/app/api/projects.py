import subprocess
import sys
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.db import Project, SessionLocal

router = APIRouter(tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1)
    local_path: str = Field(min_length=1)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    local_path: str | None
    base_branch: str


class BrowseProjectResponse(BaseModel):
    path: str


def _git_output(local_path: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(local_path), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.git_command_timeout_seconds,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail="Selected folder is not a Git repository") from exc
    return result.stdout.strip()


def _validate_local_project(raw_path: str) -> tuple[Path, str]:
    path = Path(raw_path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Local project folder does not exist")

    root = Path(_git_output(path, "rev-parse", "--show-toplevel")).resolve()
    if root != path:
        raise HTTPException(
            status_code=400,
            detail=f"Select the Git repository root folder: {root}",
        )

    branch = _git_output(path, "branch", "--show-current")
    if not branch:
        raise HTTPException(status_code=400, detail="Detached HEAD is not supported; checkout a branch first")
    return path, branch


def to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        local_path=project.local_path,
        base_branch=project.base_branch,
    )


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects() -> list[ProjectResponse]:
    with SessionLocal() as db:
        projects = db.scalars(select(Project).order_by(Project.updated_at.desc())).all()
        return [to_response(project) for project in projects]


def _browse_macos() -> str:
    script = 'POSIX path of (choose folder with prompt "Select a local Git project")'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail="Folder selection cancelled")
    return str(Path(result.stdout.strip()).resolve())


def _browse_windows() -> str:
    # FolderBrowserDialog can open behind the browser/terminal when it is launched
    # by the Uvicorn process. Give it an invisible top-most owner so Windows brings
    # the native picker to the foreground. PowerShell must run in STA mode for
    # Windows Forms dialogs.
    script = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$owner = New-Object System.Windows.Forms.Form
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$owner.Location = New-Object System.Drawing.Point(-32000, -32000)
$owner.Size = New-Object System.Drawing.Size(1, 1)
$dialog.Description = 'Select a local Git project'
$dialog.ShowNewFolderButton = $false

try {
    $owner.Show()
    $owner.Activate()
    $result = $dialog.ShowDialog($owner)
    if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
        Write-Output $dialog.SelectedPath
        exit 0
    }
    exit 2
}
finally {
    $dialog.Dispose()
    $owner.Dispose()
}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "Folder selection cancelled"
        raise HTTPException(status_code=400, detail=detail)
    selected = result.stdout.strip()
    if not selected:
        raise HTTPException(status_code=400, detail="Folder selection cancelled")
    return str(Path(selected).resolve())


@router.post("/projects/browse", response_model=BrowseProjectResponse)
def browse_project_folder() -> BrowseProjectResponse:
    try:
        if sys.platform == "darwin":
            selected_path = _browse_macos()
        elif sys.platform == "win32":
            selected_path = _browse_windows()
        else:
            raise HTTPException(
                status_code=501,
                detail="Native folder browsing is supported on macOS and Windows; enter the local path manually on this platform",
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Native folder browser command is not available") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=408, detail="Folder selection timed out; enter the local path manually") from exc

    return BrowseProjectResponse(path=selected_path)


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(request: CreateProjectRequest) -> ProjectResponse:
    local_path, branch = _validate_local_project(request.local_path)
    with SessionLocal() as db:
        project = Project(
            name=request.name.strip(),
            local_path=str(local_path),
            repository_url=None,
            base_branch=branch,
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
