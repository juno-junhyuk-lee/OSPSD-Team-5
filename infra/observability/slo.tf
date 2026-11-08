variable "slo_environment" {
  type    = string
  default = "demo"
}

variable "alert_email" {
  type    = string
  default = ""
}

locals {
  shared_operations = "monitoring.regex.full_match(\"create|get|replace|delete\")"
  slo_selector      = "resource.type=\"prometheus_target\" AND metric.labels.environment=\"${var.slo_environment}\" AND metric.labels.operation=${local.shared_operations}"

  burn_windows = {
    fast = { lookback = "3600s", threshold = 14.4, duration = "0s" }
    slow = { lookback = "21600s", threshold = 6, duration = "300s" }
  }
}

resource "google_monitoring_custom_service" "calendar" {
  project      = var.project_id
  service_id   = "team5-calendar-${var.slo_environment}"
  display_name = "Team 5 Calendar (${var.slo_environment})"
  depends_on   = [google_project_service.telemetry]
}

# Caller outcomes (invalid_input, not_found, access_denied) are excluded from "bad": they are correct rejections.
resource "google_monitoring_slo" "availability" {
  project             = var.project_id
  service             = google_monitoring_custom_service.calendar.service_id
  slo_id              = "availability"
  display_name        = "99% of shared-operation requests avoid service/provider failure (28d)"
  goal                = 0.99
  rolling_period_days = 28
  request_based_sli {
    good_total_ratio {
      total_service_filter = "metric.type=\"prometheus.googleapis.com/calendar.requests/counter\" AND ${local.slo_selector}"
      bad_service_filter   = "metric.type=\"prometheus.googleapis.com/calendar.request.errors/counter\" AND ${local.slo_selector} AND metric.labels.failure_source=monitoring.regex.full_match(\"service|provider\")"
    }
  }
}

resource "google_monitoring_slo" "latency" {
  project             = var.project_id
  service             = google_monitoring_custom_service.calendar.service_id
  slo_id              = "latency"
  display_name        = "95% of successful shared-operation requests finish within 1 s (28d)"
  goal                = 0.95
  rolling_period_days = 28
  request_based_sli {
    distribution_cut {
      distribution_filter = "metric.type=\"prometheus.googleapis.com/calendar.request.duration/histogram\" AND ${local.slo_selector} AND metric.labels.outcome=\"success\""
      range {
        max = 1
      }
    }
  }
}

resource "google_monitoring_notification_channel" "email" {
  count        = var.alert_email == "" ? 0 : 1
  project      = var.project_id
  display_name = "Team 5 Calendar SLO alerts"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
}

resource "google_monitoring_alert_policy" "burn_rate" {
  for_each     = { availability = google_monitoring_slo.availability.name, latency = google_monitoring_slo.latency.name }
  project      = var.project_id
  display_name = "Team 5 Calendar ${each.key} error-budget burn (${var.slo_environment})"
  combiner     = "OR"
  dynamic "conditions" {
    for_each = local.burn_windows
    content {
      display_name = "${conditions.key} burn: ${conditions.value.threshold}x over ${conditions.value.lookback}"
      condition_threshold {
        filter          = "select_slo_burn_rate(\"${each.value}\", \"${conditions.value.lookback}\")"
        comparison      = "COMPARISON_GT"
        threshold_value = conditions.value.threshold
        duration        = conditions.value.duration
      }
    }
  }
  notification_channels = google_monitoring_notification_channel.email[*].id
  documentation {
    content   = "See docs/SLO.md for the error-budget policy. Uncertain POST/PUT results keep retryable=false; this alert does not authorize retries."
    mime_type = "text/markdown"
  }
}
