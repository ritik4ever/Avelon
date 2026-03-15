"""Dataset manager endpoints for adversarial task datasets."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Dataset, DatasetStatus, Task, TaskDifficulty, TaskGenerationMethod, User
from app.schemas import (
    DatasetCreate,
    DatasetGenerationAccepted,
    DatasetResponse,
    DatasetUpload,
    TaskResponse,
)
from app.worker.tasks import run_dataset_generation

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post("/generate", response_model=DatasetGenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def generate_dataset(
    body: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset_version = body.dataset_version or f"{body.name.lower().replace(' ', '-')}-v{uuid.uuid4().hex[:8]}"

    existing = await db.execute(select(Dataset).where(Dataset.dataset_version == dataset_version))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="dataset_version already exists")

    dataset = Dataset(
        name=body.name,
        dataset_version=dataset_version,
        language=body.language,
        generation_method=body.generation_method,
        status=DatasetStatus.QUEUED,
        description=body.description,
        categories={"values": body.categories},
        task_count=0,
        metadata_json={"difficulty_mix": body.difficulty_mix, "seed": body.seed},
        is_immutable=True,
        created_by=current_user.id,
    )
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)

    async_job = run_dataset_generation.delay(
        str(dataset.id),
        body.task_count,
        body.generation_method,
        body.categories,
        body.difficulty_mix,
        body.seed,
    )
    return DatasetGenerationAccepted(dataset=dataset, job_id=async_job.id)


@router.post("/upload", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    body: DatasetUpload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(select(Dataset).where(Dataset.dataset_version == body.dataset_version))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="dataset_version already exists")

    dataset = Dataset(
        name=body.name,
        dataset_version=body.dataset_version,
        language=body.language,
        generation_method=body.generation_method,
        status=DatasetStatus.READY,
        description=body.description,
        categories={"values": body.categories},
        task_count=len(body.tasks),
        metadata_json={"source": "uploaded"},
        is_immutable=True,
        created_by=current_user.id,
    )
    db.add(dataset)
    await db.flush()

    for task in body.tasks:
        db.add(
            Task(
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

    await db.flush()
    await db.refresh(dataset)
    return dataset


@router.get("/", response_model=list[DatasetResponse])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    result = await db.execute(
        select(Dataset)
        .where(Dataset.created_by == current_user.id)
        .order_by(Dataset.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


@router.get("/{dataset_id}/tasks", response_model=list[TaskResponse])
async def list_dataset_tasks(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 200,
):
    dataset_row = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    if not dataset_row.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    tasks = await db.execute(
        select(Task)
        .where(Task.dataset_id == dataset_id)
        .order_by(Task.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return tasks.scalars().all()
