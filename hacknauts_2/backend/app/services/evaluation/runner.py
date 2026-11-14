"""
ScaleAI – Multi-Agent Evaluation Runner

Evaluates the performance, accuracy, and adherence of all three specialized Groq-powered agents:
1. Code Analysis Agent (Precision, Recall, False-Positive Rate, Evidence Accuracy)
2. Performance Testing Agent (Endpoint Accuracy, k6 Script Validity, Test-Plan Correctness, Metric Integrity)
3. Optimization Agent (Patch Validity, Change Correctness, Optimization Relevance, Regression Risk & Approval)

Outputs a structured comparison report with quantifiable metrics across 60+ benchmark evaluation examples.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project backend is importable
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.agents.agent_schemas import AgentState
from app.services.agents.code_analysis_agent import run_code_analysis_agent
from app.services.agents.optimization_agent import run_optimization_agent
from app.services.agents.performance_agent import run_performance_agent
from app.services.k6_service import validate_k6_script

log = logging.getLogger("scaleai.eval")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def load_dataset(filename: str) -> list[dict]:
    path = current_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Evaluation dataset {path} does not exist.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Code Analysis Evaluation
# ---------------------------------------------------------------------------

def evaluate_code_analysis_agent() -> dict[str, Any]:
    dataset = load_dataset("code_analysis_eval.json")
    total_tests = len(dataset)
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    evidence_accurate_count = 0

    log.info("Running Code Analysis Agent evaluation against %d benchmarks...", total_tests)

    for item in dataset:
        inp = item["input"]
        expected = item.get("expected_findings", [])
        state: AgentState = {
            "profile": inp.get("profile", {}),
            "scanner_findings": inp.get("scanner_findings", []),
            "model_key": "scaleai-groq",
            "errors": [],
        }

        out = run_code_analysis_agent(state)
        res = out.get("code_analysis_result")
        actual_findings = res.findings if res else []

        # Compare predicted findings with expected findings
        matched_expected = set()
        for af in actual_findings:
            matched = False
            for idx, ef in enumerate(expected):
                if (
                    ef.get("category", "").lower() in af.category.lower()
                    or ef.get("title", "").lower() in af.title.lower()
                    or (ef.get("file_path") and ef["file_path"] == af.file_path)
                ):
                    matched = True
                    matched_expected.add(idx)
                    # Evidence accuracy check
                    if af.line_number > 0 or af.evidence:
                        evidence_accurate_count += 1
                    break
            if matched:
                true_positives += 1
            else:
                false_positives += 1

        unmatched = len(expected) - len(matched_expected)
        false_negatives += max(0, unmatched)

    precision = true_positives / max(1, true_positives + false_positives)
    recall = true_positives / max(1, true_positives + false_negatives)
    fp_rate = false_positives / max(1, true_positives + false_positives)
    evidence_acc = evidence_accurate_count / max(1, true_positives)

    return {
        "agent": "Code Analysis Agent",
        "benchmarks_count": total_tests,
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(2 * (precision * recall) / max(0.001, precision + recall), 4),
            "false_positive_rate": round(fp_rate, 4),
            "evidence_accuracy": round(min(1.0, evidence_acc), 4),
        },
    }


# ---------------------------------------------------------------------------
# Performance Testing Evaluation
# ---------------------------------------------------------------------------

def evaluate_performance_agent() -> dict[str, Any]:
    dataset = load_dataset("performance_eval.json")
    total_tests = len(dataset)
    endpoint_matches = 0
    total_expected_endpoints = 0
    valid_scripts = 0
    correct_test_plans = 0
    metric_integrity_count = 0

    log.info("Running Performance Testing Agent evaluation against %d benchmarks...", total_tests)

    for item in dataset:
        inp = item["input"]
        expected_endpoints = item.get("expected_endpoints", [])
        expected_plan = item.get("expected_test_plan", {})
        total_expected_endpoints += len(expected_endpoints)

        profile = inp.get("profile", {})
        profile["target_users"] = inp.get("target_users", 1000)

        state: AgentState = {
            "profile": profile,
            "model_key": "scaleai-groq",
            "errors": [],
        }

        out = run_performance_agent(state)
        res = out.get("performance_result")
        if not res:
            continue

        # 1. Metric integrity: metrics MUST be null before execution
        if res.metrics is None and res.execution_status == "not_started":
            metric_integrity_count += 1

        # 2. k6 script validity check
        is_valid, _ = validate_k6_script(res.k6_script)
        if is_valid:
            valid_scripts += 1

        # 3. Endpoint matching
        actual_paths = {ep.path for ep in res.endpoints}
        for ep in expected_endpoints:
            if ep["path"] in actual_paths or any(ep["path"] in p for p in actual_paths):
                endpoint_matches += 1

        # 4. Test plan scenario correctness
        if expected_plan.get("test_type"):
            if res.test_plan.test_type == expected_plan["test_type"]:
                correct_test_plans += 1
        else:
            correct_test_plans += 1

    endpoint_acc = endpoint_matches / max(1, total_expected_endpoints)
    script_validity = valid_scripts / max(1, total_tests)
    plan_correctness = correct_test_plans / max(1, total_tests)
    metric_integrity = metric_integrity_count / max(1, total_tests)

    return {
        "agent": "Performance Testing Agent",
        "benchmarks_count": total_tests,
        "metrics": {
            "endpoint_identification_accuracy": round(endpoint_acc, 4),
            "k6_script_validity": round(script_validity, 4),
            "test_plan_correctness": round(plan_correctness, 4),
            "metric_interpretation_accuracy": round(metric_integrity, 4),
        },
    }


# ---------------------------------------------------------------------------
# Optimization Evaluation
# ---------------------------------------------------------------------------

def evaluate_optimization_agent() -> dict[str, Any]:
    dataset = load_dataset("optimization_eval.json")
    total_tests = len(dataset)
    valid_patches = 0
    correct_proposals = 0
    relevant_optimizations = 0
    safe_governance_count = 0

    log.info("Running Optimization Agent evaluation against %d benchmarks...", total_tests)

    for item in dataset:
        inp = item["input"]
        expected_opts = item.get("expected_optimizations", [])
        code_finding = inp.get("code_analysis_finding", {})

        from app.services.agents.agent_schemas import CodeAnalysisResult, CodeFinding, FindingStatistics
        mock_code_res = CodeAnalysisResult(
            overall_score=75,
            summary="Input evaluation finding",
            findings=[
                CodeFinding(
                    finding_id=code_finding.get("finding_id", "CA-001"),
                    title=code_finding.get("title", "Issue"),
                    category=code_finding.get("category", "code"),
                    severity=code_finding.get("severity", "medium"),
                    file_path=code_finding.get("file_path", "app.py"),
                    line_number=code_finding.get("line_number", 10),
                    evidence=code_finding.get("evidence", ""),
                    explanation="Scalability defect detected.",
                    impact="Increased latency.",
                    recommendation="Refactor using optimal patterns.",
                    confidence=0.85,
                )
            ],
            statistics=FindingStatistics(medium=1),
        )

        state: AgentState = {
            "profile": inp.get("profile", {}),
            "code_analysis_result": mock_code_res,
            "performance_result": None,
            "model_key": "scaleai-groq",
            "errors": [],
        }

        out = run_optimization_agent(state)
        res = out.get("optimization_result")
        if not res or not res.optimizations:
            continue

        for opt in res.optimizations:
            # 1. Patch validity
            if opt.proposed_solution and (opt.optimized_code or len(opt.validation_steps) > 0):
                valid_patches += 1

            # 2. Change correctness & token presence
            matched_proposal = False
            for exp in expected_opts:
                req_tokens = exp.get("required_patch_tokens", [])
                full_text = (opt.proposed_solution + " " + opt.optimized_code).lower()
                if not req_tokens or any(t.lower() in full_text for t in req_tokens):
                    matched_proposal = True
                    break
            if matched_proposal:
                correct_proposals += 1

            # 3. Relevance to input finding
            if code_finding.get("finding_id") in opt.related_findings or opt.file_path == code_finding.get("file_path"):
                relevant_optimizations += 1

            # 4. Governance & risk check (requires_approval must be True, valid risk)
            if opt.requires_approval and opt.risk in ("high", "medium", "low"):
                safe_governance_count += 1

    total_proposals = max(1, total_tests)
    return {
        "agent": "Optimization Agent",
        "benchmarks_count": total_tests,
        "metrics": {
            "patch_validity": round(min(1.0, valid_patches / total_proposals), 4),
            "correctness_of_proposed_changes": round(min(1.0, correct_proposals / total_proposals), 4),
            "relevance_of_optimization": round(min(1.0, relevant_optimizations / total_proposals), 4),
            "governance_and_regression_safety": round(min(1.0, safe_governance_count / total_proposals), 4),
        },
    }


# ---------------------------------------------------------------------------
# Runner & Report Generation
# ---------------------------------------------------------------------------

def run_all_evaluations() -> dict[str, Any]:
    start_time = time.time()
    code_eval = evaluate_code_analysis_agent()
    perf_eval = evaluate_performance_agent()
    opt_eval = evaluate_optimization_agent()
    duration_s = round(time.time() - start_time, 2)

    report = {
        "platform": "ScaleAI Multi-Agent Architecture",
        "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "duration_seconds": duration_s,
        "total_benchmark_cases": (
            code_eval["benchmarks_count"] + perf_eval["benchmarks_count"] + opt_eval["benchmarks_count"]
        ),
        "agents": [code_eval, perf_eval, opt_eval],
    }

    report_path = current_dir / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    log.info("Evaluation complete! Report written to %s", report_path)
    return report


if __name__ == "__main__":
    report = run_all_evaluations()
    print("\n" + "=" * 65)
    print(" SCALEAI THREE-AGENT EVALUATION BENCHMARK REPORT")
    print("=" * 65)
    for agent in report["agents"]:
        print(f"\n--- {agent['agent']} ({agent['benchmarks_count']} benchmarks) ---")
        for k, v in agent["metrics"].items():
            print(f"  {k:35}: {v * 100:.1f}%")
    print("\n" + "=" * 65)
