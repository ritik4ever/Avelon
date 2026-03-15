"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


PROVIDER_PATTERN = "^(openai|anthropic|google|custom)$"
GENERATION_PATTERN = "^(template|mutation|fuzzing|upload|mixed)$"
DIFFICULTY_PATTERN = "^(easy|medium|hard|adversarial)$"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ContractUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_hash: str
    file_size_bytes: int
    solidity_version: Optional[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContractListItem(BaseModel):
    id: uuid.UUID
    filename: str
    file_hash: str
    file_size_bytes: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationCreate(BaseModel):
    contract_id: uuid.UUID
    ai_provider: str = Field(default="openai", pattern=PROVIDER_PATTERN)
    ai_model: str = Field(default="gpt-4o")
    ai_temperature: float = Field(default=0.0, ge=0.0, le=0.2)
    custom_api_key: Optional[str] = None
    custom_api_base: Optional[str] = None


class EvaluationResponse(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    task_id: Optional[uuid.UUID]
    model_id: Optional[uuid.UUID]
    status: str
    ai_provider: str
    ai_model: str
    ai_temperature: float
    latency_ms: Optional[float]
    precision_score: Optional[float]
    recall_score: Optional[float]
    hallucination_rate: Optional[float]
    miss_rate: Optional[float]
    reliability_score: Optional[float]
    token_usage_prompt: Optional[int]
    token_usage_completion: Optional[int]
    estimated_cost_usd: Optional[float]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationListItem(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    status: str
    ai_provider: str
    ai_model: str
    reliability_score: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class VulnerabilityItem(BaseModel):
    id: uuid.UUID
    source: str
    vuln_type: str
    function_name: Optional[str]
    line_number: Optional[int]
    severity: str
    confidence: Optional[float]
    description: Optional[str]
    match_classification: str

    model_config = {"from_attributes": True}


class BenchmarkCreate(BaseModel):
    ai_provider: str = Field(default="openai", pattern=PROVIDER_PATTERN)
    ai_model: str = Field(default="gpt-4o")
    dataset_id: Optional[uuid.UUID] = None
    ai_temperature: float = Field(default=0.0, ge=0.0, le=0.2)
    custom_api_key: Optional[str] = None
    custom_api_base: Optional[str] = None


class BenchmarkRunResponse(BaseModel):
    id: uuid.UUID
    dataset_id: Optional[uuid.UUID]
    model_id: Optional[uuid.UUID]
    ai_provider: str
    ai_model: str
    ai_temperature: float
    status: str
    total_contracts: int
    completed_contracts: int
    avg_precision: Optional[float]
    avg_recall: Optional[float]
    avg_hallucination_rate: Optional[float]
    avg_miss_rate: Optional[float]
    avg_reliability_score: Optional[float]
    avg_latency_ms: Optional[float]
    category_performance: Optional[dict]
    difficulty_performance: Optional[dict]
    benchmark_summary: Optional[str]
    total_token_usage: Optional[int]
    total_estimated_cost_usd: Optional[float]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class BenchmarkResultItem(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    task_id: Optional[uuid.UUID]
    difficulty: Optional[str]
    precision_score: Optional[float]
    recall_score: Optional[float]
    hallucination_rate: Optional[float]
    miss_rate: Optional[float]
    reliability_score: Optional[float]
    latency_ms: Optional[float]

    model_config = {"from_attributes": True}


class ComparisonModelTarget(BaseModel):
    ai_provider: str = Field(pattern=PROVIDER_PATTERN)
    ai_model: str = Field(min_length=1, max_length=100)
    custom_api_key: Optional[str] = None
    custom_api_base: Optional[str] = None


class ComparisonCreate(BaseModel):
    contract_id: uuid.UUID
    models: list[ComparisonModelTarget] = Field(min_length=2, max_length=12)
    ai_temperature: float = Field(default=0.0, ge=0.0, le=0.2)


class ComparisonRunResponse(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    status: str
    total_models: int
    completed_models: int
    avg_precision: Optional[float]
    avg_recall: Optional[float]
    avg_hallucination_rate: Optional[float]
    avg_miss_rate: Optional[float]
    avg_reliability_score: Optional[float]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ComparisonResultItem(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    ai_provider: str
    ai_model: str
    precision_score: Optional[float]
    recall_score: Optional[float]
    hallucination_rate: Optional[float]
    miss_rate: Optional[float]
    reliability_score: Optional[float]
    tp_count: Optional[int]
    fp_count: Optional[int]
    fn_count: Optional[int]

    model_config = {"from_attributes": True}


class DatasetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    dataset_version: Optional[str] = Field(default=None, max_length=64)
    language: str = Field(default="solidity", max_length=32)
    generation_method: str = Field(default="mixed", pattern=GENERATION_PATTERN)
    description: Optional[str] = None
    task_count: int = Field(default=40, ge=1, le=5000)
    categories: list[str] = Field(default_factory=list)
    difficulty_mix: dict[str, float] = Field(default_factory=dict)
    seed: Optional[int] = None


class TaskUploadItem(BaseModel):
    task_id: str = Field(min_length=3, max_length=128)
    language: str = Field(default="solidity", max_length=32)
    contract_code: str = Field(min_length=10)
    expected_vulnerabilities: list[dict] = Field(default_factory=list)
    difficulty: str = Field(default="medium", pattern=DIFFICULTY_PATTERN)
    category: str = Field(min_length=2, max_length=128)
    generation_method: str = Field(default="upload", pattern=GENERATION_PATTERN)
    metadata_json: Optional[dict] = None


class DatasetUpload(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    dataset_version: str = Field(min_length=3, max_length=64)
    language: str = Field(default="solidity", max_length=32)
    generation_method: str = Field(default="upload", pattern=GENERATION_PATTERN)
    description: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    tasks: list[TaskUploadItem] = Field(min_length=1)


class DatasetResponse(BaseModel):
    id: uuid.UUID
    name: str
    dataset_version: str
    language: str
    generation_method: str
    status: str
    description: Optional[str]
    categories: Optional[dict]
    task_count: int
    metadata_json: Optional[dict]
    is_immutable: bool
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    task_id: str
    language: str
    contract_code: str
    expected_vulnerabilities: list[dict]
    difficulty: str
    category: str
    generation_method: str
    metadata_json: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DatasetGenerationAccepted(BaseModel):
    dataset: DatasetResponse
    job_id: str


class FailureItem(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    benchmark_run_id: Optional[uuid.UUID]
    task_id: Optional[uuid.UUID]
    failure_type: str
    severity: str
    vulnerability_type: Optional[str]
    confidence: Optional[float]
    details_json: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class FailureSummary(BaseModel):
    total_failures: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    by_vulnerability_type: dict[str, int]


class LeaderboardEntry(BaseModel):
    rank: int
    provider: str
    model_name: str
    reliability_score: float
    hallucination_rate: float
    miss_rate: float
    average_latency_ms: float
    benchmark_runs: int


class ReportResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    reproducibility_hash: str
    analyzer_versions: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
