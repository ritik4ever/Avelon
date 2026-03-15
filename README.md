# Avelon

**AI Red-Team Platform for Code Models**

Avelon is a production-oriented evaluation platform for stress-testing AI coding models on adversarial smart contract security tasks. It is positioned as reliability infrastructure, not an AI auditor. The system generates or ingests adversarial tasks, runs models against them, establishes ground truth with static analyzers, scores failures, and produces reproducible benchmark artifacts.

## What Is Implemented

- Multi-model reliability comparison on the same Solidity contract
- Benchmark mode for running one model across a dataset
- Adversarial dataset generation with `template`, `mutation`, `fuzzing`, and `mixed` generation methods
- Dataset upload and immutable dataset versioning
- Unified model execution for `openai`, `anthropic`, `google`, and `custom` OpenAI-compatible providers
- Ground-truth collection through isolated `Slither` and `Mythril` execution
- Failure classification:
  - hallucinated vulnerability
  - missed vulnerability
  - incorrect reasoning chain
  - overconfidence
  - partial detection
  - misidentified vulnerability type
- Severity-weighted scoring and aggregated benchmark statistics
- Public leaderboard based on weighted reliability
- Failure explorer and downloadable reports
- Docker Compose deployment with backend, worker, dataset generator, analyzer runner, Redis, Postgres, and frontend

## Product Workflows

### 1. Compare Models

Default workflow in the frontend:

- upload one Solidity contract
- select multiple models
- run deterministic evaluations
- compare `precision`, `recall`, `hallucination_rate`, `miss_rate`, and `weighted_reliability_score`

### 2. Benchmark Model

Benchmark workflow:

- select provider and model
- optionally choose a generated or uploaded dataset version
- run the model across the task set
- store aggregate benchmark history
- inspect category-level and difficulty-level performance

### 3. Manage Datasets

Dataset workflow:

- generate adversarial datasets asynchronously
- upload curated tasks
- keep dataset versions immutable
- inspect generated task sets and metadata

## Architecture

### Services

- `frontend`: Next.js application
- `backend`: FastAPI API
- `worker`: Celery worker for evaluations, comparisons, and benchmarks
- `dataset-generator`: Celery worker dedicated to dataset generation
- `analyzer-runner`: isolated FastAPI microservice for `Slither` and `Mythril`
- `postgres`: primary relational store
- `redis`: queue broker and cache backend

### Backend Modules

- `app/services/task_generator.py`: adversarial task generation
- `app/services/ai_auditor.py`: unified model execution and JSON validation
- `app/services/analyzer_client.py`: analyzer-runner integration
- `app/services/comparator.py`: AI vs. ground-truth matching
- `app/services/scorer.py`: deterministic severity-weighted scoring
- `app/services/failure_analyzer.py`: reasoning failure classification
- `app/services/report_generator.py`: report creation
- `app/worker/tasks.py`: async evaluation, comparison, benchmark, and dataset jobs

### Sandbox Model

The analyzer runner is intentionally isolated:

- read-only root filesystem
- `tmpfs` scratch space
- no outbound internet on the internal Docker network
- CPU, memory, and PID limits in Compose
- timeout-bounded analyzer execution

## Scoring Model

For each evaluation:

- `TP`: correct detections
- `FP`: hallucinated vulnerabilities
- `FN`: missed vulnerabilities

Computed metrics:

- `precision = TP / (TP + FP)`
- `recall = TP / (TP + FN)`
- `hallucination_rate = FP / (TP + FP)`
- `miss_rate = FN / (TP + FN)`
- `weighted_reliability_score`

Severity weighting penalizes missed `critical` and `high` findings more heavily than lower-severity errors.

## Data Model

Primary tables currently modeled and migrated:

- `users`
- `datasets`
- `tasks`
- `models`
- `contracts`
- `evaluations`
- `vulnerabilities`
- `reports`
- `comparison_runs`
- `comparison_results`
- `benchmark_runs`
- `benchmark_results`
- `failures`
- `app_schema_migrations`

All major entities include `created_at` and `updated_at`.

## Frontend Pages

Implemented routes:

- `/`: landing page
- `/register`
- `/login`
- `/dashboard`
- `/upload`: multi-model comparison
- `/comparison/[id]`
- `/benchmark`
- `/benchmark/[id]`
- `/datasets`
- `/failures`
- `/leaderboard`
- `/processing/[id]`
- `/results/[id]`

## API Surface

### Auth

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`

### Health

- `GET /api/v1/live`
- `GET /api/v1/health`

### Contracts And Evaluations

- `POST /api/v1/contracts/upload`
- `GET /api/v1/contracts/`
- `GET /api/v1/contracts/{id}`
- `POST /api/v1/evaluations/`
- `GET /api/v1/evaluations/`
- `GET /api/v1/evaluations/{id}`
- `GET /api/v1/evaluations/{id}/vulnerabilities`

### Comparisons

- `POST /api/v1/comparisons/`
- `GET /api/v1/comparisons/`
- `GET /api/v1/comparisons/{id}`
- `GET /api/v1/comparisons/{id}/results`

### Benchmarks

- `POST /api/v1/benchmarks/`
- `GET /api/v1/benchmarks/`
- `GET /api/v1/benchmarks/{id}`
- `GET /api/v1/benchmarks/{id}/results`

### Datasets

- `POST /api/v1/datasets/generate`
- `POST /api/v1/datasets/upload`
- `GET /api/v1/datasets/`
- `GET /api/v1/datasets/{id}`
- `GET /api/v1/datasets/{id}/tasks`

### Failures, Leaderboard, Reports

- `GET /api/v1/failures`
- `GET /api/v1/failures/summary`
- `GET /api/v1/leaderboard/models`
- `GET /api/v1/reports/evaluation/{evaluation_id}`
- `GET /api/v1/reports/evaluation/{evaluation_id}/json`
- `GET /api/v1/reports/evaluation/{evaluation_id}/pdf`

## Provider Support

Supported provider values:

- `openai`
- `anthropic`
- `google`
- `custom`

`custom` is intended for local or hosted OpenAI-compatible endpoints via `CUSTOM_OPENAI_BASE_URL`.

## Determinism

The product is intentionally deterministic for security evaluation:

- frontend comparison and benchmark flows default to temperature `0.0`
- backend schemas restrict temperature to `0.0` through `0.2`
- scoring is designed for reproducibility, not creative generation

## Reports

Generated report artifacts include:

- model metadata
- analyzer versions
- comparison outcomes
- aggregate metrics
- reproducibility hash
- downloadable JSON and PDF outputs

## Migrations And Existing Volumes

The backend includes an idempotent migration runner and a DB bootstrap resolver:

- startup tries current `Avelon` DB credentials first
- if that fails, startup can fall back to legacy pre-rebrand credentials from `.env`

Relevant environment variables:

- `DATABASE_URL`
- `DATABASE_URL_SYNC`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `LEGACY_POSTGRES_USER`
- `LEGACY_POSTGRES_PASSWORD`
- `LEGACY_POSTGRES_DB`

This allows non-fresh Postgres volumes to be upgraded without resetting all data.

## Environment

Core variables used by the system:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `CUSTOM_OPENAI_BASE_URL`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `REDIS_URL`
- `ANALYZER_RUNNER_URL`
- `UPLOAD_DIR`

Use [.env.example](C:/Users/ritik/Desktop/AI%20Auditor/.env.example) as the template.

## Local Run

```bash
cp .env.example .env
cd infra
docker compose up --build -d postgres redis analyzer-runner backend worker dataset-generator frontend
docker compose ps
```

Primary URLs:

- frontend: `http://localhost:3000`
- backend liveness: `http://localhost:8000/api/v1/live`
- backend readiness: `http://localhost:8000/api/v1/health`

## Useful Commands

```bash
cd infra
docker compose logs backend --tail=120
docker compose logs worker --tail=120
docker compose logs dataset-generator --tail=120
docker compose logs analyzer-runner --tail=120
```

Full reset for local development:

```bash
cd infra
docker compose down --remove-orphans --volumes
docker compose up --build -d postgres redis analyzer-runner backend worker dataset-generator frontend
```

## Current Scope

Current implementation focus:

- Solidity smart contract tasks
- adversarial reliability evaluation for code-security reasoning
- model benchmarking and failure analysis

Architecture is intentionally extensible to additional languages such as Rust and Go, but those language pipelines are not yet implemented in the current repo.
