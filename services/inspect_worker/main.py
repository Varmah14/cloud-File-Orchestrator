# # services/inspect_worker/main.py
# import base64
# import json
# import datetime as dt
# import os
# import logging

# from fastapi import FastAPI, Request
# from fastapi.responses import Response

# from google.cloud import storage, pubsub_v1, firestore

# from common.config import (
#     GCP_PROJECT_ID,
#     CLASSIFY_TOPIC,
#     JOBS_COLLECTION,
# )

# # ------------------------------------------------------------------------------
# # MIME detection helpers
# # ------------------------------------------------------------------------------

# # Try to import pure-magic (optional dependency)
# try:
#     import puremagic  # from pure-magic

#     HAS_PUREMAGIC = True
#     logging.info("pure-magic loaded successfully in inspect worker")
# except ImportError:
#     HAS_PUREMAGIC = False
#     logging.warning("pure-magic not installed—falling back to other methods")

# # Static fallback for common extensions
# EXTENSION_MAP = {
#     ".pdf": "application/pdf",
#     ".txt": "text/plain",
#     ".csv": "text/csv",
#     ".json": "application/json",
#     ".xml": "application/xml",
#     ".doc": "application/msword",
#     ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
#     ".xls": "application/vnd.ms-excel",
#     ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#     ".ppt": "application/vnd.ms-powerpoint",
#     ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
#     ".png": "image/png",
#     ".jpg": "image/jpeg",
#     ".jpeg": "image/jpeg",
#     ".gif": "image/gif",
#     ".zip": "application/zip",
# }


# def detect_mime_type(blob, content_bytes: bytes) -> str:
#     """
#     Decide MIME type using (in order):
#       1) pure-magic on the first 512 bytes (if available)
#       2) GCS blob.content_type (if not octet-stream/None)
#       3) File extension via EXTENSION_MAP
#       4) Fallback: application/octet-stream
#     """
#     mime_type = None

#     # 1) pure-magic from bytes
#     if HAS_PUREMAGIC and content_bytes:
#         try:
#             header = content_bytes[:512]  # header is enough
#             match = puremagic.from_string(header)
#             logging.info(f"pure-magic match: {match}")

#             # pure-magic returns a MagicMatch with `.mime`
#             if match and hasattr(match, "mime"):
#                 mime_type = match.mime  # e.g. "application/pdf"
#                 logging.info(f"Detected MIME via pure-magic: {mime_type}")
#         except Exception as e:
#             logging.error(f"pure-magic failed: {e}")
#             mime_type = None

#     # 2) GCS content_type
#     if not mime_type:
#         gcs_mime = blob.content_type
#         if gcs_mime and gcs_mime != "application/octet-stream":
#             mime_type = gcs_mime
#             logging.info(f"Using GCS content_type: {mime_type}")
#         else:
#             logging.info("GCS content_type was None or octet-stream—skipping")

#     # 3) Extension-based fallback
#     if not mime_type:
#         _, ext = os.path.splitext(blob.name.lower())
#         mime_type = EXTENSION_MAP.get(ext)
#         if mime_type:
#             logging.info(f"Using extension fallback: {ext} -> {mime_type}")
#         else:
#             logging.warning(f"No extension match for {blob.name}")

#     # 4) Final fallback
#     mime_type = mime_type or "application/octet-stream"
#     logging.info(f"Final MIME type for {blob.name}: {mime_type}")
#     return mime_type


# # ------------------------------------------------------------------------------
# # FastAPI app + GCP clients
# # ------------------------------------------------------------------------------

# app = FastAPI()

# storage_client = storage.Client()
# pubsub_client = pubsub_v1.PublisherClient()
# firestore_client = firestore.Client(project=GCP_PROJECT_ID)


# def topic_path(topic_name: str) -> str:
#     return pubsub_client.topic_path(GCP_PROJECT_ID, topic_name)


# @app.post("/pubsub-push")
# async def pubsub_push(request: Request):
#     """
#     Entry point for Pub/Sub push messages from the ingest topic.
#     Expected envelope: {"message": {"data": "<base64-JSON>"}}
#     """
#     envelope = await request.json()
#     if "message" not in envelope:
#         return Response(status_code=400)

#     msg = envelope["message"]
#     data = msg.get("data")
#     if data is None:
#         return Response(status_code=400)

#     payload_str = base64.b64decode(data).decode("utf-8")
#     event = json.loads(payload_str)

#     job_id = event["job_id"]
#     bucket_name = event["bucket"]
#     blob_name = event["blob"]

#     # Download the full file once (we reuse bytes for size + MIME)
#     bucket = storage_client.bucket(bucket_name)
#     blob = bucket.blob(blob_name)
#     content_bytes = blob.download_as_bytes()
#     file_size = len(content_bytes)

#     # Detect MIME type using our helper
#     mime_type = detect_mime_type(blob, content_bytes)

#     # Inspection metadata
#     inspection = {
#         "mime_type": mime_type,
#         "file_size": file_size,
#     }

#     # Update Firestore job: set INSPECTED + inspection info
#     now = dt.datetime.utcnow().isoformat() + "Z"
#     job_ref = firestore_client.collection(JOBS_COLLECTION).document(job_id)
#     job_ref.update(
#         {
#             "inspection": inspection,
#             "status": "INSPECTED",
#             "updated_at": now,
#         }
#     )

#     # Publish event to classify topic
#     classify_event = {
#         "job_id": job_id,
#         "bucket": bucket_name,
#         "blob": blob_name,
#         "mime_type": mime_type,
#         "file_size": file_size,
#     }
#     classify_data = json.dumps(classify_event).encode("utf-8")
#     pubsub_client.publish(topic_path(CLASSIFY_TOPIC), data=classify_data)

#     # Pub/Sub push needs any 2xx
#     return Response(status_code=204)


# services/inspect_worker/main.py
# services/inspect_worker/main.py

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
    if "size" in payload or "contentType" in payload:
        # We already have fresh metadata from the event — trust it
        pass
    else:
        # Internal orchestrator event — safe to reload
        try:
            blob.reload()
        except Exception as e:
            logger.error(f"Failed to reload blob metadata: {e}")
            return Response(status_code=500)

    mime_type = detect_mime_type(blob)
    file_size = blob.size or 0

    # Update Firestore
    doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
    doc_ref.set(
        {
            "inspection": {
                "mime_type": mime_type,
                "file_size": file_size,
                "inspected_at": dt.datetime.utcnow().isoformat() + "Z",
            },
            "status": "INSPECTED",
            "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        },
        merge=True,
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
