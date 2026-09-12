from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.jobs import router as jobs_router
from app.api.test_controls import router as test_controls_router
from app.core.config import settings
from app.db import init_db
from app.services.worker_manager import worker_manager


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    worker_manager.start()
    yield
    worker_manager.stop()


app = FastAPI(
    title="Development Workflow",
    description="AI-assisted software development workflow",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(jobs_router, prefix="/api")
if settings.environment != "production":
    app.include_router(test_controls_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
