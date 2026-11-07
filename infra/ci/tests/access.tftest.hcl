mock_provider "google" {}

variables {
  project_id           = "ospsd-team5"
  state_bucket         = "ospsd-team5-terraform-state"
  environment          = "verify"
  github_repository_id = "123456789"
  github_owner_id      = "987654321"
}

run "verify_access_is_scoped" {
  command = plan

  assert {
    condition     = google_cloud_run_v2_service_iam_member.deploy.name == "team5-calendar-verify"
    error_message = "Verify CI must target only the verify Cloud Run service."
  }

  assert {
    condition     = google_artifact_registry_repository_iam_member.images.repository == "team5-calendar-verify"
    error_message = "Verify CI must push only to the verify image repository."
  }

  assert {
    condition     = google_storage_bucket_iam_member.state_objects.condition[0].expression == "resource.name.startsWith(\"projects/_/buckets/ospsd-team5-terraform-state/objects/calendar/verify/\")"
    error_message = "State writes must exclude demo and CI bootstrap state."
  }

  assert {
    condition = alltrue([
      for grant in google_secret_manager_secret_iam_member.smoke :
      startswith(grant.secret_id, "team5-calendar-verify-") &&
      contains(["roles/secretmanager.viewer", "roles/secretmanager.secretAccessor"], grant.role)
    ])
    error_message = "CI must not administer secrets or access other environments."
  }
}

run "demo_uses_distinct_environment" {
  command = plan

  variables {
    environment = "demo"
  }

  assert {
    condition     = local.github_subject == "repo:juno-junhyuk-lee/OSPSD-Team-5:environment:calendar-demo" && google_service_account.deployer.account_id == "team5-calendar-demo-ci"
    error_message = "Demo must have its own GitHub Environment and deployer."
  }
}

run "reject_pull_request_ref" {
  command = plan

  variables {
    trusted_refs = ["refs/pull/46/merge"]
  }

  expect_failures = [var.trusted_refs]
}

run "reject_unknown_environment" {
  command = plan

  variables {
    environment = "production"
  }

  expect_failures = [var.environment]
}
