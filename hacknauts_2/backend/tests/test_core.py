import os
import pytest

from app.errors import AnalysisError
from app.services.detect import detect_stack
from app.services.fsutil import load_repo
from app.services.git_ops import normalize_repo_url


def test_url_normalization():
    assert normalize_repo_url("http://www.github.com/a/b.git/") == ("https://github.com/a/b", "a/b")
    for bad in ["https://evil.com/a/b", "https://github.com/a", "https://github.com/../x", "-oProxy=x"]:
        with pytest.raises(AnalysisError):
            normalize_repo_url(bad)


def test_detect_and_skip_symlinks(tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi\nredis\npsycopg\n")
    (tmp_path / "Dockerfile").write_text("FROM python")
    (tmp_path / "app.py").write_text('@app.get("/users")\ndef users(): ...\n')
    os.symlink("/etc/passwd", tmp_path / "leak.py")
    rf = load_repo(tmp_path)
    p = detect_stack(rf)
    assert [s.rel for s in rf.sources] == ["app.py"]
    assert p.frameworks == ["FastAPI"] and p.cache == ["redis"] and p.endpoint_count == 1
    assert p.has_container_config
