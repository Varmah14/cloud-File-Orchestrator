# services/inspect_worker/main.py
import base64
import json
import datetime as dt
import io

from fastapi import FastAPI, Request
from fastapi.responses import Response

from google.cloud import storage, pubsub_v1, firestore
import magic  # from python-magic

from common.config import (
    GCP_PROJECT_ID,
    CLASSIFY_TOPIC,
    JOBS_COLLECTION,
)

app = FastAPI()

storage_client = storage.Client()
pubsub_client = pubsub_v1.PublisherClient()
firestore_client = firestore.Client(project=GCP_PROJECT_ID)


def topic_path(topic_name: str) -> str:
    return pubsub_client.topic_path(GCP_PROJECT_ID, topic_name)


@app.post("/pubsub-push")
async def pubsub_push(request: Request):
    """
    Entry point for Pub/Sub push messages.
    Format: {"message": {"data": "..."}}
    """
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
    bucket_name = event["bucket"]
    blob_name = event["blob"]

    # Download file from GCS
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    content_bytes = blob.download_as_bytes()
    file_size = len(content_bytes)

    # Detect mime type using python-magic
    mime_type = magic.from_buffer(content_bytes[:2048], mime=True)

    # Simple additional metadata (you can expand later)
    inspection = {
        "mime_type": mime_type,
        "file_size": file_size,
    }

    # Update Firestore job
    now = dt.datetime.utcnow().isoformat() + "Z"
    job_ref = firestore_client.collection(JOBS_COLLECTION).document(job_id)
    job_ref.update(
        {
            "inspection": inspection,
            "status": "INSPECTED",
            "updated_at": now,
        }
    )

    # Publish to classify topic
    classify_event = {
        "job_id": job_id,
        "bucket": bucket_name,
        "blob": blob_name,
        "mime_type": mime_type,
        "file_size": file_size,
    }

    classify_data = json.dumps(classify_event).encode("utf-8")
    pubsub_client.publish(topic_path(CLASSIFY_TOPIC), data=classify_data)

    # Pub/Sub push expects 2xx
    return Response(status_code=204)
