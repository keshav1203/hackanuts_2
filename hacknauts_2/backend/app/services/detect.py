from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .fsutil import RepoFiles


def W(*names: str) -> str:
    return r"(?<![\w.-])(?:" + "|".join(re.escape(n) for n in names) + r")(?![\w-])"


FRAMEWORKS = {
    "FastAPI": W("fastapi"), "Flask": W("flask"), "Django": W("django"), "Express": W("express"),
    "NestJS": W("@nestjs/core"), "Next.js": W("next"), "Fastify": W("fastify"), "Koa": W("koa"),
    "Spring Boot": r"(?<![\w.-])spring-boot", "Gin": W("gin-gonic/gin"), "Echo": W("labstack/echo"),
    "Fiber": W("gofiber/fiber"), "Rails": W("rails"), "Laravel": W("laravel/framework"),
}
DATABASES = {
    "PostgreSQL": W("psycopg", "psycopg2", "psycopg2-binary", "asyncpg", "pg", "postgresql", "lib/pq", "pgx"),
    "MySQL": W("mysqlclient", "pymysql", "mysql", "mysql2", "mysql-connector-java"),
    "MongoDB": W("pymongo", "motor", "mongodb", "mongoose"),
    "SQLite": W("sqlite3", "better-sqlite3", "aiosqlite"),
}
ORMS = {
    "SQLAlchemy": W("sqlalchemy"), "Prisma": W("@prisma/client", "prisma"), "Sequelize": W("sequelize"),
    "TypeORM": W("typeorm"), "Mongoose": W("mongoose"), "GORM": W("gorm.io/gorm", "gorm"),
    "Hibernate/JPA": r"(?<![\w.-])(?:spring-boot-starter-data-jpa|hibernate)", "ActiveRecord": W("activerecord"),
}
CACHE = W("redis", "ioredis", "django-redis", "flask-caching", "cachetools", "pymemcache", "memcached",
          "node-cache", "lru-cache", "cache-manager", "caffeine", "ristretto", "bigcache", "spring-boot-starter-cache")
QUEUES = W("celery", "rq", "dramatiq", "arq", "bull", "bullmq", "bee-queue", "kafkajs", "kafka-python",
           "aio-pika", "pika", "amqplib", "sidekiq", "spring-kafka")

PY_DECOR = re.compile(r"@\s*[\w.]+\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]*)['\"]", re.I)
PY_ROUTE = re.compile(r"@\s*[\w.]+\.route\(\s*['\"]([^'\"]*)['\"](.*)")
DJANGO = re.compile(r"\b(?:re_)?path\(\s*r?['\"]([^'\"]*)['\"]")
JS_ROUTE = re.compile(r"\b(?:app|router|server|\w+Router)\.(get|post|put|delete|patch)\(\s*['\"`]([^'\"`]*)['\"`]")
JAVA_MAP = re.compile(r"@(Get|Post|Put|Delete|Patch)Mapping\(\s*(?:value\s*=\s*)?['\"]([^'\"]*)['\"]")
GO_ROUTE = re.compile(r"\.(GET|POST|PUT|DELETE|PATCH)\(\s*['\"]([^'\"]*)['\"]")
GO_HANDLE = re.compile(r"HandleFunc\(\s*['\"]([^'\"]*)['\"]")


@dataclass
class StackProfile:
    primary_language: str | None
    languages: dict[str, float]
    frameworks: list[str]
    databases: list[str]
    orms: list[str]
    cache: list[str]
    queues: list[str]
    has_container_config: bool
    endpoints: list[dict]
    endpoint_count: int
    files_scanned: int
    truncated: bool

    def to_dict(self) -> dict:
        d = asdict(self)
        d["endpoints"] = d["endpoints"][:60]
        return d


def _match(table: dict[str, str], text: str) -> list[str]:
    return [label for label, pat in table.items() if re.search(pat, text)]


def _names(pattern: str, text: str) -> list[str]:
    return sorted({m.group(0) for m in re.finditer(pattern, text)})


def _endpoints(rf: RepoFiles) -> list[dict]:
    found: list[dict] = []

    def add(method: str, path: str, rel: str, line: int) -> None:
        found.append({"method": method.upper(), "path": path or "/", "file": rel, "line": line})

    for sf in rf.sources:
        for n, line in enumerate(sf.text.splitlines(), 1):
            if len(line) > 400:
                continue
            if sf.lang == "Python":
                if m := PY_DECOR.search(line):
                    add(m.group(1), m.group(2), sf.rel, n)
                elif m := PY_ROUTE.search(line):
                    meth = re.search(r"methods\s*=\s*[\[(]\s*['\"](\w+)", m.group(2))
                    add(meth.group(1) if meth else "GET", m.group(1), sf.rel, n)
                elif sf.rel.endswith("urls.py") and (m := DJANGO.search(line)):
                    add("ANY", m.group(1), sf.rel, n)
            elif sf.lang in ("JavaScript", "TypeScript"):
                if m := JS_ROUTE.search(line):
                    add(m.group(1), m.group(2), sf.rel, n)
            elif sf.lang in ("Java", "Kotlin"):
                if m := JAVA_MAP.search(line):
                    add(m.group(1), m.group(2), sf.rel, n)
            elif sf.lang == "Go":
                if m := GO_ROUTE.search(line):
                    add(m.group(1), m.group(2), sf.rel, n)
                elif m := GO_HANDLE.search(line):
                    add("ANY", m.group(1), sf.rel, n)
    return found


def detect_stack(rf: RepoFiles) -> StackProfile:
    deps = "\n".join(t.lower() for t in rf.manifests.values())
    total = sum(rf.lang_bytes.values()) or 1
    langs = {k: round(100 * v / total, 1) for k, v in sorted(rf.lang_bytes.items(), key=lambda kv: -kv[1])[:6]}
    frameworks = _match(FRAMEWORKS, deps)
    orms = _match(ORMS, deps)
    if "Django" in frameworks:
        orms.append("Django ORM")
    endpoints = _endpoints(rf)
    return StackProfile(
        primary_language=next(iter(langs), None),
        languages=langs,
        frameworks=frameworks,
        databases=_match(DATABASES, deps),
        orms=orms,
        cache=_names(CACHE, deps),
        queues=_names(QUEUES, deps),
        has_container_config=rf.container_config,
        endpoints=endpoints,
        endpoint_count=len(endpoints),
        files_scanned=len(rf.sources),
        truncated=rf.truncated,
    )
