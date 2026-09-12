from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Development Workflow"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://workflow:workflow@localhost:5432/development_workflow"
    langgraph_database_url: str = "postgres://workflow:workflow@localhost:5432/development_workflow?sslmode=disable"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
