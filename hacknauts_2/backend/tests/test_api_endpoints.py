import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Report, Repository, User
from app.routers.analyses import _dispatch_analysis
from app.schemas import AnalysisIn, ReportOut


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True

    # Check /api/health alias as well
    api_res = client.get("/api/health")
    assert api_res.status_code == 200
    assert api_res.json()["ok"] is True


def test_groq_health_endpoint(client):
    res = client.get("/health/groq")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "connected" in data
    assert "model" in data

    # Check /api/health/groq alias
    res_api = client.get("/api/health/groq")
    assert res_api.status_code == 200
    assert "configured" in res_api.json()


def test_analysis_input_schema():
    # Only allowed model is scaleai-groq
    valid = AnalysisIn(repo_url="https://github.com/fastapi/fastapi", target_users=500)
    assert valid.model == "scaleai-groq"
    assert valid.target_users == 500


def test_report_out_schema_fields():
    # Verify ReportOut can serialize code_analysis, performance_analysis, and optimization
    from datetime import datetime, timezone

    sample = {
        "id": 1,
        "status": "done",
        "stage": "Done",
        "error": None,
        "model": "scaleai-groq",
        "target_users": 1000,
        "repo_url": "https://github.com/owner/repo",
        "repo_name": "owner/repo",
        "language": "Python",
        "framework": "FastAPI",
        "architecture": {"endpoint_count": 5},
        "findings": [],
        "summary": "Summary text",
        "ai_used": True,
        "code_analysis": {"overall_score": 90, "findings": []},
        "performance_analysis": {"endpoints": [], "test_plan": {"test_type": "load"}},
        "optimization": {"optimizations": []},
        "agent_errors": [],
        "load_test": None,
        "created_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
    }
    rep = ReportOut.model_validate(sample)
    assert rep.code_analysis["overall_score"] == 90
    assert rep.performance_analysis["test_plan"]["test_type"] == "load"


def test_auth_and_analyses_flow(client):
    # 1. Login with demo account
    demo_res = client.post("/api/auth/demo")
    assert demo_res.status_code == 200
    token = demo_res.json()["token"]
    assert token
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Check /api/auth/me
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert "email" in me_res.json()

    # 3. Create a mock report directly in DB to test API analysis queries
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == demo_res.json()["email"]).first()
        repo = db.query(Repository).filter(Repository.user_id == user.id, Repository.url == "https://github.com/test-org/api-test-repo").first()
        if not repo:
            repo = Repository(
                user_id=user.id,
                url="https://github.com/test-org/api-test-repo",
                full_name="test-org/api-test-repo",
                language="Python",
                framework="FastAPI",
            )
            db.add(repo)
            db.flush()
        report = Report(
            repository_id=repo.id,
            user_id=user.id,
            status="done",
            stage="Done",
            model="scaleai-groq",
            target_users=500,
            summary="All tests passed successfully.",
            findings=[
                {
                    "title": "Unindexed foreign key",
                    "area": "Database",
                    "severity": "Medium",
                    "file": "models.py",
                    "line": 42,
                    "description": "Missing index on user_id",
                }
            ],
            code_analysis={"overall_score": 88, "findings": [{"title": "Unindexed foreign key", "severity": "Medium"}]},
            performance_analysis={
                "endpoints": [{"path": "/items", "method": "GET"}],
                "k6_script": "export default function() {}",
            },
            optimization={"optimizations": [{"title": "Add index", "expected_benefit": "3x speedup"}]},
        )
        db.add(report)
        db.commit()
        report_id = report.id

    # 4. List analyses
    list_res = client.get("/api/analyses", headers=headers)
    assert list_res.status_code == 200
    analyses = list_res.json()
    assert any(a["id"] == report_id for a in analyses)

    # 5. Get individual analysis
    get_res = client.get(f"/api/analyses/{report_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["repo_name"] == "test-org/api-test-repo"

    # 6. Execute load test
    load_test_res = client.post(f"/api/analyses/{report_id}/load-test", headers=headers)
    assert load_test_res.status_code == 200
    report_data = load_test_res.json()
    assert report_data["load_test"] is not None
    assert "metrics" in report_data["load_test"]
    assert "curve" in report_data["load_test"]

    # 7. Ask about analysis
    ask_res = client.post(
        f"/api/analyses/{report_id}/ask",
        headers=headers,
        json={"query": "What optimization do you recommend?"},
    )
    assert ask_res.status_code == 200
    assert "answer" in ask_res.json()
    assert len(ask_res.json()["answer"]) > 10


def test_dispatch_analysis_resilience():
    # Calling _dispatch_analysis when Redis is offline should complete immediately without hanging
    _dispatch_analysis(999999)
