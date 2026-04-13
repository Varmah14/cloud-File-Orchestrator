project_id         = "my-file-orchestrator"
region             = "us-central1"
firestore_location = "us-central"

upload_bucket    = "mfo-uploads"
processed_bucket = "mfo-organized"

ingest_topic   = "ingest-topic"
classify_topic = "classify-topic"
act_topic      = "act-topic"

jobs_collection  = "jobs"
rules_collection = "rules"

ui_origins = "*"

api_image      = "us-central1-docker.pkg.dev/my-file-orchestrator/cloud-run-source-deploy/drbfo-api:latest"
inspect_image  = "us-central1-docker.pkg.dev/my-file-orchestrator/cloud-run-source-deploy/drbfo-inspect:latest"
classify_image = "us-central1-docker.pkg.dev/my-file-orchestrator/cloud-run-source-deploy/drbfo-classify:latest"
act_image      = "us-central1-docker.pkg.dev/my-file-orchestrator/cloud-run-source-deploy/drbfo-act:latest"
