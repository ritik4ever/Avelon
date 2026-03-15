"""Celery task pipeline for evaluations, benchmarks, comparisons, and datasets."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.worker.celery_app import celery_app

logger = get_task_logger(__name__)

sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
SyncSession = sessionmaker(bind=sync_engine)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _update_eval_status(session: Session, eval_id: str, status: str, error: str | None = None):
    from app.models import Evaluation

    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    if error:
        values["error_message"] = error
    if status in ("preprocessing", "ai_analysis"):
        values["started_at"] = datetime.now(timezone.utc)
    session.execute(update(Evaluation).where(Evaluation.id == eval_id).values(**values))
    session.commit()


def _load_curated_ground_truth(contract_hash: str) -> list[dict]:
    datasets_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "datasets",
        "ground_truth",
    )
    if not os.path.exists(datasets_dir):
        return []
    for filename in os.listdir(datasets_dir):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(datasets_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue
        if data.get("contract_hash") == contract_hash:
            return data.get("vulnerabilities", [])
    return []


def _vulnerability_category(vuln_type: str) -> str:
    value = (vuln_type or "").lower()
    if "reentr" in value:
        return "reentrancy"
    if "access" in value or "owner" in value or "auth" in value:
        return "access_control"
    if "overflow" in value or "underflow" in value or "arith" in value:
        return "arithmetic"
    if "flash" in value:
        return "flash_loan"
    if "storage" in value:
        return "storage_layout"
    if "delegate" in value or "proxy" in value:
        return "proxy_upgradeability"
    return "other"


def _new_stats() -> dict[str, dict[str, int]]:
    return defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})


def _finalize_stats(raw: dict[str, dict[str, int]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key, row in raw.items():
        tp = row["tp"]
        fp = row["fp"]
        fn = row["fn"]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        out[key] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "reliability": round(precision * recall, 4),
        }
    return out


def _sync_model(session: Session, provider: str, model_name: str, api_base: str | None, user_id):
    from app.models import ModelRegistry

    row = session.execute(
        select(ModelRegistry).where(
            ModelRegistry.provider == provider,
            ModelRegistry.model_name == model_name,
            ModelRegistry.api_base == api_base,
        )
    ).scalar_one_or_none()
    if row:
        return row
    row = ModelRegistry(
        provider=provider,
        model_name=model_name,
        display_name=f"{provider}:{model_name}",
        api_base=api_base,
        created_by=user_id,
    )
    session.add(row)
    session.flush()
    return row


def _store_vulnerabilities(session: Session, evaluation_id: str, ai_rows: list[dict], gt_rows: list[dict], comparison: dict):
    from app.models import MatchClassification, SeverityLevel, Vulnerability, VulnSource

    session.execute(delete(Vulnerability).where(Vulnerability.evaluation_id == evaluation_id))
    session.flush()

    for row in ai_rows:
        session.add(
            Vulnerability(
                evaluation_id=evaluation_id,
                source=VulnSource.AI.value,
                vuln_type=row["vuln_type"],
                function_name=row.get("function_name"),
                line_number=row.get("line_number"),
                severity=SeverityLevel((row.get("severity") or "medium").lower()),
                confidence=row.get("confidence"),
                description=row.get("description", ""),
                match_classification=MatchClassification(row.get("match_classification", "unmatched")),
            )
        )

    for row in gt_rows:
        source = row.get("source") or VulnSource.CURATED.value
        session.add(
            Vulnerability(
                evaluation_id=evaluation_id,
                source=source,
                vuln_type=row["vuln_type"],
                function_name=row.get("function_name"),
                line_number=row.get("line_number"),
                severity=SeverityLevel((row.get("severity") or "medium").lower()),
                confidence=row.get("confidence"),
                description=row.get("description", ""),
                match_classification=MatchClassification(row.get("match_classification", "unmatched")),
            )
        )

    session.flush()

    true_positive_ids = {
        (tp["ai_finding"]["vuln_type"], tp["ai_finding"].get("function_name"))
        for tp in comparison.get("true_positives", [])
    }
    false_positive_ids = {
        (fp["vuln_type"], fp.get("function_name"))
        for fp in comparison.get("false_positives", [])
    }
    false_negative_ids = {
        (fn["vuln_type"], fn.get("function_name"))
        for fn in comparison.get("false_negatives", [])
    }

    rows = session.execute(select(Vulnerability).where(Vulnerability.evaluation_id == evaluation_id)).scalars().all()
    for row in rows:
        key = (row.vuln_type, row.function_name)
        if row.source == VulnSource.AI and key in true_positive_ids:
            row.match_classification = MatchClassification.TRUE_POSITIVE
        elif row.source == VulnSource.AI and key in false_positive_ids:
            row.match_classification = MatchClassification.FALSE_POSITIVE
        elif row.source != VulnSource.AI and key in false_negative_ids:
            row.match_classification = MatchClassification.FALSE_NEGATIVE


def _classify_and_store_failures(session: Session, evaluation_id: str, benchmark_run_id, task_id, comparison: dict):
    from app.models import Failure, FailureType, SeverityLevel
    from app.services.failure_analyzer import classify_failures

    session.execute(delete(Failure).where(Failure.evaluation_id == evaluation_id))
    failures = classify_failures(comparison)
    for failure in failures:
        severity = (failure.get("severity") or "medium").lower()
        if severity not in {"info", "low", "medium", "high", "critical"}:
            severity = "medium"
        session.add(
            Failure(
                evaluation_id=evaluation_id,
                benchmark_run_id=benchmark_run_id,
                task_id=task_id,
                failure_type=FailureType(failure["failure_type"]),
                severity=SeverityLevel(severity),
                vulnerability_type=failure.get("vulnerability_type"),
                confidence=failure.get("confidence"),
                details_json=failure.get("details_json"),
            )
        )


def _score_by_difficulty(rows: list[dict]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row.get("difficulty") or "unknown"].append(row)
    out: dict[str, dict[str, float]] = {}
    for difficulty, entries in grouped.items():
        n = len(entries)
        out[difficulty] = {
            "count": n,
            "precision": round(sum(e["precision"] for e in entries) / n, 4),
            "recall": round(sum(e["recall"] for e in entries) / n, 4),
            "hallucination_rate": round(sum(e["hallucination"] for e in entries) / n, 4),
            "miss_rate": round(sum(e["miss"] for e in entries) / n, 4),
            "reliability": round(sum(e["reliability"] for e in entries) / n, 4),
        }
    return out


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, queue="evaluations")
def run_evaluation(
    self: Task,
    evaluation_id: str,
    custom_api_key: Optional[str] = None,
    custom_api_base: Optional[str] = None,
):
    """Execute full evaluation for one contract."""
    from app.models import Contract, ContractStatus, EvalStatus, Evaluation, Task as DatasetTask
    from app.services.ai_auditor import run_ai_audit
    from app.services.analyzer_client import run_static_analysis
    from app.services.comparator import compare_findings
    from app.services.normalizer import normalize_vulnerabilities
    from app.services.preprocessor import preprocess_contract
    from app.services.report_generator import generate_json_report, generate_pdf_report
    from app.services.scorer import compute_scores

    session = SyncSession()
    try:
        evaluation = session.execute(select(Evaluation).where(Evaluation.id == evaluation_id)).scalar_one_or_none()
        if not evaluation:
            return {"status": "error", "message": "evaluation_not_found"}

        contract = session.execute(select(Contract).where(Contract.id == evaluation.contract_id)).scalar_one_or_none()
        if not contract:
            _update_eval_status(session, evaluation_id, EvalStatus.FAILED.value, "contract_not_found")
            return {"status": "error", "message": "contract_not_found"}

        _update_eval_status(session, evaluation_id, EvalStatus.PREPROCESSING.value)
        preprocess = preprocess_contract(contract.original_source)
        contract.flattened_source = preprocess["flattened_source"]
        contract.solidity_version = preprocess["solidity_version"]
        contract.status = ContractStatus.PREPROCESSED.value
        session.commit()

        _update_eval_status(session, evaluation_id, EvalStatus.AI_ANALYSIS.value)
        evaluation.ai_temperature = 0.0
        ai_result = _run_async(
            run_ai_audit(
                contract_source=preprocess.get("cleaned_source", contract.original_source),
                provider=evaluation.ai_provider,
                model=evaluation.ai_model,
                temperature=0.0,
                api_key=custom_api_key,
                api_base=custom_api_base,
            )
        )
        evaluation.token_usage_prompt = ai_result.get("prompt_tokens", 0)
        evaluation.token_usage_completion = ai_result.get("completion_tokens", 0)
        evaluation.estimated_cost_usd = ai_result.get("estimated_cost", 0.0)
        evaluation.latency_ms = ai_result.get("latency_ms")
        session.commit()

        _update_eval_status(session, evaluation_id, EvalStatus.STATIC_ANALYSIS.value)
        static_result = _run_async(
            run_static_analysis(contract_source=contract.original_source, solidity_version=contract.solidity_version)
        )

        _update_eval_status(session, evaluation_id, EvalStatus.COMPARING.value)
        ai_normalized = normalize_vulnerabilities(ai_result["normalized_vulnerabilities"], "ai")
        slither_normalized = normalize_vulnerabilities(static_result.get("slither", []), "slither")
        mythril_normalized = normalize_vulnerabilities(static_result.get("mythril", []), "mythril")

        task = None
        if evaluation.task_id:
            task = session.execute(select(DatasetTask).where(DatasetTask.id == evaluation.task_id)).scalar_one_or_none()
        curated_rows = normalize_vulnerabilities(_load_curated_ground_truth(contract.file_hash), "curated")
        expected_rows = normalize_vulnerabilities(task.expected_vulnerabilities, "curated") if task else []

        if expected_rows:
            ground_truth = expected_rows
        else:
            dedupe = set()
            ground_truth = []
            for row in slither_normalized + mythril_normalized + curated_rows:
                key = (row["vuln_type"], row.get("function_name"))
                if key not in dedupe:
                    dedupe.add(key)
                    ground_truth.append(row)

        comparison = compare_findings(ai_normalized, ground_truth)
        _update_eval_status(session, evaluation_id, EvalStatus.SCORING.value)
        scores = compute_scores(comparison)

        evaluation.precision_score = scores["precision"]
        evaluation.recall_score = scores["recall"]
        evaluation.hallucination_rate = scores["hallucination_rate"]
        evaluation.miss_rate = scores["miss_rate"]
        evaluation.reliability_score = scores["weighted_reliability"]
        session.commit()

        _store_vulnerabilities(session, evaluation_id, ai_normalized, ground_truth, comparison)
        _classify_and_store_failures(
            session,
            evaluation_id=evaluation_id,
            benchmark_run_id=None,
            task_id=evaluation.task_id,
            comparison=comparison,
        )

        analyzer_versions = static_result.get("versions", {})
        report_json, reproducibility_hash = generate_json_report(
            evaluation_id=str(evaluation.id),
            contract_filename=contract.filename,
            contract_hash=contract.file_hash,
            ai_provider=evaluation.ai_provider,
            ai_model=evaluation.ai_model,
            ai_temperature=evaluation.ai_temperature,
            scores=scores,
            comparison=comparison,
            analyzer_versions=analyzer_versions,
        )
        reports_dir = os.path.join(settings.upload_dir, "reports")
        pdf_path = generate_pdf_report(report_json, reports_dir, str(evaluation.id))

        from app.models import Report

        session.execute(delete(Report).where(Report.evaluation_id == evaluation.id))
        session.add(
            Report(
                evaluation_id=evaluation.id,
                report_json=report_json,
                pdf_path=pdf_path,
                reproducibility_hash=reproducibility_hash,
                analyzer_versions=analyzer_versions,
            )
        )

        evaluation.status = EvalStatus.REPORT_READY
        evaluation.completed_at = datetime.now(timezone.utc)
        session.commit()
        return {"status": "success", "evaluation_id": str(evaluation.id)}
    except Exception as exc:
        session.rollback()
        logger.error(f"[{evaluation_id}] evaluation_failed: {exc}")
        try:
            _update_eval_status(session, evaluation_id, "failed", str(exc))
        except Exception:
            pass
        raise
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="benchmarks")
def run_benchmark(
    self: Task,
    benchmark_id: str,
    custom_api_key: Optional[str] = None,
    custom_api_base: Optional[str] = None,
):
    """Run full benchmark on either DB dataset tasks or legacy filesystem dataset."""
    from app.models import (
        BenchmarkResult,
        BenchmarkRun,
        BenchmarkStatus,
        Contract,
        ContractStatus,
        Evaluation,
        EvalStatus,
        Failure,
        Task as DatasetTask,
    )

    session = SyncSession()
    try:
        benchmark = session.execute(select(BenchmarkRun).where(BenchmarkRun.id == benchmark_id)).scalar_one_or_none()
        if not benchmark:
            return {"status": "error", "message": "benchmark_not_found"}

        benchmark.status = BenchmarkStatus.RUNNING
        benchmark.started_at = datetime.now(timezone.utc)
        model_profile = _sync_model(session, benchmark.ai_provider, benchmark.ai_model, custom_api_base, benchmark.user_id)
        benchmark.model_id = model_profile.id
        session.commit()

        tasks: list[DatasetTask] = []
        fallback_files: list[tuple[str, str]] = []
        if benchmark.dataset_id:
            tasks = session.execute(
                select(DatasetTask).where(DatasetTask.dataset_id == benchmark.dataset_id).order_by(DatasetTask.created_at.asc())
            ).scalars().all()
        if not tasks:
            datasets_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "datasets",
                "contracts",
            )
            if os.path.exists(datasets_dir):
                for filename in sorted(os.listdir(datasets_dir)):
                    if filename.endswith(".sol"):
                        with open(os.path.join(datasets_dir, filename), "r", encoding="utf-8") as handle:
                            fallback_files.append((filename, handle.read()))

        benchmark.total_contracts = len(tasks) if tasks else len(fallback_files)
        session.commit()

        score_rows: list[dict] = []
        category_totals = _new_stats()

        items = []
        if tasks:
            for task in tasks:
                items.append(
                    {
                        "filename": f"{task.task_id}.sol",
                        "source": task.contract_code,
                        "task_id": task.id,
                        "difficulty": task.difficulty.value if hasattr(task.difficulty, "value") else task.difficulty,
                    }
                )
        else:
            for filename, source in fallback_files:
                items.append({"filename": filename, "source": source, "task_id": None, "difficulty": None})

        for index, item in enumerate(items, start=1):
            source = item["source"]
            file_hash = hashlib.sha256(source.encode()).hexdigest()
            contract = Contract(
                user_id=benchmark.user_id,
                task_id=item["task_id"],
                filename=item["filename"],
                original_source=source,
                file_hash=file_hash,
                file_size_bytes=len(source.encode()),
                status=ContractStatus.UPLOADED,
            )
            session.add(contract)
            session.flush()

            evaluation = Evaluation(
                user_id=benchmark.user_id,
                contract_id=contract.id,
                task_id=item["task_id"],
                model_id=benchmark.model_id,
                ai_provider=benchmark.ai_provider,
                ai_model=benchmark.ai_model,
                ai_temperature=0.0,
                status=EvalStatus.QUEUED,
            )
            session.add(evaluation)
            session.flush()
            session.commit()

            run_evaluation.apply(args=[str(evaluation.id), custom_api_key, custom_api_base])
            evaluation = session.execute(select(Evaluation).where(Evaluation.id == evaluation.id)).scalar_one()

            session.add(
                BenchmarkResult(
                    benchmark_run_id=benchmark.id,
                    evaluation_id=evaluation.id,
                    contract_id=contract.id,
                    task_id=item["task_id"],
                    difficulty=item["difficulty"],
                    precision_score=evaluation.precision_score,
                    recall_score=evaluation.recall_score,
                    hallucination_rate=evaluation.hallucination_rate,
                    miss_rate=evaluation.miss_rate,
                    reliability_score=evaluation.reliability_score,
                    latency_ms=evaluation.latency_ms,
                )
            )
            session.execute(
                update(Failure)
                .where(Failure.evaluation_id == evaluation.id)
                .values(benchmark_run_id=benchmark.id)
            )
            benchmark.completed_contracts = index
            session.commit()

            score_rows.append(
                {
                    "precision": evaluation.precision_score or 0.0,
                    "recall": evaluation.recall_score or 0.0,
                    "hallucination": evaluation.hallucination_rate or 0.0,
                    "miss": evaluation.miss_rate or 0.0,
                    "reliability": evaluation.reliability_score or 0.0,
                    "latency": evaluation.latency_ms or 0.0,
                    "tokens": (evaluation.token_usage_prompt or 0) + (evaluation.token_usage_completion or 0),
                    "cost": evaluation.estimated_cost_usd or 0.0,
                    "difficulty": item["difficulty"] or "unknown",
                }
            )

            from app.models import Vulnerability, VulnSource

            vuln_rows = session.execute(select(Vulnerability).where(Vulnerability.evaluation_id == evaluation.id)).scalars().all()
            for row in vuln_rows:
                source_value = row.source.value if hasattr(row.source, "value") else row.source
                match_value = row.match_classification.value if hasattr(row.match_classification, "value") else row.match_classification
                category = _vulnerability_category(row.vuln_type)
                if source_value == VulnSource.AI.value and match_value == "true_positive":
                    category_totals[category]["tp"] += 1
                elif source_value == VulnSource.AI.value and match_value == "false_positive":
                    category_totals[category]["fp"] += 1
                elif source_value != VulnSource.AI.value and match_value == "false_negative":
                    category_totals[category]["fn"] += 1

        if score_rows:
            n = len(score_rows)
            benchmark.avg_precision = sum(r["precision"] for r in score_rows) / n
            benchmark.avg_recall = sum(r["recall"] for r in score_rows) / n
            benchmark.avg_hallucination_rate = sum(r["hallucination"] for r in score_rows) / n
            benchmark.avg_miss_rate = sum(r["miss"] for r in score_rows) / n
            benchmark.avg_reliability_score = sum(r["reliability"] for r in score_rows) / n
            benchmark.avg_latency_ms = sum(r["latency"] for r in score_rows) / n
            benchmark.total_token_usage = int(sum(r["tokens"] for r in score_rows))
            benchmark.total_estimated_cost_usd = float(sum(r["cost"] for r in score_rows))
            benchmark.category_performance = _finalize_stats(dict(category_totals))
            benchmark.difficulty_performance = _score_by_difficulty(score_rows)
            benchmark.benchmark_summary = (
                f"{benchmark.ai_model} reliability on adversarial smart contracts: "
                f"{(benchmark.avg_reliability_score or 0.0) * 100:.1f}%"
            )

        benchmark.status = BenchmarkStatus.COMPLETED
        benchmark.completed_at = datetime.now(timezone.utc)
        session.commit()
        return {"status": "success", "benchmark_id": str(benchmark.id)}
    except Exception as exc:
        session.rollback()
        logger.error(f"[{benchmark_id}] benchmark_failed: {exc}")
        try:
            benchmark = session.execute(select(BenchmarkRun).where(BenchmarkRun.id == benchmark_id)).scalar_one_or_none()
            if benchmark:
                benchmark.status = BenchmarkStatus.FAILED
                benchmark.error_message = str(exc)
                session.commit()
        except Exception:
            pass
        raise
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30, queue="evaluations")
def run_comparison(self: Task, comparison_id: str, models: list[dict]):
    """Run multi-model comparison on one contract."""
    from app.models import (
        ComparisonResult,
        ComparisonRun,
        ComparisonStatus,
        Evaluation,
        EvalStatus,
    )

    session = SyncSession()
    try:
        comparison = session.execute(select(ComparisonRun).where(ComparisonRun.id == comparison_id)).scalar_one_or_none()
        if not comparison:
            return {"status": "error", "message": "comparison_not_found"}

        comparison.status = ComparisonStatus.RUNNING
        comparison.started_at = datetime.now(timezone.utc)
        comparison.total_models = len(models)
        comparison.completed_models = 0
        session.commit()

        score_rows: list[dict] = []
        for index, target in enumerate(models, start=1):
            model_profile = _sync_model(
                session,
                target["ai_provider"],
                target["ai_model"],
                target.get("custom_api_base"),
                comparison.user_id,
            )
            evaluation = Evaluation(
                user_id=comparison.user_id,
                contract_id=comparison.contract_id,
                model_id=model_profile.id,
                ai_provider=target["ai_provider"],
                ai_model=target["ai_model"],
                ai_temperature=0.0,
                status=EvalStatus.QUEUED,
            )
            session.add(evaluation)
            session.flush()
            session.commit()

            run_evaluation.apply(args=[str(evaluation.id), target.get("custom_api_key"), target.get("custom_api_base")])
            evaluation = session.execute(select(Evaluation).where(Evaluation.id == evaluation.id)).scalar_one()

            from app.models import Vulnerability, VulnSource

            rows = session.execute(select(Vulnerability).where(Vulnerability.evaluation_id == evaluation.id)).scalars().all()
            tp = fp = fn = 0
            for row in rows:
                source_value = row.source.value if hasattr(row.source, "value") else row.source
                match_value = row.match_classification.value if hasattr(row.match_classification, "value") else row.match_classification
                if source_value == VulnSource.AI.value and match_value == "true_positive":
                    tp += 1
                elif source_value == VulnSource.AI.value and match_value == "false_positive":
                    fp += 1
                elif source_value != VulnSource.AI.value and match_value == "false_negative":
                    fn += 1

            session.add(
                ComparisonResult(
                    comparison_run_id=comparison.id,
                    evaluation_id=evaluation.id,
                    ai_provider=target["ai_provider"],
                    ai_model=target["ai_model"],
                    precision_score=evaluation.precision_score,
                    recall_score=evaluation.recall_score,
                    hallucination_rate=evaluation.hallucination_rate,
                    miss_rate=evaluation.miss_rate,
                    reliability_score=evaluation.reliability_score,
                    tp_count=tp,
                    fp_count=fp,
                    fn_count=fn,
                )
            )
            comparison.completed_models = index
            session.commit()

            score_rows.append(
                {
                    "precision": evaluation.precision_score or 0.0,
                    "recall": evaluation.recall_score or 0.0,
                    "hallucination": evaluation.hallucination_rate or 0.0,
                    "miss": evaluation.miss_rate or 0.0,
                    "reliability": evaluation.reliability_score or 0.0,
                }
            )

        if score_rows:
            n = len(score_rows)
            comparison.avg_precision = sum(r["precision"] for r in score_rows) / n
            comparison.avg_recall = sum(r["recall"] for r in score_rows) / n
            comparison.avg_hallucination_rate = sum(r["hallucination"] for r in score_rows) / n
            comparison.avg_miss_rate = sum(r["miss"] for r in score_rows) / n
            comparison.avg_reliability_score = sum(r["reliability"] for r in score_rows) / n

        comparison.status = ComparisonStatus.COMPLETED
        comparison.completed_at = datetime.now(timezone.utc)
        session.commit()
        return {"status": "success", "comparison_id": comparison_id}
    except Exception as exc:
        session.rollback()
        logger.error(f"[{comparison_id}] comparison_failed: {exc}")
        try:
            comparison = session.execute(select(ComparisonRun).where(ComparisonRun.id == comparison_id)).scalar_one_or_none()
            if comparison:
                comparison.status = ComparisonStatus.FAILED
                comparison.error_message = str(exc)
                session.commit()
        except Exception:
            pass
        raise
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30, queue="datasets")
def run_dataset_generation(
    self: Task,
    dataset_id: str,
    task_count: int,
    generation_method: str,
    categories: list[str],
    difficulty_mix: dict[str, float],
    seed: Optional[int],
):
    """Generate immutable adversarial dataset tasks."""
    from app.models import Dataset, DatasetStatus, Task as DatasetTask, TaskDifficulty, TaskGenerationMethod
    from app.services.task_generator import generate_adversarial_tasks

    session = SyncSession()
    try:
        dataset = session.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
        if not dataset:
            return {"status": "error", "message": "dataset_not_found"}

        dataset.status = DatasetStatus.GENERATING
        session.commit()

        generated = generate_adversarial_tasks(
            dataset_version=dataset.dataset_version,
            language=dataset.language,
            task_count=task_count,
            generation_method=generation_method,
            categories=categories,
            difficulty_mix=difficulty_mix,
            seed=seed,
        )

        session.execute(delete(DatasetTask).where(DatasetTask.dataset_id == dataset.id))
        for task in generated:
            session.add(
                DatasetTask(
                    dataset_id=dataset.id,
                    task_id=task.task_id,
                    language=task.language,
                    contract_code=task.contract_code,
                    expected_vulnerabilities=task.expected_vulnerabilities,
                    difficulty=TaskDifficulty(task.difficulty),
                    category=task.category,
                    generation_method=TaskGenerationMethod(task.generation_method),
                    metadata_json=task.metadata_json,
                )
            )

        dataset.task_count = len(generated)
        dataset.categories = {"values": sorted({t.category for t in generated})}
        dataset.metadata_json = {
            "generation_method": generation_method,
            "seed": seed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        dataset.status = DatasetStatus.READY
        session.commit()
        return {"status": "success", "dataset_id": dataset_id, "task_count": len(generated)}
    except Exception as exc:
        session.rollback()
        logger.error(f"[{dataset_id}] dataset_generation_failed: {exc}")
        try:
            dataset = session.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
            if dataset:
                dataset.status = DatasetStatus.FAILED
                dataset.metadata_json = {"error": str(exc)}
                session.commit()
        except Exception:
            pass
        raise
    finally:
        session.close()
