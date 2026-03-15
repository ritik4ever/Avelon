"""SQLAlchemy ORM models for the Avelon red-team platform."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ContractStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PREPROCESSED = "preprocessed"
    FAILED = "failed"


class EvalStatus(str, enum.Enum):
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    AI_ANALYSIS = "ai_analysis"
    STATIC_ANALYSIS = "static_analysis"
    COMPARING = "comparing"
    SCORING = "scoring"
    REPORT_READY = "report_ready"
    FAILED = "failed"
    TIMEOUT = "timeout"


class VulnSource(str, enum.Enum):
    AI = "ai"
    SLITHER = "slither"
    MYTHRIL = "mythril"
    CURATED = "curated"


class SeverityLevel(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MatchClassification(str, enum.Enum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    UNMATCHED = "unmatched"


class BenchmarkStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComparisonStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DatasetStatus(str, enum.Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class TaskDifficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    ADVERSARIAL = "adversarial"


class TaskGenerationMethod(str, enum.Enum):
    TEMPLATE = "template"
    MUTATION = "mutation"
    FUZZING = "fuzzing"
    UPLOAD = "upload"
    MIXED = "mixed"


class FailureType(str, enum.Enum):
    HALLUCINATED_VULNERABILITY = "hallucinated_vulnerability"
    MISSED_VULNERABILITY = "missed_vulnerability"
    INCORRECT_REASONING_CHAIN = "incorrect_reasoning_chain"
    OVERCONFIDENCE = "overconfidence"
    PARTIAL_DETECTION = "partial_detection"
    MISIDENTIFIED_VULNERABILITY_TYPE = "misidentified_vulnerability_type"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    api_key_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contracts = relationship("Contract", back_populates="user", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="user", cascade="all, delete-orphan")
    benchmark_runs = relationship("BenchmarkRun", back_populates="user", cascade="all, delete-orphan")
    comparison_runs = relationship("ComparisonRun", back_populates="user", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="created_by_user", cascade="all, delete-orphan")
    models = relationship("ModelRegistry", back_populates="created_by_user")


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    dataset_version = Column(String(64), nullable=False, unique=True, index=True)
    language = Column(String(32), nullable=False, default="solidity")
    generation_method = Column(Enum(TaskGenerationMethod), default=TaskGenerationMethod.MIXED, nullable=False)
    status = Column(Enum(DatasetStatus), default=DatasetStatus.QUEUED, index=True)
    description = Column(Text, nullable=True)
    categories = Column(JSONB, nullable=True)
    task_count = Column(Integer, nullable=False, default=0)
    metadata_json = Column(JSONB, nullable=True)
    is_immutable = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by_user = relationship("User", back_populates="datasets")
    tasks = relationship("Task", back_populates="dataset", cascade="all, delete-orphan")
    benchmark_runs = relationship("BenchmarkRun", back_populates="dataset")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(128), nullable=False, unique=True, index=True)
    language = Column(String(32), nullable=False, default="solidity")
    contract_code = Column(Text, nullable=False)
    expected_vulnerabilities = Column(JSONB, nullable=False)
    difficulty = Column(Enum(TaskDifficulty), nullable=False, default=TaskDifficulty.MEDIUM, index=True)
    category = Column(String(128), nullable=False, index=True)
    generation_method = Column(Enum(TaskGenerationMethod), nullable=False, default=TaskGenerationMethod.TEMPLATE)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="tasks")
    evaluations = relationship("Evaluation", back_populates="task")
    benchmark_results = relationship("BenchmarkResult", back_populates="task")
    failures = relationship("Failure", back_populates="task")


class ModelRegistry(Base):
    __tablename__ = "models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(32), nullable=False, index=True)
    model_name = Column(String(128), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    api_base = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("provider", "model_name", "api_base", name="uq_model_provider_name_base"),)

    created_by_user = relationship("User", back_populates="models")
    evaluations = relationship("Evaluation", back_populates="model_profile")
    benchmark_runs = relationship("BenchmarkRun", back_populates="model_profile")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    original_source = Column(Text, nullable=False)
    flattened_source = Column(Text, nullable=True)
    solidity_version = Column(String(20), nullable=True)
    file_hash = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(Integer, nullable=False)
    status = Column(Enum(ContractStatus), default=ContractStatus.UPLOADED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="contracts")
    evaluations = relationship("Evaluation", back_populates="contract", cascade="all, delete-orphan")
    comparison_runs = relationship("ComparisonRun", back_populates="contract", cascade="all, delete-orphan")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(Enum(EvalStatus), default=EvalStatus.QUEUED, index=True)

    ai_provider = Column(String(50), nullable=False)
    ai_model = Column(String(100), nullable=False)
    ai_temperature = Column(Float, default=0.0)
    latency_ms = Column(Float, nullable=True)

    token_usage_prompt = Column(Integer, nullable=True)
    token_usage_completion = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)

    precision_score = Column(Float, nullable=True)
    recall_score = Column(Float, nullable=True)
    hallucination_rate = Column(Float, nullable=True)
    miss_rate = Column(Float, nullable=True)
    reliability_score = Column(Float, nullable=True)

    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="evaluations")
    contract = relationship("Contract", back_populates="evaluations")
    task = relationship("Task", back_populates="evaluations")
    model_profile = relationship("ModelRegistry", back_populates="evaluations")
    vulnerabilities = relationship("Vulnerability", back_populates="evaluation", cascade="all, delete-orphan")
    failures = relationship("Failure", back_populates="evaluation", cascade="all, delete-orphan")
    report = relationship("Report", back_populates="evaluation", uselist=False, cascade="all, delete-orphan")


class Vulnerability(Base):
    __tablename__ = "vulnerabilities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(Enum(VulnSource), nullable=False, index=True)
    vuln_type = Column(String(255), nullable=False)
    function_name = Column(String(255), nullable=True)
    line_number = Column(Integer, nullable=True)
    severity = Column(Enum(SeverityLevel), default=SeverityLevel.MEDIUM)
    confidence = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    match_classification = Column(Enum(MatchClassification), default=MatchClassification.UNMATCHED, index=True)
    matched_vuln_id = Column(UUID(as_uuid=True), ForeignKey("vulnerabilities.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    evaluation = relationship("Evaluation", back_populates="vulnerabilities")


class Failure(Base):
    __tablename__ = "failures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    benchmark_run_id = Column(UUID(as_uuid=True), ForeignKey("benchmark_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    failure_type = Column(Enum(FailureType), nullable=False, index=True)
    severity = Column(Enum(SeverityLevel), nullable=False, default=SeverityLevel.MEDIUM, index=True)
    vulnerability_type = Column(String(255), nullable=True, index=True)
    confidence = Column(Float, nullable=True)
    details_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    evaluation = relationship("Evaluation", back_populates="failures")
    benchmark_run = relationship("BenchmarkRun", back_populates="failures")
    task = relationship("Task", back_populates="failures")


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    report_json = Column(JSONB, nullable=False)
    pdf_path = Column(Text, nullable=True)
    reproducibility_hash = Column(String(64), nullable=False)
    analyzer_versions = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    evaluation = relationship("Evaluation", back_populates="report")


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id", ondelete="SET NULL"), nullable=True, index=True)
    ai_provider = Column(String(50), nullable=False)
    ai_model = Column(String(100), nullable=False)
    ai_temperature = Column(Float, default=0.0)
    status = Column(Enum(BenchmarkStatus), default=BenchmarkStatus.QUEUED, index=True)

    total_contracts = Column(Integer, default=0)
    completed_contracts = Column(Integer, default=0)
    avg_precision = Column(Float, nullable=True)
    avg_recall = Column(Float, nullable=True)
    avg_hallucination_rate = Column(Float, nullable=True)
    avg_miss_rate = Column(Float, nullable=True)
    avg_reliability_score = Column(Float, nullable=True)
    avg_latency_ms = Column(Float, nullable=True)
    category_performance = Column(JSONB, nullable=True)
    difficulty_performance = Column(JSONB, nullable=True)
    benchmark_summary = Column(Text, nullable=True)
    total_token_usage = Column(Integer, nullable=True)
    total_estimated_cost_usd = Column(Float, nullable=True)

    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="benchmark_runs")
    dataset = relationship("Dataset", back_populates="benchmark_runs")
    model_profile = relationship("ModelRegistry", back_populates="benchmark_runs")
    results = relationship("BenchmarkResult", back_populates="benchmark_run", cascade="all, delete-orphan")
    failures = relationship("Failure", back_populates="benchmark_run")


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    benchmark_run_id = Column(UUID(as_uuid=True), ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    difficulty = Column(Enum(TaskDifficulty), nullable=True, index=True)
    precision_score = Column(Float, nullable=True)
    recall_score = Column(Float, nullable=True)
    hallucination_rate = Column(Float, nullable=True)
    miss_rate = Column(Float, nullable=True)
    reliability_score = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    benchmark_run = relationship("BenchmarkRun", back_populates="results")
    task = relationship("Task", back_populates="benchmark_results")


class ComparisonRun(Base):
    __tablename__ = "comparison_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(ComparisonStatus), default=ComparisonStatus.QUEUED, index=True)
    total_models = Column(Integer, default=0)
    completed_models = Column(Integer, default=0)
    avg_precision = Column(Float, nullable=True)
    avg_recall = Column(Float, nullable=True)
    avg_hallucination_rate = Column(Float, nullable=True)
    avg_miss_rate = Column(Float, nullable=True)
    avg_reliability_score = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="comparison_runs")
    contract = relationship("Contract", back_populates="comparison_runs")
    results = relationship("ComparisonResult", back_populates="comparison_run", cascade="all, delete-orphan")


class ComparisonResult(Base):
    __tablename__ = "comparison_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comparison_run_id = Column(
        UUID(as_uuid=True), ForeignKey("comparison_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    ai_provider = Column(String(50), nullable=False)
    ai_model = Column(String(100), nullable=False)
    precision_score = Column(Float, nullable=True)
    recall_score = Column(Float, nullable=True)
    hallucination_rate = Column(Float, nullable=True)
    miss_rate = Column(Float, nullable=True)
    reliability_score = Column(Float, nullable=True)
    tp_count = Column(Integer, nullable=True)
    fp_count = Column(Integer, nullable=True)
    fn_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_comp_results_run_model", "comparison_run_id", "ai_provider", "ai_model"),
        UniqueConstraint("comparison_run_id", "ai_provider", "ai_model", name="uq_comp_run_model"),
    )

    comparison_run = relationship("ComparisonRun", back_populates="results")
