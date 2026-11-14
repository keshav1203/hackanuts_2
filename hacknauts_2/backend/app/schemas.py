from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class TokenOut(BaseModel):
    token: str
    email: str


class UserOut(BaseModel):
    email: str


class AnalysisIn(BaseModel):
    repo_url: str = Field(max_length=300)
    target_users: int = Field(1000, ge=1, le=10_000_000)
    # Single honest model entry – three specialised agents run internally
    model: Literal["scaleai-groq"] = "scaleai-groq"


class ReportOut(BaseModel):
    id: int
    status: str
    stage: str
    error: str | None
    model: str
    target_users: int
    repo_url: str
    repo_name: str
    language: str | None
    framework: str | None
    architecture: dict | None
    # Legacy flat findings list (backward compat with existing ReportView)
    findings: list[dict] | None
    summary: str | None
    ai_used: bool
    # Structured agent results
    code_analysis: dict | None = None
    performance_analysis: dict | None = None
    optimization: dict | None = None
    agent_errors: list[str] | None = None
    created_at: datetime
    finished_at: datetime | None
    load_test: dict | None = None  # future k6 execution results


class ReportListItem(BaseModel):
    id: int
    status: str
    repo_name: str
    created_at: datetime


class QueryIn(BaseModel):
    query: str
    model: str | None = None


class QueryOut(BaseModel):
    answer: str
