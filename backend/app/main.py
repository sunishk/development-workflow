from fastapi import FastAPI

from app.api.jobs import router as jobs_router

app = FastAPI(
    title="Development Workflow",
    description="AI-assisted software development workflow",
    version="0.1.0",
)

app.include_router(jobs_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
