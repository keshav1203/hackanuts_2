from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

import tree_sitter_javascript as tsjs
import tree_sitter_python as tspy
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from ..config import settings
from .detect import StackProfile
from .fsutil import SKIP_DIRS, RepoFiles, SourceFile

log = logging.getLogger(__name__)
SEV_ORDER = {"High": 0, "Medium": 1, "Low": 2}
RULES_FILE = Path(__file__).resolve().parent.parent / "rules" / "scalability.yml"

# kind -> (area, severity, title, why it hurts under load)
RULES = {
    "n_plus_one": ("Database", "High", "Database query inside a loop",
                   "Each iteration sends its own query, so round trips grow with the data and every request gets slower."),
    "blocking_in_async": ("Code", "High", "Blocking call inside async code",
                          "A blocking call freezes the event loop, so one slow request stalls every other request on that worker."),
    "blocking_sync_call": ("Code", "Medium", "Synchronous blocking call",
                           "Synchronous I/O or sleeping holds a worker thread, which caps how many requests run at once."),
    "sequential_await": ("Code", "Medium", "Awaiting inside a loop runs calls one at a time",
                         "Independent async calls run in sequence, so their latencies add up instead of overlapping."),
    "http_in_loop": ("Code", "Medium", "HTTP requests inside a loop",
                     "Each iteration waits on a network call, so response time grows with the number of items."),
    "nested_loop": ("Code", "Low", "Nested loops",
                    "Work grows with the product of the loop sizes, which gets slow as inputs grow."),
    "no_cache": ("Code", "Medium", "Read endpoint without caching",
                 "Identical reads hit the database every time, so traffic spikes turn directly into database load."),
    "unbounded_query": ("Database", "Medium", "Query returns every row",
                        "Fetching all rows makes memory use and response time grow with table size."),
    "select_star": ("Database", "Low", "SELECT * fetches unneeded columns",
                    "Reading every column moves extra data and blocks index-only scans."),
    "leading_wildcard_like": ("Database", "Medium", "LIKE with a leading wildcard",
                              "A pattern that starts with % cannot use a normal index, so the database scans the whole table."),
    "dynamic_sql": ("Database", "High", "SQL built from strings",
                    "Building SQL from strings stops the database reusing query plans and risks SQL injection."),
    "no_cache_layer": ("Infrastructure", "Medium", "No caching layer detected",
                       "The app serves endpoints backed by a database but no cache library is declared, so every read reaches the database."),
    "no_job_queue": ("Infrastructure", "Low", "Heavy work runs inside requests",
                     "Blocking or slow work happens during requests and no background job queue is declared."),
    "no_container_config": ("Infrastructure", "Low", "No container or deploy configuration found",
                            "Without a Dockerfile or compose file the app is harder to replicate across instances for scaling."),
}

# ---------------------------------------------------------------- helpers
_PARSERS: dict[str, Parser] = {}


def _parser(lang: str, ext: str) -> Parser:
    key = "tsx" if ext == ".tsx" else lang
    if key not in _PARSERS:
        if lang == "Python":
            language = Language(tspy.language())
        elif lang == "JavaScript":
            language = Language(tsjs.language())
        elif key == "tsx":
            language = Language(tsts.language_tsx())
        else:
            language = Language(tsts.language_typescript())
        _PARSERS[key] = Parser(language)
    return _PARSERS[key]


def _ctx(lines: list[str], line: int, radius: int = 5) -> str:
    return "\n".join(lines[max(0, line - 1 - radius): line + radius])[:1500]


def _mk(kind: str, rel: str, line: int, lines: list[str], source: str, severity: str | None = None) -> dict:
    area, sev, title, why = RULES[kind]
    snippet = lines[line - 1].strip()[:200] if lines and 0 < line <= len(lines) else ""
    return {
        "id": "", "kind": kind, "area": area, "severity": severity or sev, "title": title, "why": why,
        "file": rel, "line": line, "snippet": snippet, "context": _ctx(lines, line) if line else "",
        "source": source, "explanation": "", "fix_code": "", "ai_generated": False,
    }


def _txt(n) -> str:
    return n.text.decode("utf8", "ignore") if n is not None else ""


# ---------------------------------------------------------------- Python (tree-sitter)
PY_LOOPS = {"for_statement", "while_statement"}
PY_DB_METHODS = {"execute", "executemany", "query", "filter", "filter_by", "get", "first", "all", "one", "scalar",
                 "scalars", "fetchone", "fetchall", "find", "find_one", "aggregate", "count", "raw", "select"}
PY_DB_RECV = re.compile(r"(?:^|\.)(db|session|sess|conn|connection|cursor|cur|engine|objects|collection)(?:\.|\(|$)")
PY_BLOCKING = re.compile(r"^(time\.sleep|requests\.(get|post|put|patch|delete|head|request)|"
                         r"urllib\.request\.urlopen|subprocess\.(run|call|check_output|check_call)|os\.system)$")
PY_ROUTE_DEC = re.compile(r"@\s*[\w.]+\.(get|post|put|delete|patch|route)\s*\(", re.I)
CACHE_DEC = re.compile(r"cache|cached|lru_cache|memoize", re.I)


def _py_callee(node) -> tuple[str, str, str]:
    fn = node.child_by_field_name("function")
    if fn is None:
        return "", "", ""
    if fn.type == "attribute":
        return _txt(fn.child_by_field_name("object")), _txt(fn.child_by_field_name("attribute")), _txt(fn)
    return "", _txt(fn), _txt(fn)


def _walk_py(node, ctx: dict, out: list, rel: str, lines: list[str]) -> None:
    t = node.type
    route = None
    if t == "function_definition":
        is_async = any(c.type == "async" for c in node.children)
        if node.parent is not None and node.parent.type == "decorated_definition":
            dec = " ".join(_txt(c) for c in node.parent.children if c.type == "decorator")
            m = PY_ROUTE_DEC.search(dec)
            if m:
                g = m.group(1).lower()
                is_get = g == "get" or (g == "route" and not re.search(r"methods\s*=", dec, re.I))
                route = {"get": is_get, "cached": bool(CACHE_DEC.search(dec)), "db": False, "line": node.start_point[0] + 1}
        ctx = dict(ctx, loop=0, is_async=is_async, route=route or ctx["route"])
    elif t in PY_LOOPS:
        depth = ctx["loop"] + 1
        if depth >= 2:
            out.append(_mk("nested_loop", rel, node.start_point[0] + 1, lines, "treesitter",
                           "Medium" if depth >= 3 else "Low"))
        ctx = dict(ctx, loop=depth)
    elif t == "call":
        obj, attr, full = _py_callee(node)
        is_db = attr in PY_DB_METHODS and bool(PY_DB_RECV.search(obj))
        line = node.start_point[0] + 1
        if is_db:
            if ctx["route"] is not None:
                ctx["route"]["db"] = True
            if ctx["loop"] > 0:
                out.append(_mk("n_plus_one", rel, line, lines, "treesitter"))
            if attr == "all" and re.search(r"query\(|\.objects\b|^objects|select\(", obj) \
                    and not re.search(r"limit|paginate", obj, re.I):
                out.append(_mk("unbounded_query", rel, line, lines, "treesitter"))
        if PY_BLOCKING.match(full):
            if ctx["is_async"]:
                out.append(_mk("blocking_in_async", rel, line, lines, "treesitter"))
            elif ctx["loop"] > 0 and full.startswith("requests."):
                out.append(_mk("http_in_loop", rel, line, lines, "treesitter"))
            elif ctx["route"] is not None and full.startswith(("time.sleep", "subprocess", "os.system")):
                out.append(_mk("blocking_sync_call", rel, line, lines, "treesitter"))

    iterable = node.child_by_field_name("right") if t == "for_statement" else None
    for child in node.children:
        child_ctx = {**ctx, "loop": ctx["loop"] - 1} if (iterable is not None and child == iterable) else ctx
        _walk_py(child, child_ctx, out, rel, lines)

    if route and route["db"] and route["get"] and not route["cached"]:
        out.append(_mk("no_cache", rel, route["line"], lines, "treesitter"))


# ---------------------------------------------------------------- JS / TS (tree-sitter)
JS_LOOPS = {"for_statement", "for_in_statement", "while_statement", "do_statement"}
JS_FUNCS = {"function_declaration", "function_expression", "function", "arrow_function", "method_definition",
            "generator_function_declaration"}
JS_STRONG_DB = {"findOne", "findMany", "findUnique", "findAll", "findById", "findByPk", "countDocuments",
                "insertOne", "updateOne", "deleteOne", "findOneAndUpdate"}
JS_WEAK_DB = {"query", "execute", "raw", "find", "count", "aggregate", "get", "save", "create", "update", "delete"}
JS_DB_RECV = re.compile(r"(?i)\b(db|prisma|pool|knex|sequelize|mongoose|connection|conn|collection|repo|repository|manager)\b")
JS_SYNC = re.compile(r"(readFileSync|writeFileSync|appendFileSync|readdirSync|statSync|existsSync|execSync|spawnSync|"
                     r"pbkdf2Sync|scryptSync|hashSync|compareSync|randomBytesSync)$")
JS_DB_TEXT = re.compile(r"\.(findOne|findMany|findUnique|findAll|findById|findByPk|countDocuments|query|execute|aggregate)\s*\(|"
                        r"\b(db|prisma|pool|knex)\.\w+")


def _js_callee(node) -> tuple[str, str]:
    fn = node.child_by_field_name("function")
    if fn is None:
        return "", ""
    if fn.type == "member_expression":
        return _txt(fn.child_by_field_name("object")), _txt(fn.child_by_field_name("property"))
    return "", _txt(fn)


def _js_is_db(obj: str, prop: str) -> bool:
    return prop in JS_STRONG_DB or (prop in JS_WEAK_DB and bool(JS_DB_RECV.search(obj)))


def _walk_js(node, ctx: dict, out: list, rel: str, lines: list[str]) -> None:
    t = node.type
    line = node.start_point[0] + 1
    if t in JS_FUNCS:
        ctx = dict(ctx, loop=0, fn=ctx["fn"] + 1)
    elif t in JS_LOOPS:
        depth = ctx["loop"] + 1
        if depth >= 2:
            out.append(_mk("nested_loop", rel, line, lines, "treesitter", "Medium" if depth >= 3 else "Low"))
        ctx = dict(ctx, loop=depth)
    elif t == "await_expression" and ctx["loop"] > 0:
        inner = next((c for c in node.children if c.type == "call_expression"), None)
        if inner is not None:
            obj, prop = _js_callee(inner)
            out.append(_mk("n_plus_one" if _js_is_db(obj, prop) else "sequential_await", rel, line, lines, "treesitter"))
    elif t == "call_expression":
        obj, prop = _js_callee(node)
        if ctx["fn"] > 0 and JS_SYNC.search(prop):
            out.append(_mk("blocking_sync_call", rel, line, lines, "treesitter", "High" if ctx["loop"] > 0 else None))
        if prop == "get" and re.search(r"(?i)(app|router|server)$", obj):
            args = _txt(node.child_by_field_name("arguments"))
            if re.match(r"\(\s*['\"`]/", args) and JS_DB_TEXT.search(args) and not re.search("cache", args, re.I):
                out.append(_mk("no_cache", rel, line, lines, "treesitter"))

    right = node.child_by_field_name("right") if t == "for_in_statement" else None
    for child in node.children:
        child_ctx = {**ctx, "loop": ctx["loop"] - 1} if (right is not None and child == right) else ctx
        _walk_js(child, child_ctx, out, rel, lines)


def _analyze_ast(sf: SourceFile, lines: list[str]) -> list[dict]:
    out: list[dict] = []
    try:
        tree = _parser(sf.lang, sf.ext).parse(sf.text.encode("utf8", "ignore"))
        if sf.lang == "Python":
            _walk_py(tree.root_node, {"loop": 0, "is_async": False, "route": None}, out, sf.rel, lines)
        else:
            _walk_js(tree.root_node, {"loop": 0, "fn": 0}, out, sf.rel, lines)
    except RecursionError:
        log.warning("Skipped deeply nested file %s", sf.rel)
    except Exception:
        log.exception("AST analysis failed for %s", sf.rel)
    return out


# ---------------------------------------------------------------- text rules (all languages)
SQL_KW = re.compile(r"(?i)\b(select\b.+\bfrom\b|insert\s+into\b|update\s+\w+\s+set\b|delete\s+from\b)")
DYN = re.compile(r"""(\bf['"]|['"]\s*\+\s*[A-Za-z_(]|[A-Za-z_)\]]\s*\+\s*['"]|\$\{|\.format\()""")
SELECT_STAR = re.compile(r"(?i)\bselect\s+\*\s+from\b")
LIKE_WILD = re.compile(r"(?i)\bi?like\s+['\"]%")


def _scan_text(sf: SourceFile, lines: list[str]) -> list[dict]:
    out = []
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if len(s) > 400 or s.startswith(("#", "//", "*", "/*", "--")):
            continue
        if SELECT_STAR.search(s):
            out.append(_mk("select_star", sf.rel, n, lines, "pattern"))
        if LIKE_WILD.search(s):
            out.append(_mk("leading_wildcard_like", sf.rel, n, lines, "pattern"))
        if SQL_KW.search(s) and DYN.search(s):
            out.append(_mk("dynamic_sql", sf.rel, n, lines, "pattern"))
    return out


# ---------------------------------------------------------------- Semgrep
def _run_semgrep(rf: RepoFiles, texts: dict[str, list[str]]) -> list[dict]:
    if not shutil.which("semgrep"):
        log.info("semgrep not installed; skipping")
        return []
    cmd = ["semgrep", "--config", str(RULES_FILE), "--json", "--quiet", "--metrics=off", "--disable-version-check",
           "--timeout", "10"]
    for d in sorted(SKIP_DIRS):
        cmd += ["--exclude", d]
    cmd.append(str(rf.root))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                              env={**os.environ, "SEMGREP_SEND_METRICS": "off"})
        data = json.loads(proc.stdout or "{}")
    except Exception:
        log.exception("semgrep failed")
        return []
    out = []
    for r in data.get("results", []):
        kind = (r.get("extra", {}).get("metadata") or {}).get("kind")
        if kind not in RULES:
            continue
        rel = os.path.relpath(r["path"], rf.root).replace(os.sep, "/")
        out.append(_mk(kind, rel, r["start"]["line"], texts.get(rel, []), "semgrep"))
    return out


# ---------------------------------------------------------------- architecture-level findings
def _architecture_findings(profile: StackProfile, findings: list[dict]) -> list[dict]:
    out = []
    if profile.endpoint_count and profile.databases and not profile.cache:
        out.append(_mk("no_cache_layer", "", 0, [], "architecture"))
    if not profile.queues and any(f["kind"] in ("http_in_loop", "blocking_in_async", "blocking_sync_call") for f in findings):
        out.append(_mk("no_job_queue", "", 0, [], "architecture"))
    if profile.endpoint_count and not profile.has_container_config:
        out.append(_mk("no_container_config", "", 0, [], "architecture"))
    return out


def scan_repository(rf: RepoFiles, profile: StackProfile) -> list[dict]:
    texts = {sf.rel: sf.text.splitlines() for sf in rf.sources}
    found: list[dict] = []
    for sf in rf.sources:
        lines = texts[sf.rel]
        found += _scan_text(sf, lines)
        if sf.lang in ("Python", "JavaScript", "TypeScript"):
            found += _analyze_ast(sf, lines)
    found += _run_semgrep(rf, texts)
    found += _architecture_findings(profile, found)

    seen, per_file, unique = set(), {}, []
    for f in found:
        key = (f["file"], f["line"], f["kind"])
        pf = (f["file"], f["kind"])
        if key in seen or per_file.get(pf, 0) >= 8:
            continue
        seen.add(key)
        per_file[pf] = per_file.get(pf, 0) + 1
        unique.append(f)
    unique.sort(key=lambda f: (SEV_ORDER[f["severity"]], f["file"], f["line"]))
    unique = unique[: settings.max_findings]
    for i, f in enumerate(unique, 1):
        f["id"] = f"F{i}"
    return unique
