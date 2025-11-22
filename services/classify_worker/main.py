# services/classify_worker/main.py
import base64
import json
import datetime as dt
import os

from fastapi import FastAPI, Request
from fastapi.responses import Response

from google.cloud import pubsub_v1, firestore

from common.config import (
    GCP_PROJECT_ID,
    ACT_TOPIC,
    JOBS_COLLECTION,
)

app = FastAPI()

pubsub_client = pubsub_v1.PublisherClient()
firestore_client = firestore.Client(project=GCP_PROJECT_ID)


def topic_path(topic_name: str) -> str:
    return pubsub_client.topic_path(GCP_PROJECT_ID, topic_name)


def simple_classification(mime_type: str, blob: str) -> str:
    """Better classification using both mime type and file extension."""
    mime = (mime_type or "").lower()
    blob_lower = blob.lower()

    _, ext = os.path.splitext(blob_lower)

    if "pdf" in mime or ext == ".pdf":
        return "docs/"

    if mime.startswith("image/") or ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        return "images/"

    if mime.startswith("text/") or ext in [".txt", ".md"]:
        return "text/"

    return "others/"


@app.post("/pubsub-push")
async def pubsub_push(request: Request):
    envelope = await request.json()
    if "message" not in envelope:
        return Response(status_code=400)

    msg = envelope["message"]
    data = msg.get("data")
    if data is None:
        return Response(status_code=400)

    payload_str = base64.b64decode(data).decode("utf-8")
    event = json.loads(payload_str)

    job_id = event["job_id"]
    bucket = event["bucket"]
    blob = event["blob"]
    mime_type = event["mime_type"]

    target_prefix = simple_classification(mime_type, blob)

    classification = {
        "mime_type": mime_type,
        "target_prefix": target_prefix,
    }

    now = dt.datetime.utcnow().isoformat() + "Z"
    job_ref = firestore_client.collection(JOBS_COLLECTION).document(job_id)
    job_ref.update(
        {
            "classification": classification,
            "status": "CLASSIFIED",
            "updated_at": now,
        }
    )

    act_event = {
        "job_id": job_id,
        "bucket": bucket,
        "blob": blob,
        "target_prefix": target_prefix,
    }

    act_data = json.dumps(act_event).encode("utf-8")
    pubsub_client.publish(topic_path(ACT_TOPIC), data=act_data)

    return Response(status_code=204)
