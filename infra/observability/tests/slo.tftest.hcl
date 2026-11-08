mock_provider "google" {}

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
    condition     = length(google_monitoring_notification_channel.email) == 0
    error_message = "No notification channel unless an address is configured."
  }
}
