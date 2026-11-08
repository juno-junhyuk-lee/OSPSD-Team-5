mock_provider "google" {}

variables {
  project_id = "ospsd-team5"
}

run "bounded_dashboard_and_writer_access" {
  command = plan
  assert {
    condition     = length(jsondecode(google_monitoring_dashboard.calendar.dashboard_json).mosaicLayout.tiles) == 18
    error_message = "Keep four signals for each shared operation plus investigation and shared memory capacity."
  }
  assert {
    condition = alltrue([
      for grant in google_project_iam_member.runtime :
      contains(["roles/telemetry.writer", "roles/serviceusage.serviceUsageConsumer"], grant.role) &&
      contains(["serviceAccount:team5-calendar-demo@ospsd-team5.iam.gserviceaccount.com", "serviceAccount:team5-calendar-verify@ospsd-team5.iam.gserviceaccount.com"], grant.member)
    ])
    error_message = "Telemetry must not grant deployment, secret-reading or project-administrator access."
  }
  assert {
    condition     = alltrue([for api in google_project_service.telemetry : api.disable_on_destroy == false])
    error_message = "Tearing down the dashboard must not disable shared cloud APIs."
  }
}
