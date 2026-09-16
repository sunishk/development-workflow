from dataclasses import dataclass
from uuid import UUID

from app.db import Job, SessionLocal
from app.services.coding_providers import build_provider
from app.services.event_service import event_service
from app.services.filesystem_service import filesystem_service
from app.services.repository_analysis_service import RepositoryProfile
from app.services.repository_service import repository_service
from app.services.workflow_catalog_service import workflow_catalog_service


@dataclass(frozen=True)
class CodingAgentResult:
    provider: str
    summary: str
    stdout: str
    stderr: str


class CodingAgentService:
    def implement(
        self,
        job_id: UUID,
        *,
        title: str,
        description: str,
        tasks: list[str],
        profile: RepositoryProfile,
        validation_feedback: str | None = None,
    ) -> CodingAgentResult:
        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job {job_id} not found")
            workflow_name = (job.workflow_name or "").strip()
        if not workflow_name:
            raise ValueError("Job has no workflow selected")

        instructions: dict[str, str] = {}
        for path in profile.instruction_files:
            try:
                instructions[path] = filesystem_service.read_text(job_id, path)[:20000]
            except (OSError, ValueError):
                continue

        # IMPLEMENT receives only implementation-specific instructions plus
        # cross-cutting coding standards. Planning/review/testing skills and the
        # full orchestrator document are intentionally excluded from this prompt.
        workflow_bundle = workflow_catalog_service.load(workflow_name, "IMPLEMENT")

        payload = {
            "job_id": str(job_id),
            "title": title,
            "description": description,
            "tasks": tasks,
            "repository_profile": profile.to_dict(),
            "repository_instructions": instructions,
            "validation_feedback": validation_feedback,
            "workflow": {
                "name": workflow_bundle.name,
                "stage": workflow_bundle.stage,
                "repository_commit": workflow_bundle.repository_commit,
                "skills": workflow_bundle.skills,
            },
        }

        event_service.record(
            job_id,
            "WORKFLOW_INSTRUCTIONS_LOADED",
            stage="IMPLEMENT",
            message=(
                f"workflow={workflow_bundle.name}; stage={workflow_bundle.stage}; "
                f"commit={workflow_bundle.repository_commit}; "
                f"skills={','.join(sorted(workflow_bundle.skills))}"
            )[:8000],
        )

        provider = build_provider()
        result = provider.execute(workspace.path, payload)
        event_service.record(
            job_id,
            "CODING_AGENT_COMPLETED",
            stage="IMPLEMENT",
            message=f"provider={result.provider}; {result.summary}"[:8000],
        )
        return CodingAgentResult(
            provider=result.provider,
            summary=result.summary,
            stdout=result.raw_stdout,
            stderr=result.raw_stderr,
        )


coding_agent_service = CodingAgentService()
