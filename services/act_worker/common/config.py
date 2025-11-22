import os

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "demucs-lab")

UPLOAD_BUCKET = os.environ.get("UPLOAD_BUCKET", "drbfo-uploads")
PROCESSED_BUCKET = os.environ.get("PROCESSED_BUCKET", "drbfo-organized")

INGEST_TOPIC = os.environ.get("INGEST_TOPIC", "ingest-topic")
CLASSIFY_TOPIC = os.environ.get("CLASSIFY_TOPIC", "drbfo-classify")
ACT_TOPIC = os.environ.get("ACT_TOPIC", "drbfo-act")

JOBS_COLLECTION = os.environ.get("JOBS_COLLECTION", "jobs")
