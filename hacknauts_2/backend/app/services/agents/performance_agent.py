"""
ScaleAI – Performance Testing Agent (Agent 2)

Analyzes repository architecture, identified endpoints, and user traffic targets.
Recommends load testing scenarios (smoke, load, stress, spike, soak), generates
executable k6 JavaScript scripts with checks and thresholds, and predicts potential
bottlenecks.

Crucial constraint:
- `metrics` MUST remain null until actual k6 execution results are provided.
- `execution_status` defaults to 'not_started'.
"""
from __future__ import annotations

import json
import logging

from ...config import settings
from ..groq_client import groq_chat
from .agent_schemas import (
    AgentState,
    EndpointInfo,
    PerformanceResult,
    TestPlan,
)

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are ScaleAI's Senior Performance Testing Engineer.

You specialize in API performance, load testing, scalability engineering and k6.

Your job is to understand application architecture, recommend safe performance tests and interpret actual test results.

Never invent performance measurements.

Never claim a test was executed unless actual execution results are supplied.

Separate predicted bottlenecks from experimentally verified bottlenecks.

Generated k6 scripts must be valid JavaScript compatible with k6.

Use appropriate checks, thresholds, scenarios and HTTP request handling.

Do not generate arbitrary destructive operations.

Explain why each traffic scenario is useful.
"""

K6_GUIDANCE = """\
Write standard k6 JavaScript (ES6, not Node.js).
Do NOT import node modules (fs, path, etc.).
Import only from 'k6', 'k6/http', 'k6/metrics'.
Use `__ENV.BASE_URL || 'http://localhost:8000'` as the base URL.
Include options with stages and thresholds.
Add response status checks and sleep pacing in the default function.
"""


def _build_user_message(profile: dict, target_users: int) -> str:
    lang = profile.get("primary_language") or "unknown"
    frameworks = ", ".join(profile.get("frameworks", [])) or "none"
    databases = ", ".join(profile.get("databases", [])) or "none"
    cache = ", ".join(profile.get("cache", [])) or "none"
    queues = ", ".join(profile.get("queues", [])) or "none"
    has_docker = profile.get("has_container_config", False)

    endpoints = [
        {"method": e.get("method", "GET"), "path": e.get("path", "/")}
        for e in profile.get("endpoints", [])[:5]
    ]
    endpoint_json = json.dumps(endpoints, indent=2)

    return f"""\
### APPLICATION PROFILE
- Primary Language: {lang}
- Frameworks: {frameworks}
- Databases: {databases}
- Cache Layer: {cache}
- Job Queues: {queues}
- Docker/Containerized: {has_docker}
- Target Concurrent Users: {target_users}

### DISCOVERED APPLICATION ENDPOINTS ({len(endpoints)} detected):
{endpoint_json}

### K6 SCRIPTING GUIDELINES:
{K6_GUIDANCE}

### SCENARIOS TO CONSIDER:
1. Smoke: 1-2 VUs, short duration, availability verification.
2. Load: 10-50 VUs, normal traffic patterns.
3. Stress: higher load ramp to detect failure threshold.
4. Spike: sudden burst of VUs to evaluate recovery.
5. Soak: moderate sustained load to detect resource leaks.

### INSTRUCTIONS:
1. Map up to 3 key endpoints to EndpointInfo objects (method, path, concise purpose, auth required, testable).
2. Configure a safe test plan suitable for {target_users} target users.
3. Generate a minimal valid k6 JavaScript script adhering to k6 syntax (under 15 lines).
4. Include realistic thresholds (e.g. p95 < 500ms, failed requests < 5%).
5. List architectural warnings and up to 2 predicted bottlenecks.
6. Set execution_status to "not_started" and metrics to null.
7. Return strictly valid JSON conforming to the PerformanceResult schema.
"""


def _fallback_result(profile: dict, target_users: int) -> PerformanceResult:
    """Fallback valid PerformanceResult when Groq is unavailable."""
    endpoints_raw = profile.get("endpoints", [])
    endpoint_infos = [
        EndpointInfo(
            path=e.get("path", "/"),
            method=e.get("method", "GET"),
            purpose="Discovered endpoint",
            authentication_required=False,
            testable=True,
            priority="high" if e.get("method", "GET").upper() == "GET" else "medium",
        )
        for e in endpoints_raw[:12]
    ]

    vu = max(1, min(target_users, 50))
    test_type = "smoke" if target_users <= 5 else ("load" if target_users <= 100 else "stress")

    script = f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {{
  stages: [
    {{ duration: '30s', target: {vu} }},
    {{ duration: '1m', target: {vu} }},
    {{ duration: '30s', target: 0 }},
  ],
  thresholds: {{
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<500'],
  }},
}};

export default function () {{
  const res = http.get(`${{BASE_URL}}/health`);
  check(res, {{
    'status is 200': (r) => r.status === 200,
  }});
  sleep(1);
}}
"""
    return PerformanceResult(
        summary=f"Automated performance test plan configured for {vu} virtual users simulating {test_type} testing.",
        endpoints=endpoint_infos,
        test_plan=TestPlan(
            test_type=test_type,
            virtual_users=vu,
            duration="2m",
            ramp_up="30s",
            reason=f"Targeting {target_users} concurrent users based on repository architecture.",
        ),
        k6_script=script,
        thresholds={"http_req_failed": 0.05, "http_req_duration_p95": 500},
        warnings=["Groq AI offline; generated baseline template script. Verify endpoint parameters before execution."],
        execution_status="not_started",
        metrics=None,
        bottlenecks=["Predicted: Database read lock contention under high concurrency."],
    )


def run_performance_agent(state: AgentState) -> AgentState:
    """LangGraph node: executes the Performance Testing Agent."""
    profile = state.get("profile", {})
    errors = list(state.get("errors") or [])
    target_users = profile.get("target_users", 1000)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(profile, target_users)},
    ]

    result: PerformanceResult | None = groq_chat(
        messages=messages,
        model=settings.groq_performance_model,
        schema_cls=PerformanceResult,
        temperature=settings.groq_temperature,
        max_tokens=360,
    )

    if result is None:
        log.warning("Performance Agent: Groq request failed or unconfigured; activating fallback")
        errors.append("performance: Groq unavailable; fell back to baseline k6 plan")
        result = _fallback_result(profile, target_users)

    # Enforcement: metrics must remain null until real execution occurs
    result.execution_status = "not_started"
    result.metrics = None

    log.info(
        "Performance Agent completed: endpoints=%d, scenario=%s, vus=%d",
        len(result.endpoints),
        result.test_plan.test_type,
        result.test_plan.virtual_users,
    )

    return {**state, "performance_result": result, "errors": errors}
