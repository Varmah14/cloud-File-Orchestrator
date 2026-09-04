import datetime as dt
from enum import Enum
from typing import Any, Optional

from google.cloud import firestore
from google.cloud.firestore import AsyncClient, async_transactional
from google.cloud.firestore_v1.async_transaction import AsyncTransaction

from common.config import JOBS_COLLECTION

STAGE_ORDER = {
    "PENDING": 0,
    "INSPECTED": 1,
    "CLASSIFIED": 2,
    "COMPLETED": 3,
}


def _stage_rank(status: Optional[str]) -> int:
    if not status:
        return -1
    base = status.replace("_IN_PROGRESS", "")
    return STAGE_ORDER.get(base, -1)


def compute_job_id(bucket_name: str, blob_name: str) -> str:
    """
    Single source of truth for job_id derivation. Used by services/api/main.py
    (to pre-register the PENDING doc) and services/inspect_worker/main.py (to
    resolve the same doc from a raw GCS notification). Must stay a pure
    function of the two strings only.
    """
    return f"{bucket_name}/{blob_name}".replace("/", "__")


class ClaimResult(str, Enum):
    CLAIMED = "CLAIMED"
    ALREADY_DONE = "ALREADY_DONE"
    LOCKED = "LOCKED"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


async def claim_stage(
    db: AsyncClient,
    job_id: str,
    expected_prev_statuses: set,
    in_progress_status: str,
    target_status: str,
    message_id: str,
    lease_seconds: int = 90,
) -> ClaimResult:
    """
    Atomically decide whether this handler invocation should do the real work
    for `target_status`. Two Cloud Run instances can receive the same (or a
    redelivered) Pub/Sub message concurrently with no sticky routing between
    them -- this is the compare-and-swap that arbitrates who actually runs.

    ALREADY_DONE - job status rank >= target rank, or this message_id was
                   already recorded. Caller should ack (204) without redoing
                   work.
    LOCKED       - another attempt holds an unexpired lease on this stage.
                   Caller should return 409 (NOT ack) so Pub/Sub retries
                   later without losing the message.
    CLAIMED      - transaction wrote status=in_progress_status + a claim
                   timestamp. Caller proceeds with the real work.
    """
    doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
    transaction = db.transaction()

    @async_transactional
    async def _txn(txn: AsyncTransaction) -> ClaimResult:
        snap = await doc_ref.get(transaction=txn)
        data = snap.to_dict() or {}
        current_status = data.get("status", "PENDING")
        processed_ids = set(data.get("processed_message_ids") or [])

        if message_id and message_id in processed_ids:
            return ClaimResult.ALREADY_DONE

        current_rank = _stage_rank(current_status)
        target_rank = STAGE_ORDER[target_status]

        if current_rank >= target_rank:
            return ClaimResult.ALREADY_DONE

        if current_status == in_progress_status:
            claimed_at_str = data.get(f"{target_status.lower()}_claimed_at")
            if claimed_at_str:
                age = (dt.datetime.now(dt.timezone.utc) - _parse_iso(claimed_at_str)).total_seconds()
                if age < lease_seconds:
                    return ClaimResult.LOCKED
            # lease expired (or missing timestamp) -> fall through and reclaim

        elif current_status not in expected_prev_statuses:
            # Doc isn't in a state this stage can legally start from --
            # conservative: don't clobber, treat as already handled elsewhere.
            return ClaimResult.ALREADY_DONE

        now = _now_iso()
        txn.set(
            doc_ref,
            {
                "status": in_progress_status,
                f"{target_status.lower()}_claimed_at": now,
                "updated_at": now,
            },
            merge=True,
        )
        return ClaimResult.CLAIMED

    return await _txn(transaction)


async def finalize_stage(
    db: AsyncClient,
    job_id: str,
    in_progress_status: str,
    final_status: str,
    message_id: str,
    extra_fields: Optional[dict] = None,
) -> None:
    """
    Transition <STAGE>_IN_PROGRESS -> final_status after the real work (GCS
    I/O, Pub/Sub publish -- anything outside Firestore) has already
    succeeded. Separate transaction from claim_stage, since a Firestore
    transaction can't wrap non-Firestore I/O.
    """
    doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
    transaction = db.transaction()

    @async_transactional
    async def _txn(txn: AsyncTransaction) -> None:
        now = _now_iso()
        fields: dict = dict(extra_fields or {})
        fields["status"] = final_status
        fields["updated_at"] = now
        if message_id:
            fields["processed_message_ids"] = firestore.ArrayUnion([message_id])
        txn.set(doc_ref, fields, merge=True)

    await _txn(transaction)
