from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "factory_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    stage: Mapped[str] = mapped_column(String(100), default="CREATED")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("factory_jobs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class TestFailureControl(Base):
    __tablename__ = "workflow_test_failure_control"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failures_remaining: Mapped[int] = mapped_column(Integer, default=0)


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    # create_all() does not add columns to an existing table. Keep this lightweight
    # compatibility migration until Alembic is introduced.
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE factory_jobs ADD COLUMN IF NOT EXISTS worker_id VARCHAR(100)"))
        connection.execute(text("ALTER TABLE factory_jobs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ"))
        connection.execute(text("ALTER TABLE factory_jobs ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ"))
