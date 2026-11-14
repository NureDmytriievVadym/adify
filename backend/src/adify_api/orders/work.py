"""ADY-022: work stages and evidence on an order (FR-037, FR-041).

Either participant can add a stage, mark it complete, or reopen it while the order is in
progress or in review. Stages are frozen while the order is disputed and in final states.
Evidence accepts a note, files, or both; every file is scanned for malware before it is
stored, and delivery limits are the interim rules documented in story-22.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.models import Account
from adify_api.core import malware, storage
from adify_api.core.config import get_settings
from adify_api.orders.models import (
    Order,
    OrderEvidence,
    OrderEvidenceFile,
    OrderStage,
    OrderStatus,
)
from adify_api.orders.schemas import StageInput
from adify_api.orders.service import OrderError

# FR-037, FR-041: work and evidence belong to active working states only.
WORKABLE_STATES = frozenset({OrderStatus.IN_PROGRESS, OrderStatus.IN_REVIEW})
STAGE_LIMIT = 10
NOTE_LIMIT = 2000


def _participant(order: Order, account: Account) -> None:
    if account.id not in (order.customer_id, order.provider_id):
        raise OrderError(
            403, "not_order_participant", "Only the two order participants can do this."
        )


async def _lock_workable(session: AsyncSession, order: Order) -> None:
    # Both participants can change stages; the row lock serializes their clicks.
    await session.refresh(order, with_for_update=True)
    if order.status not in WORKABLE_STATES:
        raise OrderError(
            409,
            "order_not_workable",
            "Stages and evidence can be changed only while the order is in progress or in review.",
        )


def _stage(order: Order, stage_id: uuid.UUID) -> OrderStage:
    stage = next((item for item in order.stages if item.id == stage_id), None)
    if stage is None:
        raise OrderError(404, "stage_not_found", "This work stage could not be found.")
    return stage


async def add_stage(
    session: AsyncSession, order: Order, account: Account, data: StageInput
) -> Order:
    """FR-037: either participant adds a stage with an optional deadline."""
    _participant(order, account)
    await _lock_workable(session, order)
    if len(order.stages) >= STAGE_LIMIT:
        raise OrderError(
            409, "stage_limit", f"An order can have at most {STAGE_LIMIT} work stages."
        )
    if order.deadline and data.deadline and data.deadline > order.deadline:
        raise OrderError(
            422,
            "stage_deadline_after_order",
            "A stage deadline cannot be later than the order deadline.",
        )
    order.stages.append(
        OrderStage(position=len(order.stages), title=data.title, deadline=data.deadline)
    )
    await session.commit()
    return order


async def complete_stage(
    session: AsyncSession, order: Order, account: Account, stage_id: uuid.UUID
) -> Order:
    """FR-037: either participant marks a stage as done."""
    _participant(order, account)
    await _lock_workable(session, order)
    stage = _stage(order, stage_id)
    if stage.completed_at is not None:
        raise OrderError(409, "stage_already_completed", "This stage is already complete.")
    stage.completed_at = datetime.now(UTC)
    stage.completed_by = account
    await session.commit()
    return order


async def reopen_stage(
    session: AsyncSession, order: Order, account: Account, stage_id: uuid.UUID
) -> Order:
    """FR-037: either participant reopens a completed stage."""
    _participant(order, account)
    await _lock_workable(session, order)
    stage = _stage(order, stage_id)
    if stage.completed_at is None:
        raise OrderError(409, "stage_not_completed", "This stage is not complete.")
    stage.completed_at = None
    stage.completed_by = None
    await session.commit()
    return order


async def add_evidence(
    session: AsyncSession,
    order: Order,
    account: Account,
    note: str | None,
    files: list[tuple[str, bytes]],
) -> Order:
    """FR-041: text, files, or both; each file is scanned before anything is stored."""
    _participant(order, account)
    await _lock_workable(session, order)
    settings = get_settings()
    clean_note = (note or "").strip() or None
    if clean_note and len(clean_note) > NOTE_LIMIT:
        raise OrderError(
            422, "evidence_note_too_long", f"Keep the evidence note within {NOTE_LIMIT} characters."
        )
    if not clean_note and not files:
        raise OrderError(422, "evidence_empty", "Add a note or at least one file.")
    if len(files) > settings.max_evidence_files:
        raise OrderError(
            422,
            "too_many_evidence_files",
            f"Attach at most {settings.max_evidence_files} files.",
        )

    prepared: list[OrderEvidenceFile] = []
    for filename, data in files:
        if not data:
            raise OrderError(422, "evidence_file_empty", f"{filename}: the file is empty.")
        if len(data) > settings.max_evidence_bytes:
            megabytes = settings.max_evidence_bytes // (1024 * 1024)
            raise OrderError(
                413,
                "evidence_file_too_large",
                f"{filename}: a file can be at most {megabytes} MB.",
            )
        try:
            signature = await malware.scan(data)
        except malware.ScanError:
            raise OrderError(
                503,
                "malware_scan_unavailable",
                "The malware scanner is unavailable. Try the upload again later.",
            ) from None
        if signature:
            raise OrderError(
                422,
                "malware_detected",
                f"{filename}: rejected by the malware scan ({signature}).",
            )
        content_type = storage.sniff_content_type(data) or (
            "text/plain" if storage.looks_like_text(data) else "application/octet-stream"
        )
        prepared.append(
            OrderEvidenceFile(
                id=uuid.uuid4(),
                filename=storage.clean_filename(filename),
                content_type=content_type,
                size=len(data),
                checksum=hashlib.sha256(data).hexdigest(),
                scan_result="clean",
            )
        )

    evidence = OrderEvidence(
        order_id=order.id,
        author=account,
        note=clean_note,
        files=prepared,
        created_at=datetime.now(UTC),
    )
    saved: list[uuid.UUID] = []
    try:
        for item, (_, data) in zip(prepared, files, strict=True):
            await storage.save(item.id, data)
            saved.append(item.id)
        order.evidence.append(evidence)
        await session.commit()
    except Exception:
        await session.rollback()
        for file_id in saved:
            await storage.remove(file_id)
        raise
    return order


def evidence_file(order: Order, evidence_id: uuid.UUID, file_id: uuid.UUID) -> OrderEvidenceFile:
    evidence = next((item for item in order.evidence if item.id == evidence_id), None)
    if evidence is None:
        raise OrderError(404, "evidence_not_found", "This evidence submission could not be found.")
    file = next((item for item in evidence.files if item.id == file_id), None)
    if file is None:
        raise OrderError(404, "evidence_file_not_found", "This evidence file could not be found.")
    return file
