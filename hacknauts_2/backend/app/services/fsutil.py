from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..config import settings

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "target", "venv", ".venv", "env", "__pycache__",
    ".next", ".nuxt", "coverage", "site-packages", ".idea", ".gradle", "bower_components", "third_party",
    "tests", "test", "__tests__",
}
EXT_LANG = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".go": "Go", ".rb": "Ruby", ".php": "PHP",
    ".cs": "C#", ".rs": "Rust", ".kt": "Kotlin",
}
MANIFESTS = {
    "pyproject.toml", "pipfile", "setup.py", "setup.cfg", "package.json", "pom.xml", "build.gradle",
    "build.gradle.kts", "go.mod", "gemfile", "composer.json", "cargo.toml",
}
COMPOSE = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}


@dataclass
class SourceFile:
    rel: str
    lang: str
    ext: str
    text: str


@dataclass
class RepoFiles:
    root: Path
    sources: list[SourceFile] = field(default_factory=list)
    manifests: dict[str, str] = field(default_factory=dict)
    container_config: bool = False
    lang_bytes: dict[str, int] = field(default_factory=dict)
    truncated: bool = False


def load_repo(root: Path) -> RepoFiles:
    """Read source files and dependency manifests. Symlinks are never followed: a cloned repo is untrusted
    and could link to files on this machine."""
    root = Path(os.path.realpath(root))
    prefix = str(root) + os.sep
    rf = RepoFiles(root=root)
    limit = settings.max_file_kb * 1024

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames if d.lower() not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d))
        )
        for fn in sorted(filenames):
            path = os.path.join(dirpath, fn)
            low = fn.lower()
            if os.path.islink(path) or not os.path.realpath(path).startswith(prefix):
                continue
            if low.startswith("dockerfile") or low in COMPOSE:
                rf.container_config = True
            ext = os.path.splitext(low)[1]
            lang = None if low.endswith(".min.js") else EXT_LANG.get(ext)
            is_manifest = low in MANIFESTS or (low.startswith("requirements") and ext == ".txt")
            if not (lang or is_manifest):
                continue
            try:
                if os.path.getsize(path) > limit:
                    continue
                with open(path, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            if b"\0" in data[:2048]:
                continue
            text = data.decode("utf-8", "ignore")
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if is_manifest:
                rf.manifests[rel] = text
            elif len(rf.sources) >= settings.max_files:
                rf.truncated = True
            else:
                rf.sources.append(SourceFile(rel, lang, ext, text))
                rf.lang_bytes[lang] = rf.lang_bytes.get(lang, 0) + len(data)
    return rf
