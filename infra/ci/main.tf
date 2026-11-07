locals {
  name               = "team5-calendar-${var.environment}"
  github_environment = "calendar-${var.environment}"
  github_subject = format(
    "repo:%s@%s/%s@%s:environment:%s",
    split("/", var.github_repository)[0], var.github_owner_id,
    split("/", var.github_repository)[1], var.github_repository_id,
    local.github_environment,
  )
  state_prefix      = "calendar/${var.environment}/"
  state_object_path = "projects/_/buckets/${var.state_bucket}/objects/${local.state_prefix}"
  secret_roles      = toset(["roles/secretmanager.viewer", "roles/secretmanager.secretAccessor"])
  secret_grants = {
    for grant in setproduct(["oauth", "bearer"], local.secret_roles) :
    "${grant[0]}:${grant[1]}" => { secret = grant[0], role = grant[1] }
  }
}

resource "google_project_service" "federation" {
  for_each           = toset(["iam.googleapis.com", "iamcredentials.googleapis.com", "sts.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "deployer" {
  account_id   = "${local.name}-ci"
  display_name = "Calendar ${var.environment} GitHub deployer"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "team5-github-${var.environment}"
  display_name              = "Calendar ${var.environment} GitHub"
  depends_on                = [google_project_service.federation]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  attribute_mapping = {
    "google.subject" = "assertion.sub"
  }
  attribute_condition = join(" && ", [
    "assertion.repository_id == ${jsonencode(var.github_repository_id)}",
    "assertion.repository_owner_id == ${jsonencode(var.github_owner_id)}",
    "assertion.repository == ${jsonencode(var.github_repository)}",
    "assertion.sub == ${jsonencode(local.github_subject)}",
    "assertion.ref in ${jsonencode(sort(tolist(var.trusted_refs)))}",
    "assertion.event_name in ['push', 'workflow_dispatch']",
  ])

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principal://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/subject/${local.github_subject}"
}

# Level 1 resources must exist first. CI updates releases, not foundations or IAM.
resource "google_cloud_run_v2_service_iam_member" "deploy" {
  project  = var.project_id
  location = "us-central1"
  name     = local.name
  # Admin on this service is needed for invoker_iam_disabled; never project-wide.
  role   = "roles/run.admin"
  member = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "runtime" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.name}@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_artifact_registry_repository_iam_member" "images" {
  project    = var.project_id
  location   = "us-central1"
  repository = local.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_secret_manager_secret_iam_member" "smoke" {
  for_each  = local.secret_grants
  project   = var.project_id
  secret_id = "${local.name}-${each.value.secret}"
  role      = each.value.role
  # The current smoke script uses OAuth for independent Google read-back.
  member = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "quota" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Operation polling is project-scoped even when service updates use service IAM.
resource "google_project_iam_custom_role" "operations" {
  project     = var.project_id
  role_id     = "calendar_${var.environment}_operation_reader"
  title       = "Calendar ${var.environment} operation reader"
  permissions = ["run.operations.get"]
}

resource "google_project_iam_member" "operations" {
  project = var.project_id
  role    = google_project_iam_custom_role.operations.name
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_storage_bucket_iam_member" "state_objects" {
  bucket = var.state_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.deployer.email}"

  condition {
    title       = "calendar-${var.environment}-state-only"
    description = "Release state and locks only; excludes CI bootstrap and other environments."
    expression  = "resource.name.startsWith(${jsonencode(local.state_object_path)})"
  }
}

resource "google_storage_bucket_iam_member" "state_listing" {
  bucket = var.state_bucket
  # GCS workspace discovery lists names; this does not grant object reads.
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.deployer.email}"
}
