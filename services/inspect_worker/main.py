

import os
import base64
import json
import logging

logger = logging.getLogger(__name__)


logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


import base64
import json
import datetime as dt
import logging
from fastapi import FastAPI, Request
from fastapi.responses import Response

from google.cloud import storage, pubsub_v1, firestore
from common.config import GCP_PROJECT_ID, CLASSIFY_TOPIC, JOBS_COLLECTION

# ------------------- puremagic (fixed for all versions) -------------------
try:
    import puremagic

    HAS_PUREMAGIC = True
    logging.info("puremagic imported successfully")
except ImportError:
    HAS_PUREMAGIC = False
    logging.warning("puremagic not available")

# Reliable extension map
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


# def detect_mime_type(blob) -> str:
#     # 1. puremagic — works with both old and new versions
#     if HAS_PUREMAGIC and blob.size and blob.size > 0:
#         try:
#             header = blob.download_as_bytes(start=0, end=2048)  # 2048 is safe
#             if len(header) >= 4:
#                 result = puremagic.from_string(header)

#                 # New versions return MagicMatch object → has .mime
#                 # Old versions return plain string
#                 if isinstance(result, str) and result:
#                     logging.info(f"puremagic (str) → {result}")
#                     return result
#                 elif hasattr(result, "mime") and result.mime:
#                     logging.info(f"puremagic (object) → {result.mime}")
#                     return result.mime
#         except Exception as e:
#             logging.info(f"puremagic failed: {e}")

#     # 2. GCS content_type
#     if blob.content_type and blob.content_type != "application/octet-stream":
#         logging.info(f"GCS metadata → {blob.content_type}")
#         return blob.content_type

#     # 3. Extension fallback
#     _, ext = os.path.splitext(blob.name.lower())
#     if ext in EXTENSION_MAP:
#         logging.info(f"Extension → {ext} = {EXTENSION_MAP[ext]}")
#         return EXTENSION_MAP[ext]

#     return "application/octet-stream"


def detect_mime_type(blob) -> str:
    """
    Detects MIME type and ALWAYS logs exactly how it was determined.
    """
    file_ref = f"gs://{blob.bucket.name}/{blob.name}"

    # 1. puremagic – magic bytes detection
    if HAS_PUREMAGIC and blob.size and blob.size > 0:
        try:
            header = blob.download_as_bytes(start=0, end=2048)
            if len(header) >= 4:
                result = puremagic.from_string(header)

                # Handles both old (str) and new (MagicMatch) return types
                if isinstance(result, str) and result:
                    logging.info(f"MIME DETECTED │ puremagic │ {result} │ {file_ref}")
                    return result

                if hasattr(result, "mime") and result.mime:
                    logging.info(
                        f"MIME DETECTED │ puremagic │ {result.mime} │ {file_ref}"
                    )
                    return result.mime

                # If puremagic ran but found nothing
                logging.info(
                    f"MIME UNKNOWN   │ puremagic │ no signature found │ {file_ref}"
                )

        except Exception as e:
            logging.info(f"MIME UNKNOWN   │ puremagic │ error: {e} │ {file_ref}")

    else:
        logging.info(
            f"MIME SKIPPED   │ puremagic │ file empty or lib missing │ {file_ref}"
        )

    # 2. GCS uploaded content_type
    if blob.content_type and blob.content_type != "application/octet-stream":
        logging.info(f"MIME DETECTED │ GCS metadata │ {blob.content_type} │ {file_ref}")
        return blob.content_type

    # 3. Extension fallback
    _, ext = os.path.splitext(blob.name.lower())
    if ext in EXTENSION_MAP:
        logging.info(
            f"MIME DETECTED │ extension │ {ext} → {EXTENSION_MAP[ext]} │ {file_ref}"
        )
        return EXTENSION_MAP[ext]

    # 4. Final fallback
    logging.info(f"MIME DEFAULT   │ fallback │ application/octet-stream │ {file_ref}")
    return "application/octet-stream"


# ------------------- FastAPI -------------------
app = FastAPI()
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
db = firestore.Client(project=GCP_PROJECT_ID)


# @app.post("/pubsub-push")
# async def pubsub_push(request: Request):
#     # Decode Pub/Sub push envelope
#     envelope = await request.json()
#     message = envelope.get("message", {})
#     data_b64 = message.get("data")

#     if not data_b64:
#         logger.warning("Pub/Sub push received with no data field")
#         # Return 204 so Pub/Sub doesn't retry forever
#         return Response(status_code=204)

#     payload_json = base64.b64decode(data_b64).decode("utf-8")
#     payload = json.loads(payload_json)
#     logger.info(f"Received Pub/Sub payload: {payload}")

#     # -------- Normalize formats --------
#     # Case 1: internal orchestrator event (job_id, bucket, blob)
#     job_id = payload.get("job_id")
#     bucket_name = payload.get("bucket")
#     # internal messages used "blob", GCS uses "name"
#     blob_name = payload.get("blob") or payload.get("name")

#     if not bucket_name or not blob_name:
#         logger.warning(
#             f"Missing bucket/blob in payload, skipping. bucket={bucket_name}, blob={blob_name}"
#         )
#         return Response(status_code=204)

#     # If no job_id (GCS event), synthesize one from bucket + object
#     if not job_id:
#         job_id = f"{bucket_name}/{blob_name}"
#         logger.info(f"No job_id in payload, synthesized job_id={job_id}")

#     logger.info(f"Inspecting gs://{bucket_name}/{blob_name} (job {job_id})")

#     # -------- Inspect file (MIME + size) --------
#     blob = storage_client.bucket(bucket_name).blob(blob_name)
#     blob.reload()  # fresh metadata

#     mime_type = detect_mime_type(blob)
#     file_size = blob.size or 0

#     # -------- Update Firestore job --------
#     doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
#     doc_ref.set(
#         {
#             "inspection": {
#                 "mime_type": mime_type,
#                 "file_size": file_size,
#                 "inspected_at": dt.datetime.utcnow().isoformat() + "Z",
#             },
#             "status": "INSPECTED",
#             "updated_at": dt.datetime.utcnow().isoformat() + "Z",
#         },
#         merge=True,  # in case the document didn't exist yet
#     )

#     # -------- Forward to classify topic --------
#     event = {
#         "job_id": job_id,
#         "bucket": bucket_name,
#         "blob": blob_name,
#         "mime_type": mime_type,
#         "file_size": file_size,
#     }

#     publisher.publish(
#         publisher.topic_path(GCP_PROJECT_ID, CLASSIFY_TOPIC),
#         data=json.dumps(event).encode("utf-8"),
#     )

#     # Pub/Sub push only needs a 2xx, 204 is perfect
#     return Response(status_code=204)


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

    # Normalize fields
    bucket_name = payload.get("bucket")
    blob_name = payload.get("blob") or payload.get("name")
    job_id_raw = payload.get("job_id") or f"{bucket_name}/{blob_name}"

    # FIX: prevent Firestore nested paths
    job_id = job_id_raw.replace("/", "__")

    logger.info(f"Inspecting gs://{bucket_name}/{blob_name} (job_id={job_id})")

    blob = storage_client.bucket(bucket_name).blob(blob_name)

    # CRITICAL FIX: Only reload() if this is NOT a raw GCS event
    # Raw GCS events have "size" and "contentType" in payload
    # if "size" in payload or "contentType" in payload:
    #     # We already have fresh metadata from the event — trust it
    #     pass
    # else:
    #     # Internal orchestrator event — safe to reload
    #     try:
    #         blob.reload()
    #     except Exception as e:
    #         logger.error(f"Failed to reload blob metadata: {e}")
    #         return Response(status_code=500)

    # mime_type = detect_mime_type(blob)
    # # file_size = blob.size or 0

    if "size" in payload or "contentType" in payload:
        # Raw GCS event — use metadata directly from payload
        file_size = int(payload.get("size", 0))
    else:
        # Internal orchestrator event — reload blob metadata
        try:
            blob.reload()
        except Exception as e:
            logger.error(f"Failed to reload blob metadata: {e}")
            return Response(status_code=500)
        file_size = blob.size or 0

    mime_type = detect_mime_type(blob)

    # # Update Firestore
    # doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
    # doc_ref.set(
    #     {
    #         "inspection": {
    #             "mime_type": mime_type,
    #             "file_size": file_size,
    #             "inspected_at": dt.datetime.utcnow().isoformat() + "Z",
    #         },
    #         "status": "INSPECTED",
    #         "updated_at": dt.datetime.utcnow().isoformat() + "Z",
    #     },
    #     merge=True,
    # )

    doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
    now = dt.datetime.utcnow().isoformat() + "Z"

    doc_ref.set(
        {
            "source": {
                "bucket": bucket_name,
                "blob": blob_name,
            },
            "inspection": {
                "mime_type": mime_type,
                "file_size": file_size,
                "inspected_at": now,
            },
            "status": "INSPECTED",
            "updated_at": now,
        },
        merge=True,  # keep everything else unchanged
    )

    # Forward
    event = {
        "job_id": job_id,
        "bucket": bucket_name,
        "blob": blob_name,
        "mime_type": mime_type,
        "file_size": file_size,
    }
    publisher.publish(
        publisher.topic_path(GCP_PROJECT_ID, CLASSIFY_TOPIC),
        data=json.dumps(event).encode(),
    )

    return Response(status_code=204)
