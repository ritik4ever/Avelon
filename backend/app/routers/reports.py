"""Report download endpoints: JSON and PDF."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Evaluation, Report, User
from app.schemas import ReportResponse

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/evaluation/{evaluation_id}", response_model=ReportResponse)
async def get_report(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get report metadata for an evaluation."""
    # Verify evaluation ownership
    eval_result = await db.execute(
        select(Evaluation).where(
            Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id
        )
    )
    if not eval_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")

    result = await db.execute(
        select(Report).where(Report.evaluation_id == evaluation_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not yet generated")
    return report


@router.get("/evaluation/{evaluation_id}/json")
async def download_json_report(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the full JSON report for an evaluation."""
    eval_result = await db.execute(
        select(Evaluation).where(
            Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id
        )
    )
    if not eval_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")

    result = await db.execute(
        select(Report).where(Report.evaluation_id == evaluation_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not yet generated")

    return JSONResponse(content=report.report_json)


@router.get("/evaluation/{evaluation_id}/pdf")
async def download_pdf_report(
    evaluation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the PDF security report for an evaluation."""
    eval_result = await db.execute(
        select(Evaluation).where(
            Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id
        )
    )
    if not eval_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")

    result = await db.execute(
        select(Report).where(Report.evaluation_id == evaluation_id)
    )
    report = result.scalar_one_or_none()
    if not report or not report.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF report not available")

    return FileResponse(
        path=report.pdf_path,
        media_type="application/pdf",
        filename=f"avelon_report_{evaluation_id}.pdf",
    )
