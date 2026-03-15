"""Contract upload and listing endpoints."""

import hashlib
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Contract, ContractStatus, User
from app.schemas import ContractListItem, ContractUploadResponse

router = APIRouter(prefix="/contracts", tags=["Contracts"])

ALLOWED_EXTENSIONS = {".sol"}
MAX_FILE_SIZE = settings.max_file_size_mb * 1024 * 1024  # Convert MB to bytes


def _validate_file(filename: str, content: bytes) -> None:
    """Validate uploaded file: extension, size, basic MIME check."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only .sol files are allowed. Got: {ext}",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_file_size_mb}MB",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )
    # Basic content validation — should look like Solidity source
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not valid UTF-8 text",
        )
    if "pragma solidity" not in text.lower() and "// spdx-license-identifier" not in text.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File does not appear to be a Solidity contract",
        )


@router.post("/upload", response_model=ContractUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_contract(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a Solidity contract file."""
    content = await file.read()
    _validate_file(file.filename, content)

    file_hash = hashlib.sha256(content).hexdigest()
    source_text = content.decode("utf-8")

    # Save to disk
    upload_dir = os.path.join(settings.upload_dir, str(current_user.id))
    os.makedirs(upload_dir, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(upload_dir, stored_filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    contract = Contract(
        user_id=current_user.id,
        filename=file.filename,
        original_source=source_text,
        file_hash=file_hash,
        file_size_bytes=len(content),
        status=ContractStatus.UPLOADED,
    )
    db.add(contract)
    await db.flush()
    await db.refresh(contract)
    return contract


@router.get("/", response_model=list[ContractListItem])
async def list_contracts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    """List contracts uploaded by the current user."""
    result = await db.execute(
        select(Contract)
        .where(Contract.user_id == current_user.id)
        .order_by(Contract.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{contract_id}", response_model=ContractUploadResponse)
async def get_contract(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific contract by ID."""
    result = await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.user_id == current_user.id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    return contract
