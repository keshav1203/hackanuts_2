from __future__ import annotations

import logging
import tempfile

from .db import SessionLocal
from .errors import AnalysisError
from .models import Report, now
from .services.ai_agent import run_ai_agent
from .services.detect import detect_stack
from .services.fsutil import load_repo
from .services.git_ops import clone_repo
from .services.k6_service import execute_performance_load_test, execute_k6
from .services.scanner import scan_repository

log = logging.getLogger(__name__)


def run_pipeline(report_id: int) -> None:
    with SessionLocal() as db:
        report = db.get(Report, report_id)
        if report is None:
            return
        repo = report.repository

        def stage(text: str) -> None:
            report.stage = text
            db.commit()

        try:
            report.status = "running"
            stage("Cloning repository")
            with tempfile.TemporaryDirectory(prefix="scaleai-") as tmp:
                path = clone_repo(repo.url, repo.full_name, tmp)

                stage("Detecting language and framework")
                rf = load_repo(path)
                if not rf.sources:
                    raise AnalysisError("No supported source files found in this repository.")
                profile = detect_stack(rf)
                repo.language = profile.primary_language
                repo.framework = ", ".join(profile.frameworks[:2]) or None

                stage("Scanning code, queries and architecture")
                findings = scan_repository(rf, profile)

            # Build the profile dict and inject target_users so agents can use it
            profile_dict = profile.to_dict()
            profile_dict["target_users"] = report.target_users

            # run_ai_agent runs all three agents sequentially via LangGraph
            result = run_ai_agent(profile_dict, findings, report.model, stage_callback=stage)

            arch = profile_dict.copy()
            arch["finding_counts"] = {
                s: sum(1 for f in result["findings"] if f.get("severity", "").lower() in (s.lower(), s))
                for s in ("High", "Medium", "Low")
            }

            report.architecture = arch
            # Legacy fields (backward compat with existing frontend)
            report.findings = result["findings"]
            report.summary = result["summary"]
            report.ai_used = result["ai_used"]
            # New agent result fields
            report.code_analysis = result.get("code_analysis")
            report.performance_analysis = result.get("performance")
            report.optimization = result.get("optimization")
            report.agent_errors = result.get("agent_errors") or []
            report.load_test = result.get("load_test")

            # Try to run real k6 load test when the k6 binary is available; fall back to the simulated performance test otherwise.
            if not report.load_test and report.performance_analysis:
                perf = report.performance_analysis
                script = perf.get("k6_script") or ""
                # First attempt real execution via k6 CLI
                metrics_real, notice_real = execute_k6(
                    script=script,
                    base_url="http://localhost:8000",
                    target_users=report.target_users,
                )
                if metrics_real:
                    report.load_test = {
                        "executed_at": now().isoformat(),
                        "notice": notice_real,
                        "metrics": metrics_real.model_dump(),
                        "curve": [],
                    }
                    perf["execution_status"] = "completed"
                    perf["metrics"] = metrics_real.model_dump()
                    report.performance_analysis = perf
                else:
                    # Fallback to empirical simulation when k6 is not present
                    metrics, curve, notice = execute_performance_load_test(
                        script=script,
                        target_users=report.target_users,
                        base_url="http://localhost:8000",
                    )
                    if metrics:
                        report.load_test = {
                            "executed_at": now().isoformat(),
                            "notice": notice,
                            "metrics": metrics.model_dump(),
                            "curve": curve,
                        }
                        perf["execution_status"] = "completed"
                        perf["metrics"] = metrics.model_dump()
                        report.performance_analysis = perf

            report.status, report.stage = "done", "Done"
        except AnalysisError as e:
            report.status, report.error = "failed", str(e)
        except Exception:
            log.exception("Analysis %s failed", report_id)
            report.status, report.error = "failed", "The analysis failed unexpectedly. Try again in a moment."
        finally:
            report.finished_at = now()
            db.commit()
