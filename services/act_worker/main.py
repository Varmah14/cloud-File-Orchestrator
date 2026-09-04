# services/act_worker/main.py

import asyncio
import base64
import json
import datetime as dt
import logging
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import Response

from google.cloud import storage, firestore

from common.config import (
    GCP_PROJECT_ID,
    UPLOAD_BUCKET,
    PROCESSED_BUCKET,
    RULES_COLLECTION,
)
from common.idempotency import claim_stage, finalize_stage, ClaimResult

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

app = FastAPI()
storage_client = storage.Client()
db = firestore.AsyncClient(project=GCP_PROJECT_ID)


# -------------------------- Rule evaluation helpers --------------------------


async def load_rules() -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    query = db.collection(RULES_COLLECTION).where("enabled", "==", True)
    async for d in query.stream():
        data = d.to_dict() or {}
        data["id"] = d.id
        rules.append(data)
    rules.sort(key=lambda r: r.get("priority", 0))
    return rules


def rule_matches(rule: Dict[str, Any], file_meta: Dict[str, Any]) -> bool:
    if not rule.get("enabled", True):
        return False

    conditions = rule.get("conditions") or []
    name = (file_meta.get("name") or "").lower()
    ext = (file_meta.get("ext") or "").lower()
    size_bytes = file_meta.get("file_size") or 0

    for cond in conditions:
        ctype = (cond.get("type") or "").lower()
        value = (cond.get("value") or "").strip()

        if not value:
            continue

        if ctype == "extension":
            v = value.lower()
            if not v.startswith("."):
                v = "." + v
            if ext != v:
                return False

        elif ctype == "name_contains":
            if value.lower() not in name:
                return False

        elif ctype == "size_gt_mb":
            try:
                threshold = float(value) * 1024 * 1024
            except ValueError:
                continue
            if size_bytes <= threshold:
                return False

        elif ctype == "size_lt_mb":
            try:
                threshold = float(value) * 1024 * 1024
            except ValueError:
                continue
            if size_bytes >= threshold:
                return False

    return True


def apply_actions(rule: Dict[str, Any], file_meta: Dict[str, Any]) -> Dict[str, Any]:
    actions = rule.get("actions") or []
    dest_bucket = PROCESSED_BUCKET
    dest_folder = None
    tags: List[str] = []
    delete_source_only = False

    for action in actions:
        atype = (action.get("type") or "").lower()
        value = (action.get("value") or "").strip()

        if atype == "move_to_folder":
            dest_folder = value
        elif atype == "copy_to_bucket":
            dest_bucket = value or dest_bucket
        elif atype == "tag":
            if value:
                tags.append(value)
        elif atype == "delete":
            delete_source_only = True

    return {
        "dest_bucket": dest_bucket,
        "dest_folder": dest_folder,
        "tags": tags,
        "delete_source_only": delete_source_only,
    }


# ------------------------------- Pub/Sub entry -------------------------------


@app.post("/pubsub-push")
async def pubsub_push(request: Request):
    envelope = await request.json()
    message = envelope.get("message", {})
    data_b64 = message.get("data")
    if not data_b64:
        logger.warning("Act worker: received Pub/Sub push with no data")
        return Response(status_code=204)

    payload_json = base64.b64decode(data_b64).decode("utf-8")
    payload = json.loads(payload_json)
    logger.info(f"Act worker: received payload: {payload}")

    job_id = payload.get("job_id")
    bucket_name = payload.get("bucket") or UPLOAD_BUCKET
    blob_name = payload.get("blob") or payload.get("name")
    classification = payload.get("classification") or "uncategorized"

    if not job_id or not bucket_name or not blob_name:
        logger.warning(f"Act worker: missing required fields (job_id={job_id}, bucket={bucket_name}, blob={blob_name})")
        return Response(status_code=204)

    message_id = message.get("messageId") or f"{job_id}:no-message-id"

    claim = await claim_stage(
        db,
        job_id,
        expected_prev_statuses={"CLASSIFIED"},
        in_progress_status="ACT_IN_PROGRESS",
        target_status="COMPLETED",
        message_id=message_id,
    )
    if claim == ClaimResult.ALREADY_DONE:
        return Response(status_code=204)
    if claim == ClaimResult.LOCKED:
        return Response(status_code=409)

    file_meta = {
        "job_id": job_id,
        "bucket": bucket_name,
        "blob": blob_name,
        "name": payload.get("name") or blob_name,
        "mime_type": payload.get("mime_type"),
        "file_size": payload.get("file_size") or 0,
        "ext": payload.get("ext") or "",
        "classification": classification,
    }

    rules = await load_rules()
    matched_rule = None
    applied = {
        "dest_bucket": PROCESSED_BUCKET,
        "dest_folder": classification,
        "tags": [],
        "delete_source_only": False,
    }

    for rule in rules:
        if rule_matches(rule, file_meta):
            matched_rule = rule
            applied = apply_actions(rule, file_meta)
            logger.info(f"Act worker: matched rule {rule.get('name')} ({rule.get('id')})")
            break

    src_bucket = storage_client.bucket(bucket_name)
    src_blob = src_bucket.blob(blob_name)
    filename = blob_name.split("/")[-1]

    # -- Idempotency check: if source is gone, job already processed (e.g. a
    # retry after claim_stage reclaimed an expired lease from a crashed
    # attempt that had already finished the real GCS move) --
    if not await asyncio.to_thread(src_blob.exists):
        logger.info(f"Act worker: source blob already gone, marking COMPLETED (job_id={job_id})")
        await finalize_stage(
            db, job_id, "ACT_IN_PROGRESS", "COMPLETED", message_id, extra_fields={}
        )
        return Response(status_code=204)

    # -- Case: delete only --
    if matched_rule and applied["delete_source_only"]:
        logger.info(f"Act worker: deleting gs://{bucket_name}/{blob_name}")
        await asyncio.to_thread(src_blob.delete)
        now = dt.datetime.utcnow().isoformat() + "Z"
        await finalize_stage(
            db,
            job_id,
            "ACT_IN_PROGRESS",
            "COMPLETED",
            message_id,
            extra_fields={
                "action": {
                    "action": "delete",
                    "rule_id": matched_rule.get("id"),
                    "rule_name": matched_rule.get("name"),
                    "deleted_bucket": bucket_name,
                    "deleted_blob": blob_name,
                    "tags": applied["tags"],
                    "acted_at": now,
                },
            },
        )
        return Response(status_code=204)

    # -- Case: move to processed bucket --
    dest_bucket_name = applied["dest_bucket"] or PROCESSED_BUCKET
    dest_folder = applied["dest_folder"] or classification
    dest_bucket = storage_client.bucket(dest_bucket_name)
    dest_blob_name = f"{dest_folder}/{filename}"

    logger.info(f"Act worker: moving gs://{bucket_name}/{blob_name} -> gs://{dest_bucket_name}/{dest_blob_name}")

    await asyncio.to_thread(src_bucket.copy_blob, src_blob, dest_bucket, dest_blob_name)
    await asyncio.to_thread(src_blob.delete)

    now = dt.datetime.utcnow().isoformat() + "Z"
    action_doc: Dict[str, Any] = {
        "dest_bucket": dest_bucket_name,
        "dest_blob": dest_blob_name,
        "classification": classification,
        "dest_folder": dest_folder,
        "tags": applied["tags"],
        "acted_at": now,
    }
    if matched_rule:
        action_doc["rule_id"] = matched_rule.get("id")
        action_doc["rule_name"] = matched_rule.get("name")

    await finalize_stage(
        db,
        job_id,
        "ACT_IN_PROGRESS",
        "COMPLETED",
        message_id,
        extra_fields={"action": action_doc},
    )

    return Response(status_code=204)
