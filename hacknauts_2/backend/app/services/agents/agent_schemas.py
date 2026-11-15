"""
Pydantic schemas for all three ScaleAI agents.

All fields are typed and validated.  The schemas serve three purposes:
1. Document the contract for each agent.
2. Validate Groq API responses.
3. Can be serialised directly to JSON for database storage.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, Field, field_validator, model_validator

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
    severity: Severity = "medium"
    file_path: str = Field(default="", description="Relative file path; empty for architecture findings")
    line_number: int = Field(default=0, description="1-based line number; 0 when not applicable")
    evidence: str = Field(default="", description="Exact code snippet or scanner output that supports this finding")
    explanation: str = Field(default="", description="2-4 sentences explaining why this hurts scalability")
    impact: str = Field(default="", description="Expected impact under load")
    recommendation: str = Field(default="", description="Specific actionable fix")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Agent confidence in this finding")
    scanner_id: Optional[str] = Field(default=None, description="ID of the originating scanner finding if any")
    ai_generated: bool = Field(default=True)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v: Any) -> str:
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ("critical", "high", "medium", "low", "info"):
                return v_lower
        return "medium"

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(1.0, val))
        except Exception:
            return 0.8


class FindingStatistics(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class CodeAnalysisResult(BaseModel):
    agent: Literal["code_analysis"] = "code_analysis"
    overall_score: int = Field(default=80, ge=0, le=100, description="0 = many severe issues, 100 = clean")
    summary: str
    findings: list[CodeFinding] = Field(default_factory=list)
    statistics: FindingStatistics = Field(default_factory=FindingStatistics)

    @model_validator(mode="before")
    @classmethod
    def _ensure_statistics(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "statistics" not in data or not isinstance(data.get("statistics"), dict):
                findings = data.get("findings", [])
                stats = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
                if isinstance(findings, list):
                    for f in findings:
                        if isinstance(f, dict):
                            sev = str(f.get("severity", "medium")).lower()
                            if sev in stats:
                                stats[sev] += 1
                            else:
                                stats["medium"] += 1
                data["statistics"] = stats
        return data


# ---------------------------------------------------------------------------
# Agent 2 – Performance Testing
# ---------------------------------------------------------------------------

class EndpointInfo(BaseModel):
    path: str
    method: str
    purpose: str = ""
    authentication_required: bool = False
    testable: bool = True
    priority: Literal["high", "medium", "low"] = "medium"

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, v: Any) -> str:
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ("high", "medium", "low"):
                return v_lower
        return "medium"


class TestPlan(BaseModel):
    test_type: Literal["smoke", "load", "stress", "spike", "soak"] = "load"
    virtual_users: int = 50
    duration: str = Field(default="2m", description="k6 duration string, e.g. '2m'")
    ramp_up: str = Field(default="30s", description="k6 duration string, e.g. '30s'")
    reason: str = "Automated load testing plan"

    @model_validator(mode="before")
    @classmethod
    def _normalize_plan(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "virtual_users" not in data and "vus" in data:
                data["virtual_users"] = data["vus"]
            # If model returned a map of scenarios: e.g. {'load': {'vus': 50, ...}}
            for key in ("load", "stress", "smoke", "spike", "soak"):
                if key in data and isinstance(data[key], dict):
                    sub = data[key]
                    data.setdefault("test_type", key)
                    data.setdefault("virtual_users", sub.get("vus", sub.get("virtual_users", 50)))
                    data.setdefault("duration", sub.get("duration", "2m"))
                    data.setdefault("reason", sub.get("description", f"{key} test plan"))
                    break
            # Coerce virtual_users
            if "virtual_users" in data:
                try:
                    data["virtual_users"] = int(data["virtual_users"])
                except Exception:
                    data["virtual_users"] = 50
            if "test_type" in data and isinstance(data["test_type"], str):
                t_lower = data["test_type"].lower().strip()
                if t_lower in ("smoke", "load", "stress", "spike", "soak"):
                    data["test_type"] = t_lower
                else:
                    data["test_type"] = "load"
        return data


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
    summary: str = "Automated performance evaluation plan"
    endpoints: list[EndpointInfo] = Field(default_factory=list)
    test_plan: TestPlan = Field(default_factory=TestPlan)
    k6_script: str = Field(
        default="import http from 'k6/http';\nexport default function () { http.get(__ENV.BASE_URL || 'http://localhost:8000'); }",
        description="Valid k6 JavaScript test script",
    )
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
    priority: Priority = "medium"
    related_findings: list[str] = Field(
        default_factory=list,
        description="finding_id or scanner finding id references",
    )
    file_path: str = Field(default="")
    problem: str = ""
    root_cause: str = ""
    proposed_solution: str = ""
    original_code: str = Field(default="", description="Minimal snippet showing the problem")
    optimized_code: str = Field(default="", description="Minimal replacement snippet")
    expected_benefit: str = ""
    risk: Risk = "low"
    requires_approval: bool = True
    validation_steps: list[str] = Field(default_factory=list)

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_opt_priority(cls, v: Any) -> str:
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ("critical", "high", "medium", "low"):
                return v_lower
        return "medium"

    @field_validator("risk", mode="before")
    @classmethod
    def _normalize_risk(cls, v: Any) -> str:
        if isinstance(v, str):
            v_lower = v.strip().lower()
            if v_lower in ("high", "medium", "low"):
                return v_lower
        return "low"


class OptimizationResult(BaseModel):
    agent: Literal["optimization"] = "optimization"
    summary: str = "Automated optimization recommendations"
    optimizations: list[Optimization] = Field(default_factory=list)
    overall_recommendation: str = Field(default="Prioritize high-impact query refactoring and verify with load tests.")
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
