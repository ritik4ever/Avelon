"""Benchmark endpoints: trigger model benchmark, list runs, get results."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import BenchmarkResult, BenchmarkRun, BenchmarkStatus, Dataset, ModelRegistry, User
from app.schemas import BenchmarkCreate, BenchmarkResultItem, BenchmarkRunResponse

router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])


@router.post("/", response_model=BenchmarkRunResponse, status_code=status.HTTP_201_CREATED)
async def create_benchmark(
    body: BenchmarkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a full model benchmark against the curated contract dataset."""
    model_profile_row = await db.execute(
        select(ModelRegistry).where(
            ModelRegistry.provider == body.ai_provider,
            ModelRegistry.model_name == body.ai_model,
            ModelRegistry.api_base == body.custom_api_base,
        )
    )
    model_profile = model_profile_row.scalar_one_or_none()
    if not model_profile:
        model_profile = ModelRegistry(
            provider=body.ai_provider,
            model_name=body.ai_model,
            display_name=f"{body.ai_provider}:{body.ai_model}",
            api_base=body.custom_api_base,
            created_by=current_user.id,
        )
        db.add(model_profile)
        await db.flush()

    dataset_id = body.dataset_id
    if dataset_id:
        dataset_row = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        if not dataset_row.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    benchmark = BenchmarkRun(
        user_id=current_user.id,
        dataset_id=dataset_id,
        model_id=model_profile.id,
        ai_provider=body.ai_provider,
        ai_model=body.ai_model,
        ai_temperature=0.0,
        status=BenchmarkStatus.QUEUED,
    )
    db.add(benchmark)
    await db.flush()
    await db.refresh(benchmark)

    # Dispatch Celery task
    from app.worker.tasks import run_benchmark

    run_benchmark.delay(
        str(benchmark.id),
        body.custom_api_key,
        body.custom_api_base,
    )

    return benchmark


@router.get("/", response_model=list[BenchmarkRunResponse])
async def list_benchmarks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20,
):
    """List all benchmark runs for the current user."""
    result = await db.execute(
        select(BenchmarkRun)
        .where(BenchmarkRun.user_id == current_user.id)
        .order_by(BenchmarkRun.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{benchmark_id}", response_model=BenchmarkRunResponse)
async def get_benchmark(
    benchmark_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific benchmark run by ID."""
    result = await db.execute(
        select(BenchmarkRun).where(
            BenchmarkRun.id == benchmark_id, BenchmarkRun.user_id == current_user.id
        )
    )
    benchmark = result.scalar_one_or_none()
    if not benchmark:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark not found")
    return benchmark


@router.get("/{benchmark_id}/results", response_model=list[BenchmarkResultItem])
async def get_benchmark_results(
    benchmark_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get per-contract results for a benchmark run."""
    # Verify ownership
    bench_result = await db.execute(
        select(BenchmarkRun).where(
            BenchmarkRun.id == benchmark_id, BenchmarkRun.user_id == current_user.id
        )
    )
    if not bench_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark not found")

    result = await db.execute(
        select(BenchmarkResult)
        .where(BenchmarkResult.benchmark_run_id == benchmark_id)
        .order_by(BenchmarkResult.reliability_score.desc().nullslast())
    )
    return result.scalars().all()
