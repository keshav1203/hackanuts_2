from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # one active session per email
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("user_id", "url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    url: Mapped[str] = mapped_column(String(300))
    full_name: Mapped[str] = mapped_column(String(200))
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    framework: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued | running | done | failed
    stage: Mapped[str] = mapped_column(String(80), default="Queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(40), default="scaleai-groq")
    target_users: Mapped[int] = mapped_column(Integer, default=1000)
    architecture: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Legacy scalar fields – kept for backward compatibility
    findings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_used: Mapped[bool] = mapped_column(Boolean, default=False)
    # Agent result fields (populated by the three-agent pipeline)
    code_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    performance_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    optimization: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    load_test: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repository: Mapped[Repository] = relationship()
