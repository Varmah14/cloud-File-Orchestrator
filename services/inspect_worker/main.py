import asyncio
import base64
import json
import logging
import os
import datetime as dt

from fastapi import FastAPI, Request
from fastapi.responses import Response

from google.cloud import storage, pubsub_v1, firestore
from common.config import GCP_PROJECT_ID, CLASSIFY_TOPIC
from common.idempotency import claim_stage, finalize_stage, compute_job_id, ClaimResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

try:
    import puremagic

    HAS_PUREMAGIC = True
except ImportError:
    HAS_PUREMAGIC = False
    logger.warning("puremagic not available")

EXTENSION_MAP = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".zip": "application/zip",
}


def detect_mime_type(blob) -> str:
    """
    Detects MIME type via magic bytes, then GCS content_type, then
    extension. Blocking (GCS + puremagic I/O) -- callers must run this via
    asyncio.to_thread.
    """
    file_ref = f"gs://{blob.bucket.name}/{blob.name}"

    if HAS_PUREMAGIC and blob.size and blob.size > 0:
        try:
            header = blob.download_as_bytes(start=0, end=2048)
            if len(header) >= 4:
                result = puremagic.from_string(header)
                if isinstance(result, str) and result:
                    logger.info(f"MIME DETECTED | puremagic | {result} | {file_ref}")
                    return result
                if hasattr(result, "mime") and result.mime:
                    logger.info(f"MIME DETECTED | puremagic | {result.mime} | {file_ref}")
                    return result.mime
        except Exception as e:
            logger.info(f"MIME UNKNOWN | puremagic | error: {e} | {file_ref}")

    if blob.content_type and blob.content_type != "application/octet-stream":
        logger.info(f"MIME DETECTED | GCS metadata | {blob.content_type} | {file_ref}")
        return blob.content_type

    _, ext = os.path.splitext(blob.name.lower())
    if ext in EXTENSION_MAP:
        logger.info(f"MIME DETECTED | extension | {ext} -> {EXTENSION_MAP[ext]} | {file_ref}")
        return EXTENSION_MAP[ext]

    logger.info(f"MIME DEFAULT | fallback | application/octet-stream | {file_ref}")
    return "application/octet-stream"


app = FastAPI()
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
db = firestore.AsyncClient(project=GCP_PROJECT_ID)


@app.post("/pubsub-push")
async def pubsub_push(request: Request):
    envelope = await request.json()
    message = envelope.get("message", {})
    data_b64 = message.get("data")
    if not data_b64:
        return Response(status_code=204)

    payload_json = base64.b64decode(data_b64).decode("utf-8")
    payload = json.loads(payload_json)
    logger.info(f"Received Pub/Sub payload: {payload}")

    bucket_name = payload.get("bucket")
    blob_name = payload.get("blob") or payload.get("name")
    job_id = compute_job_id(bucket_name, blob_name)
    message_id = message.get("messageId") or f"{job_id}:no-message-id"

    logger.info(f"Inspecting gs://{bucket_name}/{blob_name} (job_id={job_id})")

    claim = await claim_stage(
        db,
        job_id,
        expected_prev_statuses={"PENDING"},
        in_progress_status="INSPECT_IN_PROGRESS",
        target_status="INSPECTED",
        message_id=message_id,
    )
    if claim == ClaimResult.ALREADY_DONE:
        return Response(status_code=204)
    if claim == ClaimResult.LOCKED:
        return Response(status_code=409)

    blob = storage_client.bucket(bucket_name).blob(blob_name)

    if "size" in payload or "contentType" in payload:
        file_size = int(payload.get("size", 0))
    else:
        try:
            await asyncio.to_thread(blob.reload)
        except Exception as e:
            logger.error(f"Failed to reload blob metadata: {e}")
            return Response(status_code=500)
        file_size = blob.size or 0

    mime_type = await asyncio.to_thread(detect_mime_type, blob)

    event = {
        "job_id": job_id,
        "bucket": bucket_name,
        "blob": blob_name,
        "mime_type": mime_type,
        "file_size": file_size,
    }
    future = publisher.publish(
        publisher.topic_path(GCP_PROJECT_ID, CLASSIFY_TOPIC),
        data=json.dumps(event).encode(),
    )
    await asyncio.to_thread(future.result, timeout=30)

    now = dt.datetime.utcnow().isoformat() + "Z"
    await finalize_stage(
        db,
        job_id,
        in_progress_status="INSPECT_IN_PROGRESS",
        final_status="INSPECTED",
        message_id=message_id,
        extra_fields={
            "source": {"bucket": bucket_name, "blob": blob_name},
            "inspection": {
                "mime_type": mime_type,
                "file_size": file_size,
                "inspected_at": now,
            },
        },
    )

    return Response(status_code=204)
