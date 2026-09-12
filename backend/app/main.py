from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.coding_provider import router as coding_provider_router
from app.api.dashboard import router as dashboard_router
from app.api.jobs import router as jobs_router
from app.api.projects import router as projects_router
from app.api.repositories import router as repositories_router
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
    version="0.7.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(repositories_router, prefix="/api")
app.include_router(coding_provider_router, prefix="/api")
if settings.environment != "production":
    app.include_router(test_controls_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
