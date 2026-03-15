/**
 * API client for communicating with the Avelon backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_BASE = `${API_URL}/api/v1`;

interface RequestOptions {
    method?: string;
    body?: unknown;
    token?: string | null;
    headers?: Record<string, string>;
}

class ApiError extends Error {
    status: number;
    data: unknown;
    constructor(message: string, status: number, data?: unknown) {
        super(message);
        this.status = status;
        this.data = data;
    }
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, token, headers = {} } = options;

    const config: RequestInit = {
        method,
        headers: {
            'Content-Type': 'application/json',
            ...headers,
        },
    };

    if (token) {
        (config.headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
    }

    if (body) {
        config.body = JSON.stringify(body);
    }

    let response: Response;
    try {
        response = await fetch(`${API_BASE}${endpoint}`, config);
    } catch {
        throw new Error(`Cannot reach backend API at ${API_BASE}. Ensure backend is running.`);
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
            errorData.detail || `HTTP ${response.status}`,
            response.status,
            errorData
        );
    }

    return response.json() as Promise<T>;
}

async function uploadFile<T>(endpoint: string, file: File, token: string): Promise<T> {
    const formData = new FormData();
    formData.append('file', file);

    let response: Response;
    try {
        response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: formData,
        });
    } catch {
        throw new Error(`Cannot reach backend API at ${API_BASE}. Ensure backend is running.`);
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
            errorData.detail || `Upload failed: ${response.status}`,
            response.status,
            errorData
        );
    }

    return response.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────

export const auth = {
    register: (email: string, password: string, fullName?: string) =>
        request<{ access_token: string; refresh_token: string }>('/auth/register', {
            method: 'POST',
            body: { email, password, full_name: fullName },
        }),
    login: (email: string, password: string) =>
        request<{ access_token: string; refresh_token: string }>('/auth/login', {
            method: 'POST',
            body: { email, password },
        }),
    refresh: (refreshToken: string) =>
        request<{ access_token: string; refresh_token: string }>('/auth/refresh', {
            method: 'POST',
            body: { refresh_token: refreshToken },
        }),
    me: (token: string) =>
        request<{ id: string; email: string; full_name: string | null }>('/auth/me', { token }),
};

// ── Contracts ─────────────────────────────────────────────────────

export const contracts = {
    upload: (file: File, token: string) =>
        uploadFile<{ id: string; filename: string; file_hash: string; status: string }>(
            '/contracts/upload', file, token
        ),
    list: (token: string) =>
        request<Array<{ id: string; filename: string; status: string; created_at: string }>>(
            '/contracts/', { token }
        ),
    get: (id: string, token: string) =>
        request<{ id: string; filename: string; file_hash: string; status: string }>(
            `/contracts/${id}`, { token }
        ),
};

// ── Evaluations ───────────────────────────────────────────────────

export interface Evaluation {
    id: string;
    contract_id: string;
    status: string;
    ai_provider: string;
    ai_model: string;
    ai_temperature: number;
    precision_score: number | null;
    recall_score: number | null;
    hallucination_rate: number | null;
    miss_rate: number | null;
    reliability_score: number | null;
    token_usage_prompt: number | null;
    token_usage_completion: number | null;
    estimated_cost_usd: number | null;
    error_message: string | null;
    started_at: string | null;
    completed_at: string | null;
    created_at: string;
}

export interface VulnerabilityItem {
    id: string;
    source: string;
    vuln_type: string;
    function_name: string | null;
    line_number: number | null;
    severity: string;
    confidence: number | null;
    description: string | null;
    match_classification: string;
}

export const evaluations = {
    create: (data: {
        contract_id: string;
        ai_provider: string;
        ai_model: string;
        ai_temperature?: number;
    }, token: string) =>
        request<Evaluation>('/evaluations/', { method: 'POST', body: data, token }),
    list: (token: string) =>
        request<Array<Evaluation>>('/evaluations/', { token }),
    get: (id: string, token: string) =>
        request<Evaluation>(`/evaluations/${id}`, { token }),
    vulnerabilities: (id: string, token: string) =>
        request<Array<VulnerabilityItem>>(`/evaluations/${id}/vulnerabilities`, { token }),
};

// ── Benchmarks ────────────────────────────────────────────────────

export interface BenchmarkRun {
    id: string;
    dataset_id: string | null;
    ai_provider: string;
    ai_model: string;
    status: string;
    total_contracts: number;
    completed_contracts: number;
    avg_precision: number | null;
    avg_recall: number | null;
    avg_hallucination_rate: number | null;
    avg_miss_rate: number | null;
    avg_reliability_score: number | null;
    avg_latency_ms: number | null;
    category_performance: Record<string, {
        tp: number;
        fp: number;
        fn: number;
        precision: number;
        recall: number;
        reliability: number;
    }> | null;
    difficulty_performance: Record<string, {
        count: number;
        precision: number;
        recall: number;
        hallucination_rate: number;
        miss_rate: number;
        reliability: number;
    }> | null;
    benchmark_summary: string | null;
    total_token_usage: number | null;
    total_estimated_cost_usd: number | null;
    error_message: string | null;
    created_at: string;
}

export const benchmarks = {
    create: (data: {
        ai_provider: string;
        ai_model: string;
        dataset_id?: string;
        ai_temperature?: number;
        custom_api_key?: string;
        custom_api_base?: string;
    }, token: string) =>
        request<BenchmarkRun>('/benchmarks/', { method: 'POST', body: data, token }),
    list: (token: string) =>
        request<Array<BenchmarkRun>>('/benchmarks/', { token }),
    get: (id: string, token: string) =>
        request<BenchmarkRun>(`/benchmarks/${id}`, { token }),
    results: (id: string, token: string) =>
        request<Array<{
            id: string; contract_id: string;
            precision_score: number | null; recall_score: number | null;
            hallucination_rate: number | null;
            miss_rate: number | null;
            reliability_score: number | null;
            task_id: string | null;
            difficulty: string | null;
            latency_ms: number | null;
        }>>(`/benchmarks/${id}/results`, { token }),
};

// -- Model Comparison --------------------------------------------------------

export interface ComparisonRun {
    id: string;
    contract_id: string;
    status: string;
    total_models: number;
    completed_models: number;
    avg_precision: number | null;
    avg_recall: number | null;
    avg_hallucination_rate: number | null;
    avg_miss_rate: number | null;
    avg_reliability_score: number | null;
    error_message: string | null;
    started_at: string | null;
    completed_at: string | null;
    created_at: string;
}

export interface ComparisonResult {
    id: string;
    evaluation_id: string;
    ai_provider: string;
    ai_model: string;
    precision_score: number | null;
    recall_score: number | null;
    hallucination_rate: number | null;
    miss_rate: number | null;
    reliability_score: number | null;
    tp_count: number | null;
    fp_count: number | null;
    fn_count: number | null;
}

export const comparisons = {
    create: (
        data: {
            contract_id: string;
            models: Array<{
                ai_provider: string;
                ai_model: string;
                custom_api_key?: string;
                custom_api_base?: string;
            }>;
            ai_temperature?: number;
        },
        token: string
    ) => request<ComparisonRun>('/comparisons/', { method: 'POST', body: data, token }),
    list: (token: string) => request<Array<ComparisonRun>>('/comparisons/', { token }),
    get: (id: string, token: string) => request<ComparisonRun>(`/comparisons/${id}`, { token }),
    results: (id: string, token: string) =>
        request<Array<ComparisonResult>>(`/comparisons/${id}/results`, { token }),
};

// -- Datasets ---------------------------------------------------------------

export interface DatasetRecord {
    id: string;
    name: string;
    dataset_version: string;
    language: string;
    generation_method: string;
    status: string;
    description: string | null;
    categories: Record<string, unknown> | null;
    task_count: number;
    metadata_json: Record<string, unknown> | null;
    is_immutable: boolean;
    created_by: string | null;
    created_at: string;
    updated_at: string;
}

export interface DatasetTask {
    id: string;
    dataset_id: string;
    task_id: string;
    language: string;
    contract_code: string;
    expected_vulnerabilities: Array<Record<string, unknown>>;
    difficulty: string;
    category: string;
    generation_method: string;
    metadata_json: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
}

export interface DatasetGenerationAccepted {
    dataset: DatasetRecord;
    job_id: string;
}

export const datasets = {
    generate: (data: {
        name: string;
        dataset_version?: string;
        language?: string;
        generation_method?: string;
        description?: string;
        task_count?: number;
        categories?: string[];
        difficulty_mix?: Record<string, number>;
        seed?: number;
    }, token: string) =>
        request<DatasetGenerationAccepted>('/datasets/generate', { method: 'POST', body: data, token }),
    upload: (data: {
        name: string;
        dataset_version: string;
        language?: string;
        generation_method?: string;
        description?: string;
        categories?: string[];
        tasks: Array<{
            task_id: string;
            language?: string;
            contract_code: string;
            expected_vulnerabilities: Array<Record<string, unknown>>;
            difficulty: string;
            category: string;
            generation_method?: string;
            metadata_json?: Record<string, unknown>;
        }>;
    }, token: string) => request<DatasetRecord>('/datasets/upload', { method: 'POST', body: data, token }),
    list: (token: string) => request<Array<DatasetRecord>>('/datasets/', { token }),
    get: (id: string, token: string) => request<DatasetRecord>(`/datasets/${id}`, { token }),
    tasks: (id: string, token: string) => request<Array<DatasetTask>>(`/datasets/${id}/tasks`, { token }),
};

// -- Failures ---------------------------------------------------------------

export interface FailureRecord {
    id: string;
    evaluation_id: string;
    benchmark_run_id: string | null;
    task_id: string | null;
    failure_type: string;
    severity: string;
    vulnerability_type: string | null;
    confidence: number | null;
    details_json: Record<string, unknown> | null;
    created_at: string;
}

export interface FailureSummary {
    total_failures: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
    by_vulnerability_type: Record<string, number>;
}

export const failures = {
    list: (token: string, params?: { benchmark_id?: string; evaluation_id?: string; failure_type?: string; limit?: number }) => {
        const query = new URLSearchParams();
        if (params?.benchmark_id) query.set('benchmark_id', params.benchmark_id);
        if (params?.evaluation_id) query.set('evaluation_id', params.evaluation_id);
        if (params?.failure_type) query.set('failure_type', params.failure_type);
        if (params?.limit) query.set('limit', String(params.limit));
        return request<Array<FailureRecord>>(`/failures/${query.toString() ? `?${query.toString()}` : ''}`, { token });
    },
    summary: (token: string, benchmarkId?: string) =>
        request<FailureSummary>(`/failures/summary${benchmarkId ? `?benchmark_id=${benchmarkId}` : ''}`, { token }),
};

// -- Leaderboard ------------------------------------------------------------

export interface LeaderboardModel {
    rank: number;
    provider: string;
    model_name: string;
    reliability_score: number;
    hallucination_rate: number;
    miss_rate: number;
    average_latency_ms: number;
    benchmark_runs: number;
}

export const leaderboard = {
    models: (limit = 20) =>
        request<Array<LeaderboardModel>>(`/leaderboard/models?limit=${limit}`),
};

// ── Reports ───────────────────────────────────────────────────────

export const reports = {
    getJson: (evaluationId: string, token: string) =>
        request<Record<string, unknown>>(`/reports/evaluation/${evaluationId}/json`, { token }),
    getPdfUrl: (evaluationId: string) =>
        `${API_BASE}/reports/evaluation/${evaluationId}/pdf`,
};

export { ApiError };
