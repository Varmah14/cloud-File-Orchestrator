# services/classify_worker/main.py

import base64
import json
import logging
import os
import datetime as dt

from fastapi import FastAPI, Request
from fastapi.responses import Response

from google.cloud import pubsub_v1, firestore

from common.config import GCP_PROJECT_ID, ACT_TOPIC, JOBS_COLLECTION

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
publisher = pubsub_v1.PublisherClient()
db = firestore.Client(project=GCP_PROJECT_ID)


def topic_path(topic_name: str) -> str:
    return publisher.topic_path(GCP_PROJECT_ID, topic_name)


def simple_classification(mime_type: str, ext: str) -> str:
    """
    Very basic classifier based on extension/MIME.
    You can replace this with your more advanced logic.
    """
    ext = (ext or "").lower()
    mime = (mime_type or "").lower()

    if ext in [".jpg", ".jpeg", ".png", ".gif"] or mime.startswith("image/"):
        return "images"
    if ext in [".csv", ".xlsx"] or "spreadsheet" in mime or "csv" in mime:
        return "spreadsheets"
    if ext in [".pdf"]:
        return "pdfs"
    if ext in [".txt"]:
        return "text"
    return "uncategorized"


@app.post("/pubsub-push")
async def pubsub_push(request: Request):
    envelope = await request.json()
    message = envelope.get("message", {})
    data_b64 = message.get("data")
    if not data_b64:
        logger.warning("Classify worker: received Pub/Sub push with no data")
        return Response(status_code=204)

    payload_json = base64.b64decode(data_b64).decode("utf-8")
    payload = json.loads(payload_json)
    logger.info(f"Classify worker: received payload: {payload}")

    job_id = payload.get("job_id")
    bucket_name = payload.get("bucket")
    blob_name = payload.get("blob") or payload.get("name")
    mime_type = payload.get("mime_type")
    file_size = payload.get("file_size") or 0

    if not job_id or not bucket_name or not blob_name:
        logger.warning(
            f"Classify worker: missing fields "
            f"(job_id={job_id}, bucket={bucket_name}, blob={blob_name})"
        )
        return Response(status_code=204)

    _, ext = os.path.splitext(blob_name)
    classification = simple_classification(mime_type, ext)

    # Update Firestore job (optional but nice)
    doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
    doc_ref.set(
        {
            "classification": {
                "classification": classification,
                "mime_type": mime_type,
                "file_size": file_size,
                "ext": ext,
                "classified_at": dt.datetime.utcnow().isoformat() + "Z",
            },
            "status": "CLASSIFIED",
            "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        },
        merge=True,
    )

    # Send to act worker with full metadata
    event = {
        "job_id": job_id,
        "bucket": bucket_name,
        "blob": blob_name,
        "name": blob_name,
        "mime_type": mime_type,
        "file_size": file_size,
        "ext": ext,
        "classification": classification,
    }

    publisher.publish(
        topic_path(ACT_TOPIC),
        data=json.dumps(event).encode("utf-8"),
    )

    return Response(status_code=204)
