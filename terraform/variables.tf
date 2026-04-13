###############################################################################
# variables.tf — cloud-file-orchestrator
# Project: my-file-orchestrator
###############################################################################

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "my-file-orchestrator"
}

variable "region" {
  description = "Cloud Run / GCS region"
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore location"
  type        = string
  default     = "us-central"
}

# ── Buckets ──────────────────────────────────────────────────────────────────

variable "upload_bucket" {
  description = "GCS bucket where files are uploaded (source)"
  type        = string
  default     = "mfo-uploads"
}

variable "processed_bucket" {
  description = "GCS bucket where processed files land"
  type        = string
  default     = "mfo-organized"
}

# ── Pub/Sub topics ────────────────────────────────────────────────────────────

variable "ingest_topic" {
  description = "Pub/Sub topic for raw GCS upload events"
  type        = string
  default     = "ingest-topic"
}

variable "classify_topic" {
  description = "Pub/Sub topic between inspect → classify workers"
  type        = string
  default     = "classify-topic"
}

variable "act_topic" {
  description = "Pub/Sub topic between classify → act workers"
  type        = string
  default     = "act-topic"
}

# ── Firestore collections ────────────────────────────────────────────────────

variable "jobs_collection" {
  description = "Firestore collection for job tracking"
  type        = string
  default     = "jobs"
}

variable "rules_collection" {
  description = "Firestore collection for routing rules"
  type        = string
  default     = "rules"
}

# ── Container images ──────────────────────────────────────────────────────────

variable "api_image" {
  description = "Container image URI for the API service"
  type        = string
  default     = "us-central1-docker.pkg.dev/my-file-orchestrator/cloud-run-source-deploy/drbfo-api:latest"
}

variable "inspect_image" {
  description = "Container image URI for the inspect worker"
  type        = string
  default     = "us-central1-docker.pkg.dev/my-file-orchestrator/cloud-run-source-deploy/drbfo-inspect:latest"
}

variable "classify_image" {
  description = "Container image URI for the classify worker"
  type        = string
  default     = "us-central1-docker.pkg.dev/my-file-orchestrator/cloud-run-source-deploy/drbfo-classify:latest"
}

variable "act_image" {
  description = "Container image URI for the act worker"
  type        = string
  default     = "us-central1-docker.pkg.dev/my-file-orchestrator/cloud-run-source-deploy/drbfo-act:latest"
}

# ── API config ────────────────────────────────────────────────────────────────

variable "ui_origins" {
  description = "CORS allowed origins for the API (comma-separated or *)"
  type        = string
  default     = "*"
}
