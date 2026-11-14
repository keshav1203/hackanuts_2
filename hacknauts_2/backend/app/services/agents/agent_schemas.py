"""
Pydantic schemas for all three ScaleAI agents.

All fields are typed and validated.  The schemas serve three purposes:
1. Document the contract for each agent.
2. Validate Groq API responses.
3. Can be serialised directly to JSON for database storage.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared / common
# ---------------------------------------------------------------------------

Severity = Literal["critical", "high", "medium", "low", "info"]
Priority = Literal["critical", "high", "medium", "low"]
Risk = Literal["high", "medium", "low"]
ExecutionStatus = Literal["not_started", "running", "completed", "failed", "skipped"]


# ---------------------------------------------------------------------------
# Agent 1 – Code Analysis
# ---------------------------------------------------------------------------

class CodeFinding(BaseModel):
    finding_id: str = Field(description="Unique finding identifier, e.g. CA-001")
    title: str
    category: str = Field(description="e.g. database, code-quality, security, scalability")
    severity: Severity
    file_path: str = Field(default="", description="Relative file path; empty for architecture findings")
    line_number: int = Field(default=0, description="1-based line number; 0 when not applicable")
    evidence: str = Field(description="Exact code snippet or scanner output that supports this finding")
    explanation: str = Field(description="2-4 sentences explaining why this hurts scalability")
    impact: str = Field(description="Expected impact under load")
    recommendation: str = Field(description="Specific actionable fix")
    confidence: float = Field(ge=0.0, le=1.0, description="Agent confidence in this finding")
    scanner_id: Optional[str] = Field(default=None, description="ID of the originating scanner finding if any")
    ai_generated: bool = Field(default=True)


class FindingStatistics(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class CodeAnalysisResult(BaseModel):
    agent: Literal["code_analysis"] = "code_analysis"
    overall_score: int = Field(ge=0, le=100, description="0 = many severe issues, 100 = clean")
    summary: str
    findings: list[CodeFinding]
    statistics: FindingStatistics


# ---------------------------------------------------------------------------
# Agent 2 – Performance Testing
# ---------------------------------------------------------------------------

class EndpointInfo(BaseModel):
    path: str
    method: str
    purpose: str
    authentication_required: bool
    testable: bool
    priority: Literal["high", "medium", "low"] = "medium"


class TestPlan(BaseModel):
    test_type: Literal["smoke", "load", "stress", "spike", "soak"] = "load"
    virtual_users: int
    duration: str = Field(description="k6 duration string, e.g. '2m'")
    ramp_up: str = Field(description="k6 duration string, e.g. '30s'")
    reason: str


class PerformanceMetrics(BaseModel):
    avg_response_ms: float
    min_response_ms: float
    max_response_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    rps: float = Field(description="Requests per second")
    total_requests: int
    failed_pct: float
    virtual_users: int
    throughput_kbps: Optional[float] = None


class PerformanceResult(BaseModel):
    agent: Literal["performance_testing"] = "performance_testing"
    summary: str
    endpoints: list[EndpointInfo]
    test_plan: TestPlan
    k6_script: str = Field(description="Valid k6 JavaScript test script")
    thresholds: dict[str, Any] = Field(
        default_factory=lambda: {"http_req_failed": 0.05, "http_req_duration_p95": 500}
    )
    warnings: list[str] = Field(default_factory=list)
    execution_status: ExecutionStatus = "not_started"
    metrics: Optional[PerformanceMetrics] = Field(
        default=None,
        description="Null until actual k6 execution results are available",
    )
    bottlenecks: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent 3 – Optimization
# ---------------------------------------------------------------------------

class Optimization(BaseModel):
    optimization_id: str = Field(description="e.g. OPT-001")
    title: str
    priority: Priority
    related_findings: list[str] = Field(
        default_factory=list,
        description="finding_id or scanner finding id references",
    )
    file_path: str = Field(default="")
    problem: str
    root_cause: str
    proposed_solution: str
    original_code: str = Field(default="", description="Minimal snippet showing the problem")
    optimized_code: str = Field(default="", description="Minimal replacement snippet")
    expected_benefit: str
    risk: Risk = "low"
    requires_approval: bool = True
    validation_steps: list[str] = Field(default_factory=list)


class OptimizationResult(BaseModel):
    agent: Literal["optimization"] = "optimization"
    summary: str
    optimizations: list[Optimization]
    overall_recommendation: str
    retest_required: bool = True


# ---------------------------------------------------------------------------
# Shared LangGraph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    # Inputs
    profile: dict
    scanner_findings: list[dict]
    model_key: str
    # Agent results
    code_analysis_result: Optional[CodeAnalysisResult]
    performance_result: Optional[PerformanceResult]
    optimization_result: Optional[OptimizationResult]
    # Legacy fields kept for backward compatibility with pipeline.py
    findings: list[dict]
    summary: str
    ai_used: bool
    # Error tracking
    errors: list[str]
