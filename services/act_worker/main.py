# services/act_worker/main.py
import base64
import json
import datetime as dt
import os

from fastapi import FastAPI, Request
from fastapi.responses import Response

from google.cloud import storage, firestore

from common.config import (
    GCP_PROJECT_ID,
    PROCESSED_BUCKET,
    JOBS_COLLECTION,
)

app = FastAPI()

storage_client = storage.Client()
firestore_client = firestore.Client(project=GCP_PROJECT_ID)


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
    src_bucket_name = event["bucket"]
    src_blob_name = event["blob"]
    target_prefix = event["target_prefix"]

    src_bucket = storage_client.bucket(src_bucket_name)
    src_blob = src_bucket.blob(src_blob_name)

    # Extract just filename from blob name
    filename = os.path.basename(src_blob_name)

    # For simplicity, processed bucket can be same or different
    dest_bucket_name = PROCESSED_BUCKET or src_bucket_name
    dest_bucket = storage_client.bucket(dest_bucket_name)
    dest_blob_name = f"{target_prefix}{filename}"

    # Copy then delete
    src_bucket.copy_blob(src_blob, dest_bucket, new_name=dest_blob_name)
    src_blob.delete()

    final_location = {
        "bucket": dest_bucket_name,
        "blob": dest_blob_name,
    }

    now = dt.datetime.utcnow().isoformat() + "Z"
    job_ref = firestore_client.collection(JOBS_COLLECTION).document(job_id)
    job_ref.update(
        {
            "final_location": final_location,
            "status": "COMPLETED",
            "updated_at": now,
        }
    )

    return Response(status_code=204)
