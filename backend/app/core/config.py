from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Development Workflow"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://workflow:workflow@localhost:5432/development_workflow"
    langgraph_database_url: str = "postgres://workflow:workflow@localhost:5432/development_workflow?sslmode=disable"
    max_workers: int = 2
    worker_poll_interval_seconds: float = 1.0
    worker_cwd: str = "."
    worker_heartbeat_interval_seconds: float = 5.0
    worker_lease_seconds: int = 30
    repository_cache_root: str = ".factory/repositories"
    workspace_root: str = ".factory/workspaces"
    git_command_timeout_seconds: int = 120

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
