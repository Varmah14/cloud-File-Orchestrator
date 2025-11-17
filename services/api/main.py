# services/api/main.py
import uuid
import datetime as dt

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from google.cloud import storage, pubsub_v1, firestore

from common.config import (
    GCP_PROJECT_ID,
    UPLOAD_BUCKET,
    INGEST_TOPIC,
    JOBS_COLLECTION,
)

app = FastAPI()

storage_client = storage.Client()
pubsub_client = pubsub_v1.PublisherClient()
firestore_client = firestore.Client(project=GCP_PROJECT_ID)

# Helper: Pub/Sub topic path
def topic_path(topic_name: str) -> str:
    return pubsub_client.topic_path(GCP_PROJECT_ID, topic_name)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Generate job id
    job_id = str(uuid.uuid4())
    now = dt.datetime.utcnow().isoformat() + "Z"

    # Store file in uploads bucket
    bucket = storage_client.bucket(UPLOAD_BUCKET)
    # we keep a simple path: uploads/<job_id>_<original_name>
    blob_name = f"uploads/{job_id}_{file.filename}"
    blob = bucket.blob(blob_name)

    contents = await file.read()
    blob.upload_from_string(contents)

    # Create Firestore job document
    job_doc = {
        "job_id": job_id,
        "filename": file.filename,
        "upload_bucket": UPLOAD_BUCKET,
        "upload_blob": blob_name,
        "status": "UPLOADED",
        "created_at": now,
        "updated_at": now,
    }
    firestore_client.collection(JOBS_COLLECTION).document(job_id).set(job_doc)

    # Publish message to ingest topic for inspect worker
    message = {
        "job_id": job_id,
        "bucket": UPLOAD_BUCKET,
        "blob": blob_name,
    }

    # Data must be bytes; we’ll send JSON as string
    import json

    data = json.dumps(message).encode("utf-8")
    future = pubsub_client.publish(topic_path(INGEST_TOPIC), data=data)
    future.result()  # wait for publish

    return JSONResponse(
        {
            "job_id": job_id,
            "message": "File uploaded and job created",
        }
    )
