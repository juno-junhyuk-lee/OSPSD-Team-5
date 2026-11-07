output "github_environment" {
  value = local.github_environment
}

output "github_environment_variables" {
  description = "Non-secret GitHub Environment variables for the deployment workflow."
  value = {
    GCP_PROJECT_ID                 = var.project_id
    GCP_WORKLOAD_IDENTITY_PROVIDER = google_iam_workload_identity_pool_provider.github.name
    GCP_DEPLOYER_SERVICE_ACCOUNT   = google_service_account.deployer.email
    TF_STATE_BUCKET                = var.state_bucket
    CALENDAR_ENV                   = var.environment
  }
}

output "trusted_refs" {
  value = sort(tolist(var.trusted_refs))
}
