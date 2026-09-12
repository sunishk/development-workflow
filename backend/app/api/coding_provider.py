import shutil

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/coding-provider", tags=["coding provider"])


class CodingProviderStatusResponse(BaseModel):
    provider: str
    available: bool
    executable: str | None
    model: str | None
    message: str


@router.get("/status", response_model=CodingProviderStatusResponse)
def coding_provider_status() -> CodingProviderStatusResponse:
    provider = settings.coding_provider.strip().lower()

    if provider == "codex":
        executable = shutil.which(settings.codex_binary)
        available = executable is not None
        return CodingProviderStatusResponse(
            provider="codex",
            available=available,
            executable=executable,
            model=settings.codex_model.strip() or None,
            message=(
                "Codex CLI is available; authentication is validated when an implementation job runs."
                if available
                else f"Codex CLI executable '{settings.codex_binary}' was not found on PATH."
            ),
        )

    if provider == "command":
        configured = bool(settings.coding_agent_command.strip())
        return CodingProviderStatusResponse(
            provider="command",
            available=configured,
            executable=None,
            model=None,
            message=(
                "Custom coding command is configured."
                if configured
                else "CODING_AGENT_COMMAND is empty."
            ),
        )

    return CodingProviderStatusResponse(
        provider=provider or "unknown",
        available=False,
        executable=None,
        model=None,
        message=f"Unsupported coding provider '{settings.coding_provider}'.",
    )
