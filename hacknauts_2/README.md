# ScaleAI

**AI-powered repository scalability analysis, performance-test planning,
and code optimization recommendations.**

ScalePilot AI analyzes a public GitHub repository, detects its
technology stack, scans source code for scalability risks, and
coordinates three specialized AI agents to explain findings, prepare a
k6 performance-test plan, and recommend developer-reviewed
optimizations.

> **Important:** Static analysis and AI recommendations are not the same
> as measured performance. A performance plan is initially a proposal.
> Real k6 metrics are recorded only after the load-test execution
> endpoint runs successfully.

------------------------------------------------------------------------

## Contents

-   [Overview](#overview)
-   [Key capabilities](#key-capabilities)
-   [End-to-end workflow](#end-to-end-workflow)
-   [System architecture](#system-architecture)
-   [Technology stack](#technology-stack)
-   [AI agent workflow](#ai-agent-workflow)
-   [Code scanning and repository
    profiling](#code-scanning-and-repository-profiling)
-   [Performance testing with k6](#performance-testing-with-k6)
-   [Optimization and approval model](#optimization-and-approval-model)
-   [Project structure](#project-structure)
-   [Prerequisites](#prerequisites)
-   [Configuration](#configuration)
-   [Run with Docker Compose](#run-with-docker-compose)
-   [Run locally without Docker](#run-locally-without-docker)
-   [API reference](#api-reference)
-   [Database and background
    processing](#database-and-background-processing)
-   [Monitoring](#monitoring)
-   [Testing](#testing)
-   [Security and execution
    safeguards](#security-and-execution-safeguards)
-   [Troubleshooting](#troubleshooting)
-   [Current limitations and extension
    ideas](#current-limitations-and-extension-ideas)

## Overview

Software teams often discover scalability problems only after an
application begins receiving significant traffic. ScalePilot AI is
designed to help developers identify potential problems earlier by
inspecting a repository and producing an actionable scalability report.

A user signs in, submits a public GitHub repository URL, selects an AI
model, and specifies the number of concurrent users the application
should support. The backend then:

1.  Clones the repository into a temporary workspace.
2.  Detects languages, frameworks, databases, ORMs, caches, queues, and
    application endpoints.
3.  Scans supported source files for code and architecture patterns
    associated with scalability problems.
4.  Runs a coordinated three-agent AI workflow.
5.  Saves the report and exposes progress and results through the API.
6.  Allows the user to execute a generated k6 test against an authorized
    local target.
7.  Presents findings, performance information, and optimization
    recommendations in the React dashboard.

## Key capabilities

-   **Repository analysis:** Accepts public GitHub repository URLs and
    performs shallow clones.
-   **Technology detection:** Profiles the repository's languages,
    frameworks, databases, ORMs, cache technologies, queues, and routes.
-   **Static scalability scanning:** Uses Tree-sitter-based syntax
    analysis and Semgrep rules to detect selected code patterns.
-   **AI-assisted explanations:** Enriches scanner findings with root
    causes, impact, evidence, and recommendations.
-   **Performance-test planning:** Creates a k6 script, traffic
    scenario, virtual-user target, and thresholds.
-   **Controlled load-test execution:** Validates generated scripts and
    restricts target hosts before invoking k6.
-   **Optimization proposals:** Correlates code and performance findings
    and produces proposed patches for developer review.
-   **Analysis history:** Stores reports per user and makes previous
    analyses available.
-   **Interactive dashboard:** Displays analysis progress, architecture
    information, findings, and performance/optimization results.
-   **Resilient processing:** Uses Celery and Redis when available, with
    a background-thread fallback for analysis dispatch.
-   **Monitoring endpoint:** Exposes Prometheus metrics from the FastAPI
    application.

## End-to-end workflow

``` mermaid
flowchart TD
    A[User opens React dashboard] --> B[Sign up, sign in, or demo login]
    B --> C[Submit GitHub URL and target users]
    C --> D[FastAPI validates request]
    D --> E[Create report and repository records]
    E --> F{Redis available?}
    F -->|Yes| G[Queue Celery task]
    F -->|No| H[Run background thread]
    G --> I[Clone public GitHub repository]
    H --> I
    I --> J[Load and detect repository stack]
    J --> K[Tree-sitter and Semgrep scanning]
    K --> L[Code Analysis Agent]
    L --> M[Performance Testing Agent]
    M --> N[Optimization Agent]
    N --> O[Combine report and save results]
    O --> P[Dashboard displays report]
    P --> Q[Optional controlled k6 execution]
    Q --> R[Store measured metrics]
```

### Workflow details

1.  **Authentication:** The frontend calls the authentication API and
    stores the returned JWT for authenticated requests.
2.  **Analysis request:** The frontend sends the repository URL, target
    concurrent users, and selected model.
3.  **Report creation:** The backend validates and normalizes the GitHub
    URL, creates or reuses the user's repository record, and creates a
    report.
4.  **Job dispatch:** The backend checks Redis. If Redis is reachable,
    it dispatches a Celery task. If not, it starts the pipeline in a
    background thread.
5.  **Repository acquisition:** GitPython performs a shallow,
    single-branch clone into a temporary directory. The temporary
    workspace is removed after the repository scan stage.
6.  **Repository profiling:** Source files are loaded within configured
    limits. The detector identifies the project's technology profile and
    endpoints.
7.  **Static scanning:** Tree-sitter and configured Semgrep rules
    inspect source code for scalability-related patterns.
8.  **AI analysis:** LangGraph runs the Code Analysis, Performance
    Testing, and Optimization agents sequentially.
9.  **Persistence:** The report, findings, agent outputs, status, and
    timestamps are saved through SQLAlchemy.
10. **Dashboard polling:** The frontend requests report updates while
    the job is queued or running.
11. **Optional load test:** The user triggers the load-test endpoint.
    The backend validates the script and target before running k6.
12. **Results:** The measured metrics are stored separately from
    predictions and recommendations.

## System architecture

The application is divided into a React frontend, FastAPI backend,
relational database, background-job infrastructure, AI services, and
monitoring.

``` mermaid
flowchart LR
    U[Developer] --> FE[React + Vite dashboard]
    FE -->|REST API + JWT| API[FastAPI]
    API --> DB[(PostgreSQL)]
    API --> R[(Redis)]
    R --> CW[Celery worker]
    API -. fallback .-> BT[Background thread]
    CW --> PIPE[Analysis pipeline]
    BT --> PIPE
    PIPE --> GH[GitHub repository]
    PIPE --> SCAN[Stack detection + static scanning]
    SCAN --> LG[LangGraph workflow]
    LG --> CA[Code Analysis Agent]
    CA --> PA[Performance Agent]
    PA --> OA[Optimization Agent]
    CA --> GROQ[Groq API]
    PA --> GROQ
    OA --> GROQ
    PIPE --> DB
    API --> K6[k6 execution service]
    API --> PROM[Prometheus metrics]
```

### Main backend layers

  -------------------------------------------------------------------------------
  Layer                   Main files                      Responsibility
  ----------------------- ------------------------------- -----------------------
  HTTP API                `app/main.py`, `app/routers/`   FastAPI application,
                                                          CORS, authentication
                                                          and analysis endpoints

  Configuration           `app/config.py`                 Environment-based
                                                          application settings
                                                          and repository limits

  Data access             `app/db.py`, `app/models.py`    SQLAlchemy engine,
                                                          sessions and ORM models

  Validation              `app/schemas.py`                Pydantic request and
                                                          response schemas

  Authentication          `app/security.py`               Password hashing, JWT
                                                          creation and session
                                                          validation

  Pipeline                `app/pipeline.py`               Coordinates cloning,
                                                          profiling, scanning and
                                                          report persistence

  Background jobs         `app/celery_app.py`,            Celery task
                          `app/worker.py`                 configuration and
                                                          worker entry point

  Repository services     `app/services/git_ops.py`,      Clone, load, and
                          `fsutil.py`, `detect.py`        profile repositories

  Static scanning         `app/services/scanner.py`,      Syntax-aware scanning
                          `app/rules/scalability.yml`     and Semgrep rules

  AI orchestration        `app/services/ai_agent.py`,     LangGraph workflow and
                          `app/services/agents/`          specialized agents

  AI client               `app/services/groq_client.py`   Groq calls, model
                                                          resolution, structured
                                                          output handling and
                                                          resilience

  Performance testing     `app/services/k6_service.py`    Script/host validation
                                                          and k6 execution

  Frontend                `frontend/src/`                 Dashboard,
                                                          authentication context,
                                                          report views and API
                                                          client
  -------------------------------------------------------------------------------

## Technology stack

### Frontend

  Technology                Purpose
  ------------------------- -------------------------------------------------------
  React 18                  Component-based user interface
  Vite 5                    Frontend development server and production build tool
  JavaScript (ES modules)   Frontend application logic
  Tailwind CSS 3            Utility-first styling
  Framer Motion             UI transitions and animations
  React Router              Client-side routing
  Recharts                  Data visualization and report charts
  Lucide React              Interface icons
  Nginx                     Serves the built frontend in the frontend container

### Backend and API

  Technology                          Purpose
  ----------------------------------- ----------------------------------------------------
  Python                              Backend implementation language
  FastAPI                             REST API and request handling
  Uvicorn                             ASGI server
  Pydantic v2                         Request/response validation and settings
  SQLAlchemy 2                        ORM and database access
  PyJWT                               JWT-based authentication
  GitPython                           GitHub repository cloning
  Tree-sitter                         Syntax-tree parsing for supported source languages
  Semgrep                             Pattern-based static code scanning
  Prometheus FastAPI Instrumentator   API metrics instrumentation

### AI and orchestration

  Technology               Purpose
  ------------------------ -----------------------------------------------
  Groq API / Groq SDK      Runs language-model requests for the agents
  LangGraph                Defines and executes the multi-agent workflow
  Pydantic agent schemas   Structures and validates agent outputs

The three agent model settings can be configured independently. The
application also contains model-resolution and fallback handling so that
an unavailable or unconfigured Groq model does not necessarily stop the
entire analysis workflow.

### Performance and infrastructure

  -----------------------------------------------------------------------
  Technology                          Purpose
  ----------------------------------- -----------------------------------
  k6                                  Executes generated load-test
                                      scripts and collects performance
                                      metrics

  Redis 7                             Celery message broker and result
                                      backend

  Celery 5                            Runs repository analysis as
                                      background tasks

  PostgreSQL 16                       Primary relational database in
                                      Docker Compose

  SQLite                              Local fallback when the configured
                                      PostgreSQL connection cannot be
                                      established

  Docker                              Containerizes the backend and
                                      frontend

  Docker Compose                      Runs the application and supporting
                                      services

  Prometheus                          Scrapes backend metrics
  -----------------------------------------------------------------------

## AI agent workflow

The AI workflow is implemented in `backend/app/services/ai_agent.py`
using LangGraph's `StateGraph`.

The graph is sequential:

``` mermaid
flowchart TD
    S([START]) --> A[Code Analysis Agent]
    A --> B[Performance Testing Agent]
    B --> C[Optimization Agent]
    C --> D[Combined Report]
    D --> E([END])
```

Each agent receives the repository profile and relevant results from
earlier stages. Agent outputs use structured Pydantic schemas.

### Agent 1 --- Code Analysis Agent

**File:** `backend/app/services/agents/code_analysis_agent.py`

**Input:** - Detected repository profile. - Static scanner findings. -
Source-code evidence and file/line information.

**Responsibilities:** - Explain why a detected pattern may affect
scalability. - Enrich findings with root causes and impact. - Recommend
practical code-level fixes. - Produce a code-analysis summary and
overall score. - Preserve the connection between a finding and its
source file.

**Output:** Structured code-analysis findings, explanations,
recommendations, and score information.

### Agent 2 --- Performance Testing Agent

**File:** `backend/app/services/agents/performance_agent.py`

**Input:** - Repository architecture profile. - Detected application
endpoints. - Requested target concurrent users.

**Responsibilities:** - Select a suitable performance scenario such as
smoke, load, or stress. - Identify important endpoints to test. -
Generate a k6 JavaScript script. - Define thresholds such as
request-failure rate and p95 latency. - Identify possible bottlenecks
and architectural warnings.

**Output:** A performance test plan, endpoint list, k6 script,
thresholds, warnings, and predicted bottlenecks.

**Important:** The agent sets `execution_status` to `not_started` and
`metrics` to `null`. It does not pretend that generated predictions are
measured results.

### Agent 3 --- Optimization Agent

**File:** `backend/app/services/agents/optimization_agent.py`

**Input:** - Code Analysis Agent results. - Performance Testing Agent
results. - Repository profile.

**Responsibilities:** - Correlate code-level findings with performance
risks. - Prioritize high-impact optimization opportunities. - Explain
root causes and trade-offs. - Generate small proposed code changes. -
Identify validation steps and retest requirements.

**Output:** Structured optimization proposals, original and proposed
code snippets, risk, expected benefit, and validation guidance.

**Developer approval:** Every optimization is marked
`requires_approval: true`. The application presents suggestions; it does
not automatically overwrite the developer's repository.

### Combined report and failure handling

The final LangGraph node combines the agent summaries and records the
overall execution status. Agent nodes are wrapped in error boundaries.
If a Groq request fails or returns unusable data, individual agents can
use fallback results and add an error/warning to the report.

This provides a distinction between: - AI-generated analysis; -
rule-based fallback recommendations; - predicted performance risks;
and - metrics obtained from an actual k6 execution.

## Code scanning and repository profiling

### Repository cloning

**File:** `backend/app/services/git_ops.py`

The current implementation accepts GitHub HTTPS repository URLs matching
the public-repository URL format. It checks repository metadata and
enforces a configured repository-size limit when GitHub is reachable. It
then performs a shallow, single-branch clone without tags.

The clone is performed in a temporary workspace. The project does not
require the user to upload a ZIP of the source repository.

### Repository loading and technology detection

**Files:** `backend/app/services/fsutil.py`,
`backend/app/services/detect.py`

The loader applies limits to repository size, number of files, and
individual file size, and skips common irrelevant directories.

The detector inspects repository files and dependency/configuration
information to infer:

-   Primary language and language distribution.
-   Frameworks.
-   Databases.
-   ORMs.
-   Cache technologies.
-   Queue technologies.
-   Application endpoints and HTTP methods.
-   Other architecture/profile information used by the agents.

Framework and technology signatures in the detector include examples
such as FastAPI, Flask, Django, Express, NestJS, Next.js, Spring Boot,
Gin, Rails, and Laravel. The actual detected result depends on the
contents of the submitted repository.

### Tree-sitter

Tree-sitter parses source code into syntax trees. ScalePilot uses
Tree-sitter language packages for Python, JavaScript, and
TypeScript/TSX.

This makes it possible to inspect code structure rather than relying
only on simple text matching. The scanner uses syntax-aware logic for
selected patterns, including blocking operations, sequential awaits,
nested loops, and other scalability concerns.

### Semgrep

Semgrep provides configurable pattern-based scanning. Project-specific
rules are stored in:

`backend/app/rules/scalability.yml`

The included rules cover selected patterns such as:

-   Java `Thread.sleep(...)`.
-   Java repository `findAll()` calls.
-   Database calls inside loops in Java, Go, and PHP.
-   Ruby `.all.each(...)` patterns.

The scanner also contains its own rule catalog for additional code and
architecture risks. Tree-sitter and Semgrep therefore have complementary
roles: syntax-aware analysis and explicit pattern matching.

### Example categories of findings

  -----------------------------------------------------------------------
  Category                Example risk            Why it matters
  ----------------------- ----------------------- -----------------------
  Database                N+1 queries             Database round trips
                                                  increase with the
                                                  number of records

  Database                Unbounded queries       Large result sets
                                                  increase memory usage
                                                  and response time

  Code                    Blocking operations     Worker capacity can be
                                                  occupied while a
                                                  blocking operation runs

  Async code              Blocking calls in async Can stall an event loop
                          functions               

  Async code              Sequential awaits       Independent operations
                                                  do not overlap

  HTTP                    Network calls inside    Latency can grow with
                          loops                   the number of
                                                  iterations

  Infrastructure          Missing cache layer     Repeated reads may
                                                  repeatedly reach the
                                                  database

  Infrastructure          Missing job queue       Long-running work may
                                                  occupy request-handling
                                                  capacity
  -----------------------------------------------------------------------

These are indicators and recommendations, not proof that a production
system will fail. Findings should be reviewed in the context of the
application.

## Performance testing with k6

The Performance Testing Agent prepares a test plan and JavaScript
script. The backend's k6 service is responsible for validating and
executing that script.

### Test scenarios

  Scenario   Goal
  ---------- ---------------------------------------------------
  Smoke      Confirm basic availability with very low traffic
  Load       Observe behavior under expected normal traffic
  Stress     Increase traffic to explore system limits
  Spike      Evaluate response to a sudden increase in traffic
  Soak       Observe behavior under sustained traffic

The selected scenario and virtual-user count are generated based on the
repository profile and the target supplied by the user.

### Example generated k6 script

The following is an illustrative baseline, not a promise that every
repository receives this exact script:

``` javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  vus: 10,
  duration: '1m',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<500'],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/health`);
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1);
}
```

### Execution process

1.  The user opens a completed analysis report.
2.  The frontend calls `POST /api/analyses/{report_id}/load-test`.
3.  The backend loads the generated k6 script from the report.
4.  The service validates the script and rejects selected unsafe
    constructs.
5.  The service validates the target URL against its host allowlist.
6.  If the k6 CLI is installed, the service executes the script with a
    timeout and exports a summary.
7.  Parsed metrics are stored in the report's load-test data and
    performance-analysis result.

The current host allowlist includes `localhost`, `127.0.0.1`, `0.0.0.0`,
`host.docker.internal`, `api`, and `web`, plus hosts ending in `.local`.
This is a controlled local-testing design, not an unrestricted
production load-testing service.

### Metrics and thresholds

The generated test plan can include: - Virtual users (VUs). - Test
duration and ramp-up. - Request failure-rate threshold. - p95
response-time threshold. - Endpoint priorities. - Predicted bottlenecks.

The k6 execution service parses actual execution data into the
performance metrics schema. A generated test plan alone does not produce
real latency or failure-rate measurements.

## Optimization and approval model

The Optimization Agent uses both code-analysis findings and the
performance plan to recommend changes. Typical recommendation areas
include:

-   Replacing N+1 query patterns with batched or joined queries.
-   Adding pagination to unbounded reads.
-   Introducing caching where appropriate.
-   Removing blocking operations from asynchronous request paths.
-   Improving connection and resource management.
-   Reducing unnecessary data retrieval.
-   Moving expensive work to background processing.

Each proposal includes the problem, root cause, suggested solution, code
examples where available, expected benefit, risk, and validation steps.

**No automatic source-code modification is performed.** A developer must
inspect and approve a recommendation, implement it, run tests, and
repeat performance testing to verify whether it helped.

## Project structure

``` text
hacknauts_2/
├── .env.example
├── .gitignore
├── Makefile
├── docker-compose.yml
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── security.py
│   │   ├── pipeline.py
│   │   ├── celery_app.py
│   │   ├── worker.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   └── analyses.py
│   │   ├── rules/
│   │   │   └── scalability.yml
│   │   └── services/
│   │       ├── agents/
│   │       │   ├── agent_schemas.py
│   │       │   ├── code_analysis_agent.py
│   │       │   ├── performance_agent.py
│   │       │   └── optimization_agent.py
│   │       ├── evaluation/
│   │       ├── ai_agent.py
│   │       ├── detect.py
│   │       ├── fsutil.py
│   │       ├── git_ops.py
│   │       ├── groq_client.py
│   │       ├── k6_service.py
│   │       └── scanner.py
│   └── tests/
│       ├── test_agents.py
│       ├── test_api_endpoints.py
│       ├── test_core.py
│       ├── test_groq_client.py
│       └── test_k6_service.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── components/
│       ├── context/
│       ├── lib/
│       └── pages/
│
├── docs/
│   └── architecture.md
└── infra/
    └── prometheus.yml
```

## Prerequisites

### Docker-based setup

-   Docker Engine or Docker Desktop.
-   Docker Compose v2.
-   A Groq API key for live AI responses.

### Manual setup

-   Python compatible with the project's installed dependencies.
-   Node.js and npm.
-   PostgreSQL, or use the application's SQLite fallback for local
    development.
-   Redis if you want Celery-based background processing.
-   k6 if you want to execute load tests rather than only generate
    plans.
-   A Groq API key for live AI responses.

Use a Python version supported by all installed dependencies. If a
dependency does not yet support your system's newest Python release, use
a compatible Python version in a virtual environment.

## Configuration

From the project root, create your local environment file:

``` bash
cp .env.example .env
```

Edit `.env`:

``` dotenv
# Authentication and frontend access
JWT_SECRET=replace-with-a-long-random-secret
CORS_ORIGINS=http://localhost:5173
ENABLE_DEMO=true

# Groq API
GROQ_API_KEY=your_groq_api_key
GROQ_CODE_MODEL=llama-3.3-70b-versatile
GROQ_PERFORMANCE_MODEL=llama-3.3-70b-versatile
GROQ_OPTIMIZATION_MODEL=llama-3.3-70b-versatile

# AI request settings
GROQ_TIMEOUT=60
GROQ_MAX_RETRIES=3
GROQ_TEMPERATURE=0.2

# Frontend API URL
VITE_API_URL=http://localhost:8000
```

### Important environment variables

  -----------------------------------------------------------------------
  Variable                            Purpose
  ----------------------------------- -----------------------------------
  `JWT_SECRET`                        Secret used to sign JWT
                                      authentication tokens; replace the
                                      development value

  `JWT_HOURS`                         Token validity period in hours

  `CORS_ORIGINS`                      Comma-separated allowed frontend
                                      origins

  `ENABLE_DEMO`                       Enables or disables demo login

  `DEMO_EMAIL`                        Demo account email

  `DEMO_PASSWORD`                     Demo account password

  `DATABASE_URL`                      SQLAlchemy database connection URL

  `REDIS_URL`                         Redis broker/backend URL used by
                                      Celery

  `GROQ_API_KEY`                      Groq API credential

  `GROQ_CODE_MODEL`                   Model used by code analysis and
                                      repository Q&A

  `GROQ_PERFORMANCE_MODEL`            Model used by the performance agent

  `GROQ_OPTIMIZATION_MODEL`           Model used by the optimization
                                      agent

  `GROQ_TIMEOUT`                      Timeout for Groq requests

  `GROQ_MAX_RETRIES`                  Retry configuration for Groq calls

  `GROQ_TEMPERATURE`                  Model response temperature

  `VITE_API_URL`                      Backend URL baked into the frontend
                                      build
  -----------------------------------------------------------------------

Never commit `.env` or publish API keys, JWT secrets, or database
credentials.

## Run with Docker Compose

Run these commands from the directory containing `docker-compose.yml`:

``` bash
cp .env.example .env
```

Add your Groq API key to `.env`, then build and start the stack:

``` bash
docker compose up --build
```

Useful commands:

``` bash
# Run in the background
docker compose up --build -d

# View all service status
docker compose ps

# Follow API and worker logs
docker compose logs -f api worker

# Follow all service logs
docker compose logs -f

# Stop containers
docker compose down

# Stop containers and remove the PostgreSQL volume (deletes stored DB data)
docker compose down -v
```

### Local URLs

  Service                URL
  ---------------------- ------------------------------
  Frontend               http://localhost:5173
  Backend health         http://localhost:8000/health
  FastAPI Swagger docs   http://localhost:8000/docs
  FastAPI ReDoc          http://localhost:8000/redoc
  Prometheus             http://localhost:9090

Docker Compose starts PostgreSQL, Redis, API, Celery worker, frontend,
and Prometheus. The frontend container uses Nginx to serve the
production Vite build.

## Run locally without Docker

The following commands assume a Linux/macOS shell and that PostgreSQL
and Redis are installed and running.

### 1. Start PostgreSQL and Redis

Create a PostgreSQL database and user matching your `DATABASE_URL`, or
configure a different URL in `.env`.

Example local connection URL:

``` dotenv
DATABASE_URL=postgresql+psycopg://scalepilot:your_password@localhost:5432/scalepilot
REDIS_URL=redis://localhost:6379/0
```

The backend attempts to fall back to a local SQLite database if the
configured PostgreSQL connection cannot be established. For a
predictable multi-service setup, configure PostgreSQL correctly rather
than relying on this fallback.

### 2. Start the backend

``` bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API should be available at `http://localhost:8000`.

### 3. Start the Celery worker

Open another terminal:

``` bash
cd backend
source .venv/bin/activate
celery -A app.worker.celery_app worker --loglevel=info --concurrency=2
```

The API can dispatch jobs to this worker when Redis is reachable. If
Redis is unavailable, analysis dispatch has a background-thread
fallback.

### 4. Start the frontend

Open another terminal:

``` bash
cd frontend
npm install
npm run dev
```

Vite normally serves the frontend at `http://localhost:5173`. Ensure
`VITE_API_URL` points to the backend before starting the Vite process.

### 5. Install k6 for load-test execution

Install k6 using the instructions for your operating system from the
official k6 documentation. Confirm it is available:

``` bash
k6 version
```

If the k6 executable is not installed, the service may use its safe
fallback/simulation behavior where implemented; do not treat simulated
output as a real test of your application.

## API reference

The API is served by FastAPI. Interactive documentation is available at
`/docs`.

### Health

  Method   Endpoint             Description
  -------- -------------------- ---------------------------------------
  `GET`    `/health`            Basic backend health
  `GET`    `/api/health`        Alias for backend health
  `GET`    `/health/groq`       Groq configuration/connectivity check
  `GET`    `/api/health/groq`   Alias for Groq health check
  `GET`    `/metrics`           Prometheus metrics

### Authentication

  -----------------------------------------------------------------------
  Method                  Endpoint                Description
  ----------------------- ----------------------- -----------------------
  `POST`                  `/api/auth/signup`      Create an account

  `POST`                  `/api/auth/login`       Authenticate with email
                                                  and password

  `POST`                  `/api/auth/demo`        Start a demo session
                                                  when demo mode is
                                                  enabled

  `GET`                   `/api/auth/me`          Get the current
                                                  authenticated user

  `POST`                  `/api/auth/logout`      End the current session
  -----------------------------------------------------------------------

Successful signup/login/demo responses return a JWT token and email.
Protected routes expect:

``` http
Authorization: Bearer YOUR_JWT_TOKEN
```

### Repository analyses

  ---------------------------------------------------------------------------------------
  Method                  Endpoint                                Description
  ----------------------- --------------------------------------- -----------------------
  `POST`                  `/api/analyses`                         Create and queue a
                                                                  repository analysis;
                                                                  returns HTTP 202

  `GET`                   `/api/analyses`                         List the current user's
                                                                  latest reports

  `GET`                   `/api/analyses/{report_id}`             Retrieve a report and
                                                                  its results

  `POST`                  `/api/analyses/{report_id}/load-test`   Execute the report's
                                                                  generated k6 script

  `POST`                  `/api/analyses/{report_id}/ask`         Ask a question about
                                                                  the report
  ---------------------------------------------------------------------------------------

### Create an analysis

Example request:

``` bash
curl -X POST http://localhost:8000/api/analyses \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/owner/repository",
    "target_users": 100,
    "model": "your-selected-model"
  }'
```

The request schema defines the accepted model values. The API returns a
report identifier and initial status. Poll
`GET /api/analyses/{report_id}` to follow progress and retrieve the
completed report.

### Ask a question about a report

``` bash
curl -X POST http://localhost:8000/api/analyses/REPORT_ID/ask \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Which finding should I fix first?", "model": "your-selected-model"}'
```

The answer is based on the saved report context and uses Groq when
available, with a fallback response if the AI call cannot be completed.

## Database and background processing

### Database

SQLAlchemy models define users, repositories, and analysis reports.
PostgreSQL is the database configured by default for Docker Compose. The
local backend can fall back to SQLite if PostgreSQL is unavailable.

The application initializes its database tables during FastAPI startup
using SQLAlchemy metadata creation.

### Authentication and sessions

-   Passwords are stored as salted scrypt hashes.
-   JWTs are signed using the configured `JWT_SECRET`.
-   A session identifier is associated with the token and user.
-   Signing in again replaces the previous session identifier for that
    account.
-   Protected endpoints validate both the token and active session.

### Celery and Redis

The API dispatches repository analysis to a Celery worker when Redis is
reachable. The worker runs the same `run_pipeline` function used by the
fallback background-thread path.

This keeps longer repository analysis work out of the normal
request-response path. The report's status and stage are persisted so
the frontend can poll for progress.

## Monitoring

FastAPI metrics are exposed at:

``` text
http://localhost:8000/metrics
```

Prometheus configuration is located at `infra/prometheus.yml`. It
scrapes the API service on port `8000` every 15 seconds when running in
the provided Compose network.

Prometheus is available at:

``` text
http://localhost:9090
```

## Testing

Backend tests are located in `backend/tests/`.

Run them from the project root:

``` bash
cd backend
python -m pip install -r requirements.txt
python -m pytest -q
```

Or use the Makefile target from the project root:

``` bash
make test
```

Frontend production build:

``` bash
cd frontend
npm install
npm run build
```

Useful Makefile commands:

``` bash
make up
make down
make logs
make test
make fe
```

## Security and execution safeguards

The project includes several safeguards:

-   JWT authentication protects user-specific analysis and report
    endpoints.
-   Passwords are hashed using scrypt with per-password salts.
-   GitHub repository URLs are normalized and restricted to the expected
    GitHub URL format.
-   Repository size, clone time, file count, and file size are bounded
    through configuration.
-   Source repositories are cloned into temporary workspaces.
-   AI prompt evidence is passed through secret-redaction helpers in the
    Groq client/agent workflow.
-   Generated k6 scripts are checked for selected dangerous JavaScript
    constructs.
-   k6 target URLs are restricted to an explicit local-host allowlist.
-   k6 execution has a timeout.
-   Optimization proposals require developer approval and are not
    automatically applied.

These controls reduce risk but are not a substitute for a full security
review before production deployment. In particular, review secret
handling, dependency updates, container isolation, database credentials,
and load-test resource limits before exposing the service publicly.

## Troubleshooting

### Frontend says it cannot reach the backend

1.  Confirm the API is running.
2.  Open `http://localhost:8000/health`.
3.  Check `VITE_API_URL` in `.env`.
4.  Restart Vite after changing environment variables.
5.  Check browser console and backend logs for CORS or connection
    errors.

### PostgreSQL connection fails

1.  Confirm PostgreSQL is running and listening on the configured port.
2.  Verify database name, username, password, and `DATABASE_URL`.
3.  Check API logs for the database connection message.
4.  Remember that local development may silently switch to SQLite when
    PostgreSQL cannot be reached.

### Analysis stays queued or does not progress

1.  Check `docker compose ps`.
2.  Check Redis health and connectivity.
3.  Inspect `docker compose logs -f api worker`.
4.  Confirm the Celery worker starts successfully.
5.  If Redis is unavailable, the API may use its background-thread
    fallback; inspect API logs.

### AI results use fallback output

1.  Confirm `GROQ_API_KEY` is present in the backend environment.
2.  Check `/health/groq`.
3.  Verify configured model IDs are available to your Groq account.
4.  Inspect API/worker logs for rate limits, timeouts, or schema
    validation errors.

### k6 load test fails

1.  Confirm the analysis is complete.
2.  Confirm the generated script is valid and exports a default
    function.
3.  Confirm the target URL is on the configured host allowlist.
4.  Install k6 and verify `k6 version`.
5.  Inspect backend logs for script validation, target validation, or
    execution timeout errors.

### Port already in use

Find the process using the required port or change the host port mapping
in `docker-compose.yml`. Common local ports are `5173`, `8000`, `5432`,
`6379`, and `9090`.

## Current limitations and extension ideas

The following points describe the current implementation and sensible
future work; they should not be interpreted as already completed
features.

-   **Repository access:** The clone URL validator currently supports
    public GitHub HTTPS repository URLs. Private repository
    authentication is not implemented in the inspected clone service.
-   **Language coverage:** Tree-sitter parsing is configured for Python,
    JavaScript, and TypeScript/TSX, while Semgrep rules cover selected
    additional languages. Detection coverage varies by rule and
    language.
-   **Load-test targets:** The k6 service is restricted to
    local/allowlisted hosts. A production-grade remote testing system
    would need explicit target ownership verification, authorization,
    quotas, and isolation.
-   **Performance evidence:** AI-generated plans and predicted
    bottlenecks must remain separate from metrics collected by an
    executed test.
-   **Optimization application:** Patches are recommendations and
    require developer implementation and approval.
-   **Distributed execution:** Redis/Celery improves job handling, but
    production deployment should also consider retries, job monitoring,
    worker scaling, and persistent task observability.
-   **Database migrations:** The current startup path creates tables
    from SQLAlchemy metadata. A migration tool such as Alembic would be
    useful as the schema evolves.
-   **Evaluation:** The repository includes agent evaluation data and a
    runner; extend these datasets as new languages, rules, and agent
    behaviors are added.
-   **Observability:** Add structured logs, tracing, and business-level
    metrics for clone duration, scan duration, agent latency, queue wait
    time, and k6 execution outcomes.

## Contributing

1.  Fork the repository.
2.  Create a feature branch.
3.  Make a focused change.
4.  Run backend tests and the frontend production build.
5.  Update documentation when APIs, configuration, or workflows change.
6.  Open a pull request describing the change and its validation.

## License

Add the license and ownership details applicable to your project before
publishing or distributing it.
