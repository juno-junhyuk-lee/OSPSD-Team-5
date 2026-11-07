output "image_repository" {
  value = "${local.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/calendar"
}

output "secret_ids" {
  value = { for name, secret in google_secret_manager_secret.runtime : name => secret.secret_id }
}

output "service_url" {
  value = one(google_cloud_run_v2_service.calendar[*].uri)
}
