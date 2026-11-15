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
    finding_id: str = Field(default="CA-001", description="Unique finding identifier, e.g. CA-001")
    title: str = "Scalability finding"
    category: str = Field(default="code", description="e.g. database, code-quality, security, scalability")
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

    @model_validator(mode="before")
    @classmethod
    def _normalize_finding_dict(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "finding_id" not in data:
                data["finding_id"] = str(data.get("id") or "CA-001")
            if "category" not in data:
                data["category"] = str(data.get("area") or data.get("kind") or "code")
            if "file_path" not in data:
                data["file_path"] = str(data.get("file") or "")
            if "line_number" not in data:
                try:
                    data["line_number"] = int(data.get("line") or 0)
                except Exception:
                    data["line_number"] = 0
            if "evidence" not in data and "snippet" in data:
                data["evidence"] = str(data["snippet"])
            if "impact" not in data:
                data["impact"] = str(data.get("practical_impact") or data.get("impact_under_load") or "May increase latency under load.")
            if "explanation" not in data:
                data["explanation"] = str(data.get("why") or data.get("description") or "Bottleneck identified under concurrent load.")
            if "recommendation" not in data:
                data["recommendation"] = str(data.get("suggested_fix") or "Refactor code following best practices.")
        return data

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
    summary: str = "Code analysis completed."
    findings: list[CodeFinding] = Field(default_factory=list)
    statistics: FindingStatistics = Field(default_factory=FindingStatistics)

    @field_validator("agent", mode="before")
    @classmethod
    def _normalize_agent(cls, v: Any) -> str:
        return "code_analysis"

    @model_validator(mode="before")
    @classmethod
    def _ensure_statistics(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["agent"] = "code_analysis"
            if "summary" not in data or not data["summary"]:
                data["summary"] = "Code analysis identified scalability bottlenecks and scanner insights."
            if "overall_score" not in data:
                data["overall_score"] = 80
            else:
                try:
                    data["overall_score"] = max(0, min(100, int(data["overall_score"])))
                except Exception:
                    data["overall_score"] = 80
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
    path: str = "/"
    method: str = "GET"
    purpose: str = ""
    authentication_required: bool = False
    testable: bool = True
    priority: Literal["high", "medium", "low"] = "medium"

    @model_validator(mode="before")
    @classmethod
    def _normalize_endpoint_dict(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "path" not in data:
                data["path"] = str(data.get("url") or data.get("route") or data.get("endpoint") or "/")
            if "method" not in data:
                data["method"] = str(data.get("http_method") or "GET").upper()
            if "priority" in data and isinstance(data["priority"], str):
                p = data["priority"].lower().strip()
                data["priority"] = p if p in ("high", "medium", "low") else "medium"
        return data

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
        if isinstance(data, list):
            data = data[0] if (len(data) > 0 and isinstance(data[0], dict)) else {}
        if isinstance(data, dict):
            if "virtual_users" not in data:
                data["virtual_users"] = data.get("vus") or data.get("users") or data.get("target_vus") or 50
            if "test_type" not in data and "name" in data:
                data["test_type"] = data["name"]
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

    @field_validator("agent", mode="before")
    @classmethod
    def _normalize_agent(cls, v: Any) -> str:
        return "performance_testing"

    @model_validator(mode="before")
    @classmethod
    def _normalize_perf_result(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["agent"] = "performance_testing"
            if "summary" not in data or not data["summary"]:
                data["summary"] = "Automated performance testing plan generated."
            tp = data.get("test_plan")
            if isinstance(tp, list):
                if len(tp) > 0 and isinstance(tp[0], dict):
                    data["test_plan"] = next((p for p in tp if isinstance(p, dict) and p.get("name", "").lower() in ("load", "stress")), tp[0])
                else:
                    data["test_plan"] = {}
            if "endpoints" in data and isinstance(data["endpoints"], dict):
                eps = []
                for p, v in data["endpoints"].items():
                    if isinstance(v, dict):
                        v.setdefault("path", p)
                        eps.append(v)
                    elif isinstance(v, str):
                        eps.append({"path": p, "method": v})
                data["endpoints"] = eps
        return data


# ---------------------------------------------------------------------------
# Agent 3 – Optimization
# ---------------------------------------------------------------------------

class Optimization(BaseModel):
    optimization_id: str = Field(default="OPT-001", description="e.g. OPT-001")
    title: str = "Scalability optimization"
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

    @model_validator(mode="before")
    @classmethod
    def _normalize_opt(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "optimization_id" not in data:
                data["optimization_id"] = str(data.get("id") or "OPT-001")
            if "title" not in data:
                data["title"] = str(data.get("name") or data.get("action") or data.get("recommendation") or "Scalability optimization")
            if "file_path" not in data and "file" in data:
                data["file_path"] = str(data["file"])
            if "original_code" not in data and "before" in data:
                data["original_code"] = str(data["before"])
            if "optimized_code" not in data and "after" in data:
                data["optimized_code"] = str(data["after"])
            if "problem" not in data and "issue" in data:
                data["problem"] = str(data["issue"])
            data["requires_approval"] = True
            if "risk" in data and isinstance(data["risk"], str):
                r = data["risk"].lower().strip()
                data["risk"] = r if r in ("high", "medium", "low") else "low"
            if "priority" in data and isinstance(data["priority"], str):
                p = data["priority"].lower().strip()
                data["priority"] = p if p in ("critical", "high", "medium", "low") else "medium"
        return data

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

    @field_validator("agent", mode="before")
    @classmethod
    def _normalize_agent(cls, v: Any) -> str:
        return "optimization"

    @model_validator(mode="before")
    @classmethod
    def _normalize_opt_result(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["agent"] = "optimization"
            if "summary" not in data or not data["summary"]:
                data["summary"] = "Optimization suggestions formulated."
            if "optimizations" not in data:
                data["optimizations"] = data.get("recommendations") or data.get("patches") or []
        return data


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
