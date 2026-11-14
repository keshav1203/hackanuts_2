from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from git import GitCommandError, Repo

from ..config import settings
from ..errors import AnalysisError

_URL = re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def normalize_repo_url(raw: str) -> tuple[str, str]:
    """Return (clone_url, 'owner/name') for a public GitHub repo URL, or raise AnalysisError."""
    m = _URL.match(raw.strip())
    if not m or not m.group(1).strip(".") or not m.group(2).strip("."):
        raise AnalysisError("Enter a GitHub repository link, like https://github.com/owner/repo.")
    owner, name = m.groups()
    return f"https://github.com/{owner}/{name}", f"{owner}/{name}"


def _check_size(full_name: str) -> None:
    """Ask GitHub for the repo size before cloning. If GitHub can't be reached or rate-limits us, skip the check."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{full_name}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "scalepilot-ai"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            size_kb = json.load(resp).get("size", 0)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise AnalysisError("Repository not found. It may be private or the link may be wrong.")
        return
    except Exception:
        return
    if size_kb > settings.max_repo_mb * 1024:
        raise AnalysisError(f"Repository is larger than the {settings.max_repo_mb} MB limit.")


def clone_repo(url: str, full_name: str, workdir: str) -> Path:
    _check_size(full_name)
    dest = Path(workdir) / "repo"
    try:
        Repo.clone_from(
            url, dest, depth=1, single_branch=True, multi_options=["--no-tags"],
            env={"GIT_TERMINAL_PROMPT": "0"}, kill_after_timeout=settings.clone_timeout_s,
        )
    except GitCommandError:
        raise AnalysisError("Could not clone the repository. Check that it is public and the link is correct.")
    return dest
