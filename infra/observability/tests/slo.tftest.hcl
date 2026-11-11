mock_provider "google" {}

override_resource {
  target          = google_monitoring_dashboard.calendar
  override_during = plan
  values = {
    id = "projects/ospsd-team5/dashboards/test-dashboard"
  }
}

variables {
  project_id = "ospsd-team5"
}

run "slo_scope_and_burn_alerts" {
  command = plan
  assert {
    condition     = google_monitoring_slo.availability.goal == 0.99 && google_monitoring_slo.latency.goal == 0.95
    error_message = "Keep the documented 99% availability and 95% latency objectives."
  }
  assert {
    condition     = strcontains(google_monitoring_slo.availability.request_based_sli[0].good_total_ratio[0].bad_service_filter, "service|provider")
    error_message = "Only service and provider failures may consume the availability budget."
  }
  assert {
    condition     = strcontains(google_monitoring_slo.latency.request_based_sli[0].distribution_cut[0].distribution_filter, "outcome=\"success\"")
    error_message = "Do not mix success and error latency in the latency SLI."
  }
  assert {
    condition     = alltrue([for policy in google_monitoring_alert_policy.burn_rate : length(policy.conditions) == 2])
    error_message = "Each SLO needs a fast and a slow burn-rate condition."
  }
  assert {
    condition = alltrue([
      for policy in google_monitoring_alert_policy.burn_rate :
      [for link in policy.documentation[0].links : link.display_name] == ["Dashboard", "Runbook"] &&
      endswith(policy.documentation[0].links[0].url, "/dashboards/custom/test-dashboard?project=ospsd-team5") &&
      endswith(policy.documentation[0].links[1].url, "docs/SLO.md#runbook") &&
      strcontains(policy.documentation[0].content, "[Runbook](")
    ])
    error_message = "Each alert must link to the dashboard and the runbook."
  }
  assert {
    condition     = length(google_monitoring_notification_channel.email) == 0
    error_message = "No notification channel unless an address is configured."
  }
}
