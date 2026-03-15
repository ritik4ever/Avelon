"""Evaluation endpoints: trigger, status, results with vulnerabilities."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Contract, Evaluation, EvalStatus, User, Vulnerability
from app.schemas import (
    EvaluationCreate,
    EvaluationListItem,
    EvaluationResponse,
    VulnerabilityItem,
)

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])


@router.post("/", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation(
    body: EvaluationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create and enqueue a new evaluation job."""
    # Verify the contract belongs to this user
    result = await db.execute(
        select(Contract).where(Contract.id == body.contract_id, Contract.user_id == current_user.id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    evaluation = Evaluation(
        user_id=current_user.id,
        contract_id=body.contract_id,
        ai_provider=body.ai_provider,
        ai_model=body.ai_model,
        ai_temperature=0.0,
        status=EvalStatus.QUEUED,
    )
    db.add(evaluation)
    await db.flush()
    await db.refresh(evaluation)

    # Dispatch Celery task (import here to avoid circular imports)
    from app.worker.tasks import run_evaluation

    run_evaluation.delay(
        str(evaluation.id),
        body.custom_api_key,
        body.custom_api_base,
    )

    return evaluation


@router.get("/", response_model=list[EvaluationListItem])
async def list_evaluations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List evaluations for the current user, optionally filtered by status."""
    query = select(Evaluation).where(Evaluation.user_id == current_user.id)
    if status_filter:
        query = query.where(Evaluation.status == status_filter)
    query = query.order_by(Evaluation.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get evaluation by ID."""
    result = await db.execute(
        select(Evaluation).where(
            Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id
        )
    )
    evaluation = result.scalar_one_or_none()
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    return evaluation


@router.get("/{evaluation_id}/vulnerabilities", response_model=list[VulnerabilityItem])
async def get_evaluation_vulnerabilities(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    source: Optional[str] = Query(None),
):
    """Get all vulnerabilities for an evaluation, optionally filtered by source."""
    # Verify ownership
    eval_result = await db.execute(
        select(Evaluation).where(
            Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id
        )
    )
    if not eval_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")

    query = select(Vulnerability).where(Vulnerability.evaluation_id == evaluation_id)
    if source:
        query = query.where(Vulnerability.source == source)
    query = query.order_by(Vulnerability.severity.desc(), Vulnerability.vuln_type)
    result = await db.execute(query)
    return result.scalars().all()
