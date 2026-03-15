"""Idempotent SQL migrations for existing Postgres volumes."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection


MIGRATION_VERSION = "20260305_01_redteam_core"


def _statements_for_current_version() -> Iterable[str]:
    yield 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'
    yield """
DO $$ BEGIN
    CREATE TYPE dataset_status AS ENUM ('queued', 'generating', 'ready', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
"""
    yield """
DO $$ BEGIN
    CREATE TYPE task_difficulty AS ENUM ('easy', 'medium', 'hard', 'adversarial');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
"""
    yield """
DO $$ BEGIN
    CREATE TYPE task_generation_method AS ENUM ('template', 'mutation', 'fuzzing', 'upload', 'mixed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
"""
    yield """
DO $$ BEGIN
    CREATE TYPE failure_type AS ENUM (
        'hallucinated_vulnerability',
        'missed_vulnerability',
        'incorrect_reasoning_chain',
        'overconfidence',
        'partial_detection',
        'misidentified_vulnerability_type'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
"""
    yield """
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    dataset_version VARCHAR(64) NOT NULL UNIQUE,
    language VARCHAR(32) NOT NULL DEFAULT 'solidity',
    generation_method task_generation_method NOT NULL DEFAULT 'mixed',
    status dataset_status NOT NULL DEFAULT 'queued',
    description TEXT,
    categories JSONB,
    task_count INTEGER NOT NULL DEFAULT 0,
    metadata_json JSONB,
    is_immutable BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""
    yield """
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    task_id VARCHAR(128) NOT NULL UNIQUE,
    language VARCHAR(32) NOT NULL DEFAULT 'solidity',
    contract_code TEXT NOT NULL,
    expected_vulnerabilities JSONB NOT NULL,
    difficulty task_difficulty NOT NULL DEFAULT 'medium',
    category VARCHAR(128) NOT NULL,
    generation_method task_generation_method NOT NULL DEFAULT 'template',
    metadata_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""
    yield """
CREATE TABLE IF NOT EXISTS models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider VARCHAR(32) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    api_base VARCHAR(512),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_model_provider_name_base UNIQUE (provider, model_name, api_base)
)
"""
    yield """
CREATE TABLE IF NOT EXISTS failures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    benchmark_run_id UUID REFERENCES benchmark_runs(id) ON DELETE SET NULL,
    task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
    failure_type failure_type NOT NULL,
    severity severity_level NOT NULL DEFAULT 'medium',
    vulnerability_type VARCHAR(255),
    confidence FLOAT,
    details_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""
    yield """
ALTER TABLE contracts
    ADD COLUMN IF NOT EXISTS task_id UUID REFERENCES tasks(id) ON DELETE SET NULL
"""
    yield """
ALTER TABLE evaluations
    ADD COLUMN IF NOT EXISTS task_id UUID REFERENCES tasks(id) ON DELETE SET NULL
"""
    yield """
ALTER TABLE evaluations
    ADD COLUMN IF NOT EXISTS model_id UUID REFERENCES models(id) ON DELETE SET NULL
"""
    yield """
ALTER TABLE evaluations
    ADD COLUMN IF NOT EXISTS latency_ms FLOAT
"""
    yield """
ALTER TABLE benchmark_runs
    ADD COLUMN IF NOT EXISTS dataset_id UUID REFERENCES datasets(id) ON DELETE SET NULL
"""
    yield """
ALTER TABLE benchmark_runs
    ADD COLUMN IF NOT EXISTS model_id UUID REFERENCES models(id) ON DELETE SET NULL
"""
    yield """
ALTER TABLE benchmark_runs
    ADD COLUMN IF NOT EXISTS avg_latency_ms FLOAT
"""
    yield """
ALTER TABLE benchmark_runs
    ADD COLUMN IF NOT EXISTS difficulty_performance JSONB
"""
    yield """
ALTER TABLE benchmark_runs
    ADD COLUMN IF NOT EXISTS category_performance JSONB
"""
    yield """
ALTER TABLE benchmark_runs
    ADD COLUMN IF NOT EXISTS benchmark_summary TEXT
"""
    yield """
ALTER TABLE benchmark_results
    ADD COLUMN IF NOT EXISTS task_id UUID REFERENCES tasks(id) ON DELETE SET NULL
"""
    yield """
ALTER TABLE benchmark_results
    ADD COLUMN IF NOT EXISTS difficulty task_difficulty
"""
    yield """
ALTER TABLE benchmark_results
    ADD COLUMN IF NOT EXISTS latency_ms FLOAT
"""
    yield "CREATE INDEX IF NOT EXISTS idx_datasets_version ON datasets(dataset_version)"
    yield "CREATE INDEX IF NOT EXISTS idx_datasets_status ON datasets(status)"
    yield "CREATE INDEX IF NOT EXISTS idx_tasks_dataset_id ON tasks(dataset_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_tasks_difficulty ON tasks(difficulty)"
    yield "CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category)"
    yield "CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider)"
    yield "CREATE INDEX IF NOT EXISTS idx_models_model_name ON models(model_name)"
    yield "CREATE INDEX IF NOT EXISTS idx_contracts_task_id ON contracts(task_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_evaluations_task_id ON evaluations(task_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_evaluations_model_id ON evaluations(model_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_benchmark_runs_dataset_id ON benchmark_runs(dataset_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_benchmark_runs_model_id ON benchmark_runs(model_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_bench_results_task_id ON benchmark_results(task_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_failures_evaluation_id ON failures(evaluation_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_failures_benchmark_id ON failures(benchmark_run_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_failures_task_id ON failures(task_id)"
    yield "CREATE INDEX IF NOT EXISTS idx_failures_type ON failures(failure_type)"
    yield "CREATE INDEX IF NOT EXISTS idx_failures_severity ON failures(severity)"


def run_migrations_in_connection(conn: Connection) -> None:
    """Apply idempotent migrations in a single DB transaction."""
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS app_schema_migrations (
                version VARCHAR(128) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )

    already_applied = conn.execute(
        text("SELECT 1 FROM app_schema_migrations WHERE version = :version"),
        {"version": MIGRATION_VERSION},
    ).scalar()
    if already_applied:
        return

    for stmt in _statements_for_current_version():
        conn.execute(text(stmt))

    conn.execute(
        text(
            """
            INSERT INTO app_schema_migrations(version)
            VALUES (:version)
            ON CONFLICT (version) DO NOTHING
            """
        ),
        {"version": MIGRATION_VERSION},
    )
