"""Model comparison endpoints: run and compare multiple models on one contract."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import ComparisonResult, ComparisonRun, ComparisonStatus, Contract, User
from app.schemas import (
    ComparisonCreate,
    ComparisonResultItem,
    ComparisonRunResponse,
)

router = APIRouter(prefix="/comparisons", tags=["Comparisons"])


@router.post("/", response_model=ComparisonRunResponse, status_code=status.HTTP_201_CREATED)
async def create_comparison(
    body: ComparisonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a multi-model reliability comparison against the same contract."""
    contract_result = await db.execute(
        select(Contract).where(Contract.id == body.contract_id, Contract.user_id == current_user.id)
    )
    contract = contract_result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    deduped_models: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for model in body.models:
        key = (model.ai_provider, model.ai_model.strip())
        if key in seen:
            continue
        seen.add(key)
        deduped_models.append({
            "ai_provider": model.ai_provider,
            "ai_model": model.ai_model.strip(),
            "custom_api_key": model.custom_api_key,
            "custom_api_base": model.custom_api_base,
        })

    if len(deduped_models) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two unique models are required for comparison",
        )

    comparison = ComparisonRun(
        user_id=current_user.id,
        contract_id=contract.id,
        status=ComparisonStatus.QUEUED,
        total_models=len(deduped_models),
    )
    db.add(comparison)
    await db.flush()
    await db.refresh(comparison)

    from app.worker.tasks import run_comparison

    run_comparison.delay(str(comparison.id), deduped_models)
    return comparison


@router.get("/", response_model=list[ComparisonRunResponse])
async def list_comparisons(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20,
):
    """List all model comparison runs for the current user."""
    result = await db.execute(
        select(ComparisonRun)
        .where(ComparisonRun.user_id == current_user.id)
        .order_by(ComparisonRun.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{comparison_id}", response_model=ComparisonRunResponse)
async def get_comparison(
    comparison_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific comparison run."""
    result = await db.execute(
        select(ComparisonRun).where(
            ComparisonRun.id == comparison_id,
            ComparisonRun.user_id == current_user.id,
        )
    )
    comparison = result.scalar_one_or_none()
    if not comparison:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found")
    return comparison


@router.get("/{comparison_id}/results", response_model=list[ComparisonResultItem])
async def get_comparison_results(
    comparison_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get per-model comparison metrics for one comparison run."""
    result = await db.execute(
        select(ComparisonRun).where(
            ComparisonRun.id == comparison_id,
            ComparisonRun.user_id == current_user.id,
        )
    )
    comparison = result.scalar_one_or_none()
    if not comparison:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found")

    rows = await db.execute(
        select(ComparisonResult)
        .where(ComparisonResult.comparison_run_id == comparison_id)
        .order_by(ComparisonResult.reliability_score.desc().nullslast())
    )
    return rows.scalars().all()
