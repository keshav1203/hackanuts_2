"""
ScaleAI – LangGraph Orchestration for Three Groq-Powered Agents.

Workflow Graph:
    START
      |
    code_analysis_node    (Code Analysis Agent: enriches scanner findings)
      |
    performance_node      (Performance Testing Agent: API & k6 load test planning)
      |
    optimization_node     (Optimization Agent: root causes & minimal code patches)
      |
    combined_report_node  (Synthesizes cross-agent executive report & health metrics)
      |
    END

Error Isolation & Resilience:
- Each node executes within an isolated error boundary.
- If an individual agent encounters an unrecoverable API error or validation issue,
  the error is captured in `state["errors"]` and fallback data is populated.
- The pipeline never crashes silently or terminates prematurely.
"""
from __future__ import annotations

import logging
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .agents.agent_schemas import AgentState, CodeAnalysisResult, OptimizationResult, PerformanceResult
from .agents.code_analysis_agent import run_code_analysis_agent
from .agents.optimization_agent import run_optimization_agent
from .agents.performance_agent import run_performance_agent
from .k6_service import execute_performance_load_test

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wrapped nodes with error boundaries
# ---------------------------------------------------------------------------

def _safe_node(fn, state: AgentState, agent_name: str) -> AgentState:
    """Execute an agent node safely, recording any unexpected exceptions."""
    try:
        return fn(state)
    except Exception as exc:
        log.exception("Agent node %s failed unexpectedly: %s", agent_name, exc)
        errors = list(state.get("errors") or [])
        errors.append(f"{agent_name}: unexpected error ({type(exc).__name__})")
        return {**state, "errors": errors}


def code_analysis_node(state: AgentState) -> AgentState:
    cb = state.get("stage_callback")
    if cb:
        try:
            cb("Running Code Analysis Agent")
        except Exception:
            pass
    # Ensure profile and repository_profile are consistent
    if not state.get("profile") and state.get("repository_profile"):
        state["profile"] = state["repository_profile"]
    elif not state.get("repository_profile") and state.get("profile"):
        state["repository_profile"] = state["profile"]
    return _safe_node(run_code_analysis_agent, state, "code_analysis")


def performance_node(state: AgentState) -> AgentState:
    time.sleep(2.0)
    cb = state.get("stage_callback")
    if cb:
        try:
            cb("Running Performance Agent")
        except Exception:
            pass
    out = _safe_node(run_performance_agent, state, "performance")
    # Keep performance_analysis_result and performance_result synced
    if "performance_result" in out and "performance_analysis_result" not in out:
        out["performance_analysis_result"] = out["performance_result"]
    return out


def load_test_node(state: AgentState) -> AgentState:
    """Execute empirical performance testing across concurrency steps to discover telemetry curves."""
    cb = state.get("stage_callback")
    if cb:
        try:
            cb("Executing Performance & Load Testing")
        except Exception:
            pass

    perf_res = state.get("performance_result")
    profile = state.get("profile") or state.get("repository_profile") or {}
    target_users = profile.get("target_users", 50)
    script = getattr(perf_res, "k6_script", None) if perf_res else None
    if not script and isinstance(perf_res, dict):
        script = perf_res.get("k6_script")
    if not script:
        script = "export default function() {}"

    try:
        metrics, curve, notice = execute_performance_load_test(
            script=script,
            target_users=target_users,
            base_url="http://localhost:8000",
        )
        if metrics:
            if perf_res:
                if hasattr(perf_res, "metrics"):
                    perf_res.metrics = metrics
                    perf_res.execution_status = "completed"
                elif isinstance(perf_res, dict):
                    perf_res["metrics"] = metrics.model_dump()
                    perf_res["execution_status"] = "completed"

            state["load_test"] = {
                "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "notice": notice,
                "metrics": metrics.model_dump(),
                "curve": curve,
            }
    except Exception as exc:
        log.exception("Empirical load test execution failed: %s", exc)
        errors = list(state.get("errors") or [])
        errors.append(f"load_test: {exc}")
        state["errors"] = errors

    return state


def optimization_node(state: AgentState) -> AgentState:
    time.sleep(2.0)
    cb = state.get("stage_callback")
    if cb:
        try:
            cb("Running Optimization Agent")
        except Exception:
            pass
    return _safe_node(run_optimization_agent, state, "optimization")


def combined_report_node(state: AgentState) -> AgentState:
    """
    Synthesize findings from all three agents into an overarching executive summary
    and set pipeline execution status.
    """
    code_res: CodeAnalysisResult | None = state.get("code_analysis_result")
    perf_res: PerformanceResult | None = state.get("performance_result")
    opt_res: OptimizationResult | None = state.get("optimization_result")
    errors = state.get("errors") or []

    code_findings_cnt = len(code_res.findings) if code_res else 0
    endpoints_cnt = len(perf_res.endpoints) if perf_res else 0
    optimizations_cnt = len(opt_res.optimizations) if opt_res else 0
    score = code_res.overall_score if code_res else 80

    exec_status = "completed" if not errors else "completed_with_warnings"

    # Distinguish whether recommendations are code-based or performance-verified
    has_real_metrics = perf_res is not None and perf_res.metrics is not None
    perf_verification_note = (
        "Empirical k6 metrics have been recorded."
        if has_real_metrics
        else "Performance tests are configured but pending execution; optimizations are prioritized from code-level static analysis."
    )

    summary_paragraphs = []
    if code_res and code_res.summary:
        summary_paragraphs.append(code_res.summary)
    if perf_res and perf_res.summary:
        summary_paragraphs.append(perf_res.summary)
    if opt_res and opt_res.overall_recommendation:
        summary_paragraphs.append(opt_res.overall_recommendation)

    combined_summary = (
        " ".join(summary_paragraphs)
        if summary_paragraphs
        else (
            f"ScaleAI completed analysis with overall health score of {score}/100. "
            f"Identified {code_findings_cnt} code findings, mapped {endpoints_cnt} endpoints, "
            f"and proposed {optimizations_cnt} targeted optimizations. {perf_verification_note}"
        )
    )

    return {
        **state,
        "combined_summary": combined_summary,
        "summary": combined_summary,
        "execution_status": exec_status,
    }


# ---------------------------------------------------------------------------
# Graph definition
# ---------------------------------------------------------------------------

def _build_graph() -> object:
    g = StateGraph(AgentState)
    g.add_node("code_analysis", code_analysis_node)
    g.add_node("performance", performance_node)
    g.add_node("load_test", load_test_node)
    g.add_node("optimization", optimization_node)
    g.add_node("combined_report", combined_report_node)

    g.add_edge(START, "code_analysis")
    g.add_edge("code_analysis", "performance")
    g.add_edge("performance", "load_test")
    g.add_edge("load_test", "optimization")
    g.add_edge("optimization", "combined_report")
    g.add_edge("combined_report", END)

    return g.compile()


_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# Public Entrypoint
# ---------------------------------------------------------------------------

def run_ai_agent(
    profile: dict,
    findings: list[dict],
    model_key: str,
    stage_callback: Any = None,
) -> dict:
    """
    Run the coordinated ScaleAI multi-agent pipeline via LangGraph.

    Parameters
    ----------
    profile:        Stack profile dictionary (from detect_stack).
    findings:       Deterministic scanner findings.
    model_key:      Frontend identifier for tracking.
    stage_callback: Optional callable(stage_name: str) to report progress.
    """
    if stage_callback:
        try:
            stage_callback("Running Code Analysis Agent")
        except Exception:
            pass

    initial_state: AgentState = {
        "profile": profile,
        "repository_profile": profile,
        "scanner_findings": findings,
        "model_key": model_key,
        "findings": findings,
        "summary": "",
        "ai_used": False,
        "errors": [],
        "execution_status": "running",
        "stage_callback": stage_callback,
    }

    # If stage_callback provided, update stage before performance and optimization
    out: AgentState = _GRAPH.invoke(initial_state)

    code_res = out.get("code_analysis_result")
    perf_res = out.get("performance_result") or out.get("performance_analysis_result")
    opt_res = out.get("optimization_result")

    ai_used = bool(
        out.get("ai_used")
        or (perf_res is not None and not any("performance: Groq unavailable" in e for e in out.get("errors", [])))
        or (opt_res is not None and not any("optimization: Groq unavailable" in e for e in out.get("errors", [])))
    )

    return {
        "findings": out.get("findings", findings),
        "summary": out.get("summary", out.get("combined_summary", "")),
        "ai_used": ai_used,
        "code_analysis": code_res.model_dump() if code_res is not None else None,
        "performance": perf_res.model_dump() if perf_res is not None else None,
        "optimization": opt_res.model_dump() if opt_res is not None else None,
        "load_test": out.get("load_test"),
        "agent_errors": out.get("errors", []),
        "execution_status": out.get("execution_status", "completed"),
    }
