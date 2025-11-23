# services/act_worker/main.py

import base64
import json
import datetime as dt
import logging
import os
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import Response

from google.cloud import storage, firestore

from common.config import (
    GCP_PROJECT_ID,
    UPLOAD_BUCKET,
    PROCESSED_BUCKET,
    JOBS_COLLECTION,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

app = FastAPI()
storage_client = storage.Client()
db = firestore.Client(project=GCP_PROJECT_ID)

RULES_COLLECTION = os.getenv("RULES_COLLECTION", "rules")


# -------------------------- Rule evaluation helpers --------------------------


def load_rules() -> List[Dict[str, Any]]:
    """
    Load enabled rules from Firestore, sorted by priority.
    """
    docs = db.collection(RULES_COLLECTION).where("enabled", "==", True).stream()
    rules: List[Dict[str, Any]] = []
    for d in docs:
        data = d.to_dict() or {}
        data["id"] = d.id
        rules.append(data)

    # Lowest priority number = highest priority
    rules.sort(key=lambda r: r.get("priority", 0))
    return rules


def rule_matches(rule: Dict[str, Any], file_meta: Dict[str, Any]) -> bool:
    """
    Supported condition types:
      - extension: ".csv"  or "csv"
      - name_contains: "report"
      - size_gt_mb: "10"
      - size_lt_mb: "1"
    """
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

        else:
            # Unknown condition: ignore it
            continue

    return True


def apply_actions(rule: Dict[str, Any], file_meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supported actions:
      - move_to_folder: "reports/2025"
      - tag: "confidential"
      - delete: "true" (value ignored)
      - copy_to_bucket: "some-other-bucket"
    """
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
        logger.warning(
            f"Act worker: missing required fields "
            f"(job_id={job_id}, bucket={bucket_name}, blob={blob_name})"
        )
        return Response(status_code=204)

    # Build file metadata for rules
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

    # -------------------- Evaluate rules --------------------
    rules = load_rules()
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
            logger.info(
                f"Act worker: matched rule {rule.get('name')} ({rule.get('id')})"
            )
            break

    src_bucket = storage_client.bucket(bucket_name)
    src_blob = src_bucket.blob(blob_name)
    filename = blob_name.split("/")[-1]

    # Case: delete only
    if matched_rule and applied["delete_source_only"]:
        logger.info(
            "Act worker: deleting gs://%s/%s due to rule %s",
            bucket_name,
            blob_name,
            matched_rule.get("name"),
        )
        src_blob.delete()

        doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
        doc_ref.set(
            {
                "action": {
                    "action": "delete",
                    "rule_id": matched_rule.get("id"),
                    "rule_name": matched_rule.get("name"),
                    "deleted_bucket": bucket_name,
                    "deleted_blob": blob_name,
                    "tags": applied["tags"],
                    "acted_at": dt.datetime.utcnow().isoformat() + "Z",
                },
                "status": "COMPLETED",
                "updated_at": dt.datetime.utcnow().isoformat() + "Z",
            },
            merge=True,
        )
        return Response(status_code=204)

    # Case: move/copy to processed bucket
    dest_bucket_name = applied["dest_bucket"] or PROCESSED_BUCKET
    dest_folder = applied["dest_folder"] or classification
    dest_bucket = storage_client.bucket(dest_bucket_name)
    dest_blob_name = f"{dest_folder}/{filename}"
    dest_blob = dest_bucket.blob(dest_blob_name)

    logger.info(
        "Act worker: moving gs://%s/%s → gs://%s/%s",
        bucket_name,
        blob_name,
        dest_bucket_name,
        dest_blob_name,
    )

    # copy + delete = move
    src_bucket.copy_blob(src_blob, dest_bucket, new_name=dest_blob_name)
    src_blob.delete()

    action_doc: Dict[str, Any] = {
        "dest_bucket": dest_bucket_name,
        "dest_blob": dest_blob_name,
        "classification": classification,
        "dest_folder": dest_folder,
        "tags": applied["tags"],
        "acted_at": dt.datetime.utcnow().isoformat() + "Z",
    }
    if matched_rule:
        action_doc["rule_id"] = matched_rule.get("id")
        action_doc["rule_name"] = matched_rule.get("name")

    doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
    doc_ref.set(
        {
            "action": action_doc,
            "status": "COMPLETED",
            "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        },
        merge=True,
    )

    return Response(status_code=204)
