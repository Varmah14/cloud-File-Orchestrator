###############################################################################
# cloud-file-orchestrator — Terraform
# Project: my-file-orchestrator  |  Region: us-central1
###############################################################################

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

###############################################################################
# Enable required APIs
###############################################################################

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "firestore.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

###############################################################################
# GCS Buckets
###############################################################################

resource "google_storage_bucket" "uploads" {
  name          = var.upload_bucket
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition { age = 30 }
    action    { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket" "organized" {
  name          = var.processed_bucket
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  depends_on = [google_project_service.apis]
}

###############################################################################
# Pub/Sub Topics
###############################################################################

resource "google_pubsub_topic" "ingest" {
  name       = var.ingest_topic
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "classify" {
  name       = var.classify_topic
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "act" {
  name       = var.act_topic
  depends_on = [google_project_service.apis]
}

###############################################################################
# GCS → Pub/Sub notification (fires on every upload)
###############################################################################

data "google_storage_project_service_account" "gcs_sa" {
  project = var.project_id
}

resource "google_pubsub_topic_iam_member" "gcs_publish_ingest" {
  topic  = google_pubsub_topic.ingest.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_sa.email_address}"
}

resource "google_storage_notification" "upload_trigger" {
  bucket         = google_storage_bucket.uploads.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.ingest.id
  event_types    = ["OBJECT_FINALIZE"]

  depends_on = [google_pubsub_topic_iam_member.gcs_publish_ingest]
}

###############################################################################
# Firestore (Native mode)
###############################################################################

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

###############################################################################
# Service Account for Pub/Sub → Cloud Run push auth
###############################################################################

resource "google_service_account" "pubsub_invoker" {
  account_id   = "pubsub-cloud-run-invoker"
  display_name = "Pub/Sub → Cloud Run push invoker"
  depends_on   = [google_project_service.apis]
}

resource "google_project_iam_member" "pubsub_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

data "google_project" "project" {
  project_id = var.project_id
}

###############################################################################
# Cloud Run Services
###############################################################################

locals {
  common_env = [
    { name = "GCP_PROJECT_ID",   value = var.project_id },
    { name = "UPLOAD_BUCKET",    value = var.upload_bucket },
    { name = "SOURCE_BUCKET",    value = var.upload_bucket },
    { name = "PROCESSED_BUCKET", value = var.processed_bucket },
    { name = "INGEST_TOPIC",     value = var.ingest_topic },
    { name = "CLASSIFY_TOPIC",   value = var.classify_topic },
    { name = "ACT_TOPIC",        value = var.act_topic },
    { name = "JOBS_COLLECTION",  value = var.jobs_collection },
    { name = "RULES_COLLECTION", value = var.rules_collection },
  ]
}

# ── API ──────────────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "api" {
  name     = "drbfo-api"
  location = var.region

  template {
    containers {
      image = var.api_image

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      env {
        name  = "UI_ORIGINS"
        value = var.ui_origins
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Inspect Worker ────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "inspect" {
  name     = "drbfo-inspect"
  location = var.region

  template {
    containers {
      image = var.inspect_image

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.value.name
          value = env.value.value
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "inspect_invoker" {
  name     = google_cloud_run_v2_service.inspect.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

# ── Classify Worker ───────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "classify" {
  name     = "drbfo-classify"
  location = var.region

  template {
    containers {
      image = var.classify_image

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.value.name
          value = env.value.value
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "classify_invoker" {
  name     = google_cloud_run_v2_service.classify.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

# ── Act Worker ────────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "act" {
  name     = "drbfo-act"
  location = var.region

  template {
    containers {
      image = var.act_image

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.value.name
          value = env.value.value
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "act_invoker" {
  name     = google_cloud_run_v2_service.act.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

###############################################################################
# Pub/Sub Push Subscriptions → Cloud Run /pubsub-push
###############################################################################

resource "google_pubsub_subscription" "ingest_to_inspect" {
  name  = "ingest-sub"
  topic = google_pubsub_topic.ingest.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.inspect.uri}/pubsub-push"
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  ack_deadline_seconds       = 60
  message_retention_duration = "600s"
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  depends_on = [google_cloud_run_v2_service.inspect]
}

resource "google_pubsub_subscription" "classify_to_classify" {
  name  = "classify-sub"
  topic = google_pubsub_topic.classify.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.classify.uri}/pubsub-push"
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  ack_deadline_seconds       = 60
  message_retention_duration = "600s"
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  depends_on = [google_cloud_run_v2_service.classify]
}

resource "google_pubsub_subscription" "act_to_act" {
  name  = "act-sub"
  topic = google_pubsub_topic.act.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.act.uri}/pubsub-push"
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  ack_deadline_seconds       = 60
  message_retention_duration = "600s"
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  depends_on = [google_cloud_run_v2_service.act]
}
