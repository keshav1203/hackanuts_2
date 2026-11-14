# ScaleAI

An AI-powered software testing, scalability analysis, optimization, and monitoring platform. Powered by three specialized, coordinated AI agents running on the Groq API orchestrated via LangGraph.

```
scaleai/
├── backend/
│   ├── app/
│   │   ├── routers/        FastAPI routers (auth, analyses)
│   │   ├── services/
│   │   │   ├── agents/     Specialized AI Agents (Code Analysis, Performance, Optimization)
│   │   │   ├── evaluation/ Evaluation benchmark framework (60+ cases + runner)
│   │   │   ├── groq_client.py Centralized Groq SDK client with JSON schema & fallbacks
│   │   │   ├── k6_service.py  Controlled k6 sandbox execution service
│   │   │   ├── scanner.py     Tree-Sitter + Semgrep deterministic scanner
│   │   │   ├── detect.py      Multi-language & framework stack detector
│   │   │   └── ai_agent.py    LangGraph multi-agent orchestration
│   │   ├── models.py       SQLAlchemy ORM models
│   │   ├── schemas.py      Pydantic validation schemas
│   │   ├── pipeline.py     Celery background pipeline
│   │   └── config.py       Centralized settings & model configuration
│   └── tests/              Comprehensive unit & integration test suite
├── frontend/               React 18 + Vite + Tailwind + Framer Motion dashboard
├── infra/                  Prometheus & container configurations
├── docker-compose.yml
├── .env.example
└── Makefile
```

## Three Specialized Groq AI Agents

1. **Agent 1: Code Analysis Agent** (`code_analysis_agent.py`)
   - Inputs: AST scanner findings, repo profile, sanitized code snippets.
   - Enriches deterministic findings with root causes, scalability impact, line-accurate evidence, and fix recommendations.
   - Computes overall scalability health score (0-100) and issue breakdown statistics.

2. **Agent 2: Performance Testing Agent** (`performance_agent.py`)
   - Inputs: Architecture profile, detected endpoints, target concurrent virtual users.
   - Recommends traffic scenarios (smoke, load, stress, spike, soak).
   - Generates production-ready k6 JavaScript scripts with checks and latency thresholds.
   - Keeps execution metrics null until actually executed through the controlled k6 execution service.

3. **Agent 3: Optimization Agent** (`optimization_agent.py`)
   - Correlates findings from Code Analysis and Performance Testing.
   - Synthesizes root causes and generates minimal, safe code patches.
   - Enforces developer governance (`requires_approval: true`) — never blindly overwrites user code.

## Evaluation Framework

Located in `backend/app/services/evaluation/`:
- `code_analysis_eval.json`: 20 benchmark test cases (precision, recall, false-positive rate, evidence accuracy).
- `performance_eval.json`: 20 benchmark test cases (endpoint identification accuracy, k6 script validity, test plan correctness, metric integrity).
- `optimization_eval.json`: 20 benchmark test cases (patch validity, change correctness, optimization relevance, regression risk).
- Run benchmarks:
  ```bash
  python backend/app/services/evaluation/runner.py
  ```

## Quick Start

```bash
cp .env.example .env     # set GROQ_API_KEY (from console.groq.com)
make up                  # or: docker compose up --build
```
- App: http://localhost:5173 (demo login `demo@scalepilot.ai` / `demo1234`)
- API docs: http://localhost:8000/docs
- Groq Healthcheck: http://localhost:8000/health/groq
- Prometheus: http://localhost:9090

## Running Tests

- Backend tests:
  ```bash
  PYTHONPATH=backend pytest backend/tests
  ```
- Frontend build:
  ```bash
  cd frontend && npm run build
  ```
