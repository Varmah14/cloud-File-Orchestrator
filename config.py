import os

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "file-orchestrator-2025")

UPLOAD_BUCKET = os.environ.get("UPLOAD_BUCKET", "file-uploads")
PROCESSED_BUCKET = os.environ.get("PROCESSED_BUCKET", "file-organized")

INGEST_TOPIC = os.environ.get("INGEST_TOPIC", "ingest-topic")
CLASSIFY_TOPIC = os.environ.get("CLASSIFY_TOPIC", "classify-topic")
ACT_TOPIC = os.environ.get("ACT_TOPIC", "act-topic")

JOBS_COLLECTION = os.environ.get("JOBS_COLLECTION", "jobs")
RULES_COLLECTION = os.environ.get("RULES_COLLECTION", "rules")
