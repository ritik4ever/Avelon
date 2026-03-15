-- ============================================
-- Avelon - Database Schema (Red-Team Platform)
-- ============================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE contract_status AS ENUM ('uploaded', 'preprocessed', 'failed');
CREATE TYPE eval_status AS ENUM (
    'queued', 'preprocessing', 'ai_analysis', 'static_analysis',
    'comparing', 'scoring', 'report_ready', 'failed', 'timeout'
);
CREATE TYPE vuln_source AS ENUM ('ai', 'slither', 'mythril', 'curated');
CREATE TYPE severity_level AS ENUM ('info', 'low', 'medium', 'high', 'critical');
CREATE TYPE match_class AS ENUM ('true_positive', 'false_positive', 'false_negative', 'unmatched');
CREATE TYPE benchmark_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE comparison_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE dataset_status AS ENUM ('queued', 'generating', 'ready', 'failed');
CREATE TYPE task_difficulty AS ENUM ('easy', 'medium', 'hard', 'adversarial');
CREATE TYPE task_generation_method AS ENUM ('template', 'mutation', 'fuzzing', 'upload', 'mixed');
CREATE TYPE failure_type AS ENUM (
    'hallucinated_vulnerability',
    'missed_vulnerability',
    'incorrect_reasoning_chain',
    'overconfidence',
    'partial_detection',
    'misidentified_vulnerability_type'
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    api_key_encrypted TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);

CREATE TABLE datasets (
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
);
CREATE INDEX idx_datasets_version ON datasets(dataset_version);
CREATE INDEX idx_datasets_status ON datasets(status);
CREATE INDEX idx_datasets_created_by ON datasets(created_by);

CREATE TABLE tasks (
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
);
CREATE INDEX idx_tasks_dataset_id ON tasks(dataset_id);
CREATE INDEX idx_tasks_difficulty ON tasks(difficulty);
CREATE INDEX idx_tasks_category ON tasks(category);

CREATE TABLE models (
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
);
CREATE INDEX idx_models_provider ON models(provider);
CREATE INDEX idx_models_model_name ON models(model_name);

CREATE TABLE contracts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
    filename VARCHAR(255) NOT NULL,
    original_source TEXT NOT NULL,
    flattened_source TEXT,
    solidity_version VARCHAR(20),
    file_hash VARCHAR(64) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    status contract_status DEFAULT 'uploaded',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_contracts_user_id ON contracts(user_id);
CREATE INDEX idx_contracts_task_id ON contracts(task_id);
CREATE INDEX idx_contracts_file_hash ON contracts(file_hash);

CREATE TABLE evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
    model_id UUID REFERENCES models(id) ON DELETE SET NULL,
    status eval_status DEFAULT 'queued',
    ai_provider VARCHAR(50) NOT NULL,
    ai_model VARCHAR(100) NOT NULL,
    ai_temperature FLOAT DEFAULT 0.0,
    latency_ms FLOAT,
    token_usage_prompt INTEGER,
    token_usage_completion INTEGER,
    estimated_cost_usd FLOAT,
    precision_score FLOAT,
    recall_score FLOAT,
    hallucination_rate FLOAT,
    miss_rate FLOAT,
    reliability_score FLOAT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_evaluations_user_id ON evaluations(user_id);
CREATE INDEX idx_evaluations_contract_id ON evaluations(contract_id);
CREATE INDEX idx_evaluations_task_id ON evaluations(task_id);
CREATE INDEX idx_evaluations_model_id ON evaluations(model_id);
CREATE INDEX idx_evaluations_status ON evaluations(status);

CREATE TABLE vulnerabilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    source vuln_source NOT NULL,
    vuln_type VARCHAR(255) NOT NULL,
    function_name VARCHAR(255),
    line_number INTEGER,
    severity severity_level DEFAULT 'medium',
    confidence FLOAT,
    description TEXT,
    match_classification match_class DEFAULT 'unmatched',
    matched_vuln_id UUID REFERENCES vulnerabilities(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_vulns_evaluation_id ON vulnerabilities(evaluation_id);
CREATE INDEX idx_vulns_source ON vulnerabilities(source);
CREATE INDEX idx_vulns_match ON vulnerabilities(match_classification);

CREATE TABLE comparison_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    status comparison_status DEFAULT 'queued',
    total_models INTEGER DEFAULT 0,
    completed_models INTEGER DEFAULT 0,
    avg_precision FLOAT,
    avg_recall FLOAT,
    avg_hallucination_rate FLOAT,
    avg_miss_rate FLOAT,
    avg_reliability_score FLOAT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_comparison_runs_user_id ON comparison_runs(user_id);
CREATE INDEX idx_comparison_runs_contract_id ON comparison_runs(contract_id);
CREATE INDEX idx_comparison_runs_status ON comparison_runs(status);

CREATE TABLE comparison_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    comparison_run_id UUID NOT NULL REFERENCES comparison_runs(id) ON DELETE CASCADE,
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    ai_provider VARCHAR(50) NOT NULL,
    ai_model VARCHAR(100) NOT NULL,
    precision_score FLOAT,
    recall_score FLOAT,
    hallucination_rate FLOAT,
    miss_rate FLOAT,
    reliability_score FLOAT,
    tp_count INTEGER,
    fp_count INTEGER,
    fn_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_comp_run_model UNIQUE (comparison_run_id, ai_provider, ai_model)
);
CREATE INDEX idx_comp_results_run_id ON comparison_results(comparison_run_id);
CREATE INDEX idx_comp_results_eval_id ON comparison_results(evaluation_id);

CREATE TABLE benchmark_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dataset_id UUID REFERENCES datasets(id) ON DELETE SET NULL,
    model_id UUID REFERENCES models(id) ON DELETE SET NULL,
    ai_provider VARCHAR(50) NOT NULL,
    ai_model VARCHAR(100) NOT NULL,
    ai_temperature FLOAT DEFAULT 0.0,
    status benchmark_status DEFAULT 'queued',
    total_contracts INTEGER DEFAULT 0,
    completed_contracts INTEGER DEFAULT 0,
    avg_precision FLOAT,
    avg_recall FLOAT,
    avg_hallucination_rate FLOAT,
    avg_miss_rate FLOAT,
    avg_reliability_score FLOAT,
    avg_latency_ms FLOAT,
    category_performance JSONB,
    difficulty_performance JSONB,
    benchmark_summary TEXT,
    total_token_usage INTEGER,
    total_estimated_cost_usd FLOAT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_benchmark_runs_user_id ON benchmark_runs(user_id);
CREATE INDEX idx_benchmark_runs_dataset_id ON benchmark_runs(dataset_id);
CREATE INDEX idx_benchmark_runs_model_id ON benchmark_runs(model_id);
CREATE INDEX idx_benchmark_runs_status ON benchmark_runs(status);

CREATE TABLE benchmark_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    benchmark_run_id UUID NOT NULL REFERENCES benchmark_runs(id) ON DELETE CASCADE,
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
    difficulty task_difficulty,
    precision_score FLOAT,
    recall_score FLOAT,
    hallucination_rate FLOAT,
    miss_rate FLOAT,
    reliability_score FLOAT,
    latency_ms FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bench_results_run_id ON benchmark_results(benchmark_run_id);
CREATE INDEX idx_bench_results_eval_id ON benchmark_results(evaluation_id);
CREATE INDEX idx_bench_results_task_id ON benchmark_results(task_id);

CREATE TABLE failures (
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
);
CREATE INDEX idx_failures_evaluation_id ON failures(evaluation_id);
CREATE INDEX idx_failures_benchmark_id ON failures(benchmark_run_id);
CREATE INDEX idx_failures_task_id ON failures(task_id);
CREATE INDEX idx_failures_type ON failures(failure_type);
CREATE INDEX idx_failures_severity ON failures(severity);

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluation_id UUID UNIQUE NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    report_json JSONB NOT NULL,
    pdf_path TEXT,
    reproducibility_hash VARCHAR(64) NOT NULL,
    analyzer_versions JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_reports_evaluation_id ON reports(evaluation_id);
