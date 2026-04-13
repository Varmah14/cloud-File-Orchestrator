###############################################################################
# outputs.tf — cloud-file-orchestrator
###############################################################################

output "api_url" {
  description = "Public URL of the API service"
  value       = google_cloud_run_v2_service.api.uri
}

output "inspect_url" {
  description = "URL of the inspect worker"
  value       = google_cloud_run_v2_service.inspect.uri
}

output "classify_url" {
  description = "URL of the classify worker"
  value       = google_cloud_run_v2_service.classify.uri
}

output "act_url" {
  description = "URL of the act worker"
  value       = google_cloud_run_v2_service.act.uri
}

output "upload_bucket" {
  description = "GCS bucket for incoming uploads"
  value       = google_storage_bucket.uploads.name
}

output "processed_bucket" {
  description = "GCS bucket for organized files"
  value       = google_storage_bucket.organized.name
}

output "pubsub_invoker_sa" {
  description = "Service account used for Pub/Sub push auth"
  value       = google_service_account.pubsub_invoker.email
}
