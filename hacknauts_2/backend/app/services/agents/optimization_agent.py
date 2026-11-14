"""
ScaleAI – Optimization Agent (Agent 3)

Synthesizes findings from both the Code Analysis Agent and Performance Testing Agent.
Identifies root causes, correlates code-level bottlenecks with predicted or measured
performance issues, and generates minimal, maintainable code patches.

Security and Governance:
- All optimizations require developer approval (requires_approval: True).
- Code is NEVER automatically overwritten.
- Distinguishes code-based predictions from performance-verified recommendations.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ...config import settings
from ..groq_client import groq_chat, redact_secrets
from .agent_schemas import (
    AgentState,
    CodeAnalysisResult,
    Optimization,
    OptimizationResult,
    PerformanceResult,
)

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are ScaleAI's Senior Software Optimization Engineer.

You receive findings from the Code Analysis Agent and Performance Testing Agent.

Your responsibility is to identify root causes and propose safe, measurable improvements.

Do not blindly accept every finding from the other agents. Evaluate the evidence.

Prioritize changes according to their expected impact, implementation difficulty and risk.

Never claim an optimization improves performance without measured retest results.

Do not invent libraries, methods or framework APIs.

Generate minimal, maintainable patches.

Do not directly overwrite the user's source code.

All changes must be presented for developer approval.

When possible, explain the trade-offs and potential regressions.
"""


def _build_user_message(
    profile: dict,
    code_res: CodeAnalysisResult | None,
    perf_res: PerformanceResult | None,
) -> str:
    lang = profile.get("primary_language") or "unknown"
    frameworks = ", ".join(profile.get("frameworks", [])) or "none"
    databases = ", ".join(profile.get("databases", [])) or "none"

    code_findings_summary = []
    if code_res and code_res.findings:
        for f in code_res.findings[:settings.ai_max_findings]:
            code_findings_summary.append({
                "id": f.finding_id,
                "title": f.title,
                "category": f.category,
                "severity": f.severity,
                "file": f.file_path,
                "line": f.line_number,
                "evidence": redact_secrets(f.evidence[:300]),
                "explanation": f.explanation,
                "recommendation": f.recommendation,
            })

    perf_summary = {}
    if perf_res:
        perf_summary = {
            "test_type": perf_res.test_plan.test_type,
            "virtual_users": perf_res.test_plan.virtual_users,
            "predicted_bottlenecks": perf_res.bottlenecks,
            "warnings": perf_res.warnings,
            "has_real_metrics": perf_res.metrics is not None,
            "metrics": perf_res.metrics.model_dump() if perf_res.metrics else "Pending execution",
        }

    return f"""\
### APPLICATION PROFILE
- Primary Language: {lang}
- Frameworks: {frameworks}
- Databases: {databases}

### CODE ANALYSIS FINDINGS ({len(code_findings_summary)} items):
```json
{json.dumps(code_findings_summary, indent=2)}
```

### PERFORMANCE TESTING PERSPECTIVE:
```json
{json.dumps(perf_summary, indent=2)}
```

### OPTIMIZATION CATEGORIES TO TARGET:
- Database query optimization (N+1 query elimination, indexing, unbounded SELECTs)
- Caching layer introduction (in-memory, Redis)
- Asynchronous / non-blocking I/O patterns
- Algorithm efficiency (nested loops, duplicate iterations)
- Memory and connection pooling
- Pagination and payload minimization

### INSTRUCTIONS:
1. Synthesize the findings from Code Analysis and Performance Testing.
2. Select the highest-impact issues and formulate concrete optimizations.
3. For each optimization:
   - Provide original_code snippet illustrating the exact defect.
   - Provide optimized_code snippet showing the minimal drop-in improvement.
   - Detail the root cause and why the change relieves pressure under concurrent load.
   - Assess risk ('high', 'medium', 'low') and provide clear validation_steps.
   - Set requires_approval to true.
4. Set retest_required to true.
5. Provide a clear overall_recommendation.
6. Return strictly valid JSON conforming to the OptimizationResult schema.
"""


def _fallback_result(
    code_res: CodeAnalysisResult | None,
    perf_res: PerformanceResult | None,
) -> OptimizationResult:
    """Build a sensible OptimizationResult from available findings without AI."""
    optimizations: list[Optimization] = []

    if code_res and code_res.findings:
        for i, f in enumerate(code_res.findings[:4], 1):
            opt_id = f"OPT-{i:03d}"
            snippet = f.evidence or "# Review code in " + (f.file_path or "repository")
            patch = f.recommendation or "# Apply suggested scalability fix"
            optimizations.append(
                Optimization(
                    optimization_id=opt_id,
                    title=f"Optimize: {f.title}",
                    priority="high" if f.severity in ("critical", "high") else "medium",
                    related_findings=[f.finding_id],
                    file_path=f.file_path,
                    problem=f.explanation or f.impact,
                    root_cause=f"Inefficiency identified in {f.category}: {f.title}",
                    proposed_solution=f.recommendation,
                    original_code=snippet[:300],
                    optimized_code=patch[:300],
                    expected_benefit="Reduces request latency and database lock contention under load.",
                    risk="low" if f.severity in ("low", "medium") else "medium",
                    requires_approval=True,
                    validation_steps=[
                        f"Review code patch in {f.file_path}:{f.line_number}",
                        "Run existing test suite to prevent regressions",
                        "Verify behavior under simulated load",
                    ],
                )
            )

    if not optimizations:
        optimizations.append(
            Optimization(
                optimization_id="OPT-001",
                title="Baseline Scalability Review",
                priority="low",
                related_findings=[],
                file_path="",
                problem="No major bottlenecks identified in scanner results.",
                root_cause="Standard architecture configuration.",
                proposed_solution="Profile API endpoints under simulated load with k6.",
                original_code="",
                optimized_code="",
                expected_benefit="Establish baseline telemetry for future iterations.",
                risk="low",
                requires_approval=True,
                validation_steps=["Execute baseline smoke test"],
            )
        )

    return OptimizationResult(
        summary="Synthesized optimization recommendations based on static scanner findings. Developer review is required before applying patches.",
        optimizations=optimizations,
        overall_recommendation="Prioritize high-impact database query refactoring and verify with targeted k6 load tests.",
        retest_required=True,
    )


def run_optimization_agent(state: AgentState) -> AgentState:
    """LangGraph node: executes the Optimization Agent."""
    profile = state.get("profile", {})
    code_res = state.get("code_analysis_result")
    perf_res = state.get("performance_result")
    errors = list(state.get("errors") or [])

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(profile, code_res, perf_res)},
    ]

    result: OptimizationResult | None = groq_chat(
        messages=messages,
        model=settings.groq_optimization_model,
        schema_cls=OptimizationResult,
        temperature=settings.groq_temperature,
    )

    if result is None:
        log.warning("Optimization Agent: Groq call failed; using fallback recommendations")
        errors.append("optimization: Groq unavailable; fell back to rule-based optimizations")
        result = _fallback_result(code_res, perf_res)

    # Enforce approval requirement
    for opt in result.optimizations:
        opt.requires_approval = True

    log.info("Optimization Agent completed: %d optimization suggestions", len(result.optimizations))

    return {**state, "optimization_result": result, "errors": errors}
