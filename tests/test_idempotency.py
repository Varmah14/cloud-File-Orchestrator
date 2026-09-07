# tests/test_idempotency.py
#
# Unit tests for common.idempotency's claim/finalize compare-and-swap logic.
# No Firestore emulator: db/transaction/doc_ref are faked with unittest.mock,
# stubbing just enough of AsyncTransaction's internals (_begin/_commit/etc.)
# for the real async_transactional decorator to run our transaction body
# without touching the network.

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

from common.idempotency import (
    claim_stage,
    finalize_stage,
    compute_job_id,
    ClaimResult,
)


def make_fake_db(doc_data):
    snapshot = MagicMock()
    snapshot.to_dict.return_value = doc_data

    doc_ref = MagicMock()
    doc_ref.get = AsyncMock(return_value=snapshot)

    collection = MagicMock()
    collection.document.return_value = doc_ref

    transaction = MagicMock()
    transaction._max_attempts = 5
    transaction._read_only = False
    transaction._clean_up = MagicMock()
    transaction._begin = AsyncMock()
    transaction._commit = AsyncMock()
    transaction._rollback = AsyncMock()
    transaction.set = MagicMock()

    db = MagicMock()
    db.collection.return_value = collection
    db.transaction.return_value = transaction

    return db, doc_ref, transaction


def run(coro):
    return asyncio.run(coro)


def test_compute_job_id_is_deterministic_and_path_safe():
    a = compute_job_id("drbfo-uploads", "uploads/report.pdf")
    b = compute_job_id("drbfo-uploads", "uploads/report.pdf")
    assert a == b
    assert "/" not in a
    assert a == "drbfo-uploads__uploads__report.pdf"


def test_claim_stage_claims_from_expected_prior_status():
    db, doc_ref, transaction = make_fake_db({"status": "PENDING"})

    result = run(
        claim_stage(
            db,
            "job1",
            expected_prev_statuses={"PENDING"},
            in_progress_status="INSPECT_IN_PROGRESS",
            target_status="INSPECTED",
            message_id="m1",
        )
    )

    assert result == ClaimResult.CLAIMED
    transaction.set.assert_called_once()
    doc_ref_arg, written = transaction.set.call_args[0]
    assert doc_ref_arg is doc_ref
    assert written["status"] == "INSPECT_IN_PROGRESS"
    assert "inspected_claimed_at" in written


def test_claim_stage_already_done_when_rank_already_ahead():
    db, doc_ref, transaction = make_fake_db({"status": "CLASSIFIED"})

    result = run(
        claim_stage(
            db,
            "job1",
            expected_prev_statuses={"PENDING"},
            in_progress_status="INSPECT_IN_PROGRESS",
            target_status="INSPECTED",
            message_id="m2",
        )
    )

    assert result == ClaimResult.ALREADY_DONE
    transaction.set.assert_not_called()


def test_claim_stage_already_done_for_previously_seen_message_id():
    db, doc_ref, transaction = make_fake_db(
        {"status": "PENDING", "processed_message_ids": ["m3"]}
    )

    result = run(
        claim_stage(
            db,
            "job1",
            expected_prev_statuses={"PENDING"},
            in_progress_status="INSPECT_IN_PROGRESS",
            target_status="INSPECTED",
            message_id="m3",
        )
    )

    assert result == ClaimResult.ALREADY_DONE


def test_claim_stage_locked_while_lease_is_active():
    now = dt.datetime.now(dt.timezone.utc)
    claimed_at = (now - dt.timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
    db, doc_ref, transaction = make_fake_db(
        {"status": "INSPECT_IN_PROGRESS", "inspected_claimed_at": claimed_at}
    )

    result = run(
        claim_stage(
            db,
            "job1",
            expected_prev_statuses={"PENDING"},
            in_progress_status="INSPECT_IN_PROGRESS",
            target_status="INSPECTED",
            message_id="m4",
            lease_seconds=90,
        )
    )

    assert result == ClaimResult.LOCKED
    transaction.set.assert_not_called()


def test_claim_stage_reclaims_once_lease_has_expired():
    now = dt.datetime.now(dt.timezone.utc)
    claimed_at = (now - dt.timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
    db, doc_ref, transaction = make_fake_db(
        {"status": "INSPECT_IN_PROGRESS", "inspected_claimed_at": claimed_at}
    )

    result = run(
        claim_stage(
            db,
            "job1",
            expected_prev_statuses={"PENDING"},
            in_progress_status="INSPECT_IN_PROGRESS",
            target_status="INSPECTED",
            message_id="m5",
            lease_seconds=90,
        )
    )

    assert result == ClaimResult.CLAIMED
    transaction.set.assert_called_once()


def test_finalize_stage_writes_final_status_and_merges_extra_fields():
    db, doc_ref, transaction = make_fake_db({"status": "INSPECT_IN_PROGRESS"})

    run(
        finalize_stage(
            db,
            "job1",
            in_progress_status="INSPECT_IN_PROGRESS",
            final_status="INSPECTED",
            message_id="m6",
            extra_fields={"inspection": {"mime_type": "text/plain"}},
        )
    )

    transaction.set.assert_called_once()
    doc_ref_arg, written = transaction.set.call_args[0]
    assert doc_ref_arg is doc_ref
    assert written["status"] == "INSPECTED"
    assert written["inspection"]["mime_type"] == "text/plain"
