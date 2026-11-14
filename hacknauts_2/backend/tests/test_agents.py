import pytest

from app.services.agents.agent_schemas import (
    AgentState,
    CodeAnalysisResult,
    OptimizationResult,
    PerformanceResult,
)
from app.services.agents.code_analysis_agent import run_code_analysis_agent
from app.services.agents.optimization_agent import run_optimization_agent
from app.services.agents.performance_agent import run_performance_agent
from app.services.ai_agent import run_ai_agent


@pytest.fixture
def sample_profile():
    return {
        "primary_language": "Python",
        "frameworks": ["FastAPI"],
        "databases": ["PostgreSQL"],
        "orms": ["SQLAlchemy"],
        "cache": [],
        "queues": [],
        "endpoint_count": 2,
        "endpoints": [
            {"method": "GET", "path": "/users", "file": "app/users.py", "line": 10},
            {"method": "POST", "path": "/users", "file": "app/users.py", "line": 25},
        ],
        "files_scanned": 12,
        "has_container_config": True,
        "target_users": 200,
    }


@pytest.fixture
def sample_findings():
    return [
        {
            "id": "scan-1",
            "kind": "n_plus_one",
            "title": "Database query inside a loop",
            "severity": "High",
            "area": "Database",
            "file": "app/users.py",
            "line": 15,
            "snippet": "for u in users:\n    db.query(Profile).filter(Profile.user_id == u.id).first()",
            "why": "Each iteration sends a roundtrip.",
        }
    ]


def test_code_analysis_agent_independent(sample_profile, sample_findings):
    state: AgentState = {
        "profile": sample_profile,
        "scanner_findings": sample_findings,
        "model_key": "scaleai-groq",
        "errors": [],
    }
    out = run_code_analysis_agent(state)
    res = out.get("code_analysis_result")
    assert isinstance(res, CodeAnalysisResult)
    assert res.agent == "code_analysis"
    assert len(res.findings) >= 1
    assert res.findings[0].category.lower() in ("database", "code")
    assert res.findings[0].file_path == "app/users.py"
    assert res.overall_score >= 0 and res.overall_score <= 100


def test_performance_agent_independent(sample_profile):
    state: AgentState = {
        "profile": sample_profile,
        "model_key": "scaleai-groq",
        "errors": [],
    }
    out = run_performance_agent(state)
    res = out.get("performance_result")
    assert isinstance(res, PerformanceResult)
    assert res.agent == "performance_testing"
    assert res.execution_status == "not_started"
    # Strict rule: metrics must remain null before execution
    assert res.metrics is None
    assert len(res.endpoints) >= 1
    assert res.test_plan.virtual_users > 0
    assert "export default function" in res.k6_script or "export default ()" in res.k6_script


def test_optimization_agent_independent(sample_profile, sample_findings):
    code_state = run_code_analysis_agent({"profile": sample_profile, "scanner_findings": sample_findings})
    perf_state = run_performance_agent({"profile": sample_profile})

    state: AgentState = {
        "profile": sample_profile,
        "code_analysis_result": code_state.get("code_analysis_result"),
        "performance_result": perf_state.get("performance_result"),
        "model_key": "scaleai-groq",
        "errors": [],
    }
    out = run_optimization_agent(state)
    res = out.get("optimization_result")
    assert isinstance(res, OptimizationResult)
    assert res.agent == "optimization"
    assert len(res.optimizations) >= 1
    # Strict rule: all optimizations must require approval
    for opt in res.optimizations:
        assert opt.requires_approval is True
        assert opt.risk in ("high", "medium", "low")


def test_langgraph_orchestration_complete(sample_profile, sample_findings):
    stages_hit = []
    def track_stage(st):
        stages_hit.append(st)

    result = run_ai_agent(sample_profile, sample_findings, "scaleai-groq", stage_callback=track_stage)
    assert result["summary"] != ""
    assert result["code_analysis"] is not None
    assert result["performance"] is not None
    assert result["optimization"] is not None
    assert result["code_analysis"]["overall_score"] <= 100
    assert result["performance"]["metrics"] is None
    assert len(result["optimization"]["optimizations"]) >= 1
    assert "Running Code Analysis Agent" in stages_hit
