from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.jobs import router as jobs_router
from app.api.test_controls import router as test_controls_router
from app.db import init_db
from app.services.checkpointer import checkpointer_manager
from app.services.workflow_service import workflow_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    workflow_service.start()
    yield
    workflow_service.stop()
    checkpointer_manager.stop()


app = FastAPI(
    title="Development Workflow",
    description="AI-assisted software development workflow",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(jobs_router, prefix="/api")
app.include_router(test_controls_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
