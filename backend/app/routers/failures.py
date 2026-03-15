"""Failure explorer endpoints."""

from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Evaluation, Failure, User
from app.schemas import FailureItem, FailureSummary

router = APIRouter(prefix="/failures", tags=["Failures"])


@router.get("/", response_model=list[FailureItem])
async def list_failures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    benchmark_id: uuid.UUID | None = None,
    evaluation_id: uuid.UUID | None = None,
    failure_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=2000),
):
    base = (
        select(Failure)
        .join(Evaluation, Failure.evaluation_id == Evaluation.id)
        .where(Evaluation.user_id == current_user.id)
        .order_by(Failure.created_at.desc())
        .limit(limit)
    )
    if benchmark_id:
        base = base.where(Failure.benchmark_run_id == benchmark_id)
    if evaluation_id:
        base = base.where(Failure.evaluation_id == evaluation_id)
    if failure_type:
        base = base.where(Failure.failure_type == failure_type)
    rows = await db.execute(base)
    return rows.scalars().all()


@router.get("/summary", response_model=FailureSummary)
async def failure_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    benchmark_id: uuid.UUID | None = None,
):
    base = select(Failure).join(Evaluation, Failure.evaluation_id == Evaluation.id).where(Evaluation.user_id == current_user.id)
    if benchmark_id:
        base = base.where(Failure.benchmark_run_id == benchmark_id)
    rows = (await db.execute(base)).scalars().all()

    by_type = Counter()
    by_severity = Counter()
    by_vuln = Counter()
    for row in rows:
        t = row.failure_type.value if hasattr(row.failure_type, "value") else str(row.failure_type)
        s = row.severity.value if hasattr(row.severity, "value") else str(row.severity)
        by_type[t] += 1
        by_severity[s] += 1
        if row.vulnerability_type:
            by_vuln[row.vulnerability_type] += 1

    return FailureSummary(
        total_failures=len(rows),
        by_type=dict(by_type),
        by_severity=dict(by_severity),
        by_vulnerability_type=dict(by_vuln),
    )
