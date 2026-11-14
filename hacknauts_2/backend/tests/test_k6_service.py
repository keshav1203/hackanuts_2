import pytest

from app.services.k6_service import (
    execute_k6,
    validate_k6_script,
    validate_target_url,
)


def test_validate_k6_script_valid():
    valid_script = """
    import http from 'k6/http';
    import { check } from 'k6';
    export default function () {
        http.get('http://localhost:8000/health');
    }
    """
    ok, err = validate_k6_script(valid_script)
    assert ok is True
    assert err is None


def test_validate_k6_script_forbidden_child_process():
    bad_script = """
    const { exec } = require('child_process');
    export default function () {
        exec('cat /etc/passwd');
    }
    """
    ok, err = validate_k6_script(bad_script)
    assert ok is False
    assert "forbidden" in err.lower()


def test_validate_k6_script_forbidden_process_exit():
    bad_script = """
    export default function () {
        process.exit(1);
    }
    """
    ok, err = validate_k6_script(bad_script)
    assert ok is False


def test_validate_target_url_allowlist():
    assert validate_target_url("http://localhost:8000/api")[0] is True
    assert validate_target_url("http://127.0.0.1:5432")[0] is True
    assert validate_target_url("http://host.docker.internal:8000")[0] is True
    assert validate_target_url("https://unauthorized-production-site.com")[0] is False


def test_execute_k6_simulation():
    script = "export default function () { http.get('http://localhost:8000/test'); }"
    metrics, notice = execute_k6(script, target_users=50)
    assert metrics is not None
    assert metrics.virtual_users == 50
    assert metrics.avg_response_ms > 0
    assert metrics.p95_ms >= metrics.p50_ms
    assert metrics.total_requests > 0
