variable "project_id" {
  type = string
}

locals {
  operations = ["create", "get", "replace", "delete"]
  charts = [
    { title = "Traffic (requests/s)", metric = "calendar.requests/counter", aligner = "ALIGN_RATE", reducer = "REDUCE_SUM" },
    { title = "Errors by outcome (requests/s)", metric = "calendar.request.errors/counter", aligner = "ALIGN_RATE", reducer = "REDUCE_SUM" },
    { title = "Latency p95 (s)", metric = "calendar.request.duration/histogram", aligner = "ALIGN_DELTA", reducer = "REDUCE_PERCENTILE_95" },
    { title = "Entry concurrency / limit, p99", metric = "calendar.request.saturation/histogram", aligner = "ALIGN_DELTA", reducer = "REDUCE_PERCENTILE_99" },
  ]
}

# Separate administrator-owned state; deployment CI cannot change project IAM.
resource "google_project_service" "telemetry" {
  for_each           = toset(["telemetry.googleapis.com", "monitoring.googleapis.com", "cloudtrace.googleapis.com", "logging.googleapis.com"])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_iam_member" "runtime" {
  for_each = {
    for grant in setproduct(["demo", "verify"], ["roles/telemetry.writer", "roles/serviceusage.serviceUsageConsumer"]) :
    "${grant[0]}:${grant[1]}" => { environment = grant[0], role = grant[1] }
  }
  project    = var.project_id
  role       = each.value.role
  member     = "serviceAccount:team5-calendar-${each.value.environment}@${var.project_id}.iam.gserviceaccount.com"
  depends_on = [google_project_service.telemetry]
}

resource "google_monitoring_dashboard" "calendar" {
  project = var.project_id
  dashboard_json = jsonencode({
    displayName = "Team 5 Calendar: Level 3"
    mosaicLayout = {
      columns = 24
      tiles = concat([
        {
          width = 24, height = 3
          widget = {
            title = "Release and investigation"
            text = {
              format = "MARKDOWN"
              content = join("\n\n", [
                "Every series shows its release and environment in the legend. Choose the time range of the request. No traffic or missing data is not evidence of health; do not fill gaps with zero.",
                "Latency separates success and failure. Errors include caller, service and provider outcomes, not an SLO definition. A successful HTTP response still needs conformance/read-back checks.",
                "Saturation samples active shared-operation requests at entry / concurrency limit 1 (Cloud Run, one worker). Short requests are preserved; this is not time-weighted utilization or a queue measurement. Platform memory utilization is below.",
                "[Outcome logs](https://console.cloud.google.com/logs/query?project=${var.project_id}) — filter jsonPayload.service=\"calendar-team-5\", then release, contract_operation, outcome and trace ID. Open the log's Trace link for the request and Google child spans.",
                "[Cloud Trace](https://console.cloud.google.com/traces/list?project=${var.project_id}) — use the trace ID returned in X-Trace-ID. Observations are asynchronous and can take several minutes to appear."
              ])
            }
          }
        }
        ], flatten([
          for row, operation in local.operations : [
            for col, chart in local.charts : {
              # The API omits zero coordinates; match it to avoid perpetual diffs.
              for key, value in {
                xPos = col * 6, yPos = 3 + row * 4, width = 6, height = 4
                widget = {
                  title = "${operation}: ${chart.title}"
                  xyChart = {
                    chartOptions = { mode = "COLOR" }
                    dataSets = [{
                      plotType       = "LINE"
                      legendTemplate = "$${metric.labels.release} $${metric.labels.environment} $${metric.labels.outcome}"
                      timeSeriesQuery = {
                        timeSeriesFilter = {
                          filter = "resource.type=\"prometheus_target\" AND metric.type=\"prometheus.googleapis.com/${chart.metric}\" AND metric.labels.operation=\"${operation}\""
                          aggregation = {
                            alignmentPeriod    = "60s"
                            perSeriesAligner   = chart.aligner
                            crossSeriesReducer = chart.reducer
                            groupByFields      = chart.metric == "calendar.request.saturation/histogram" ? ["metric.labels.release", "metric.labels.environment"] : ["metric.labels.release", "metric.labels.environment", "metric.labels.outcome"]
                          }
                        }
                      }
                    }]
                  }
                }
              } : key => value if key != "xPos" || value != 0
            }
          ]
        ]), [
        {
          yPos = 19, width = 24, height = 4
          widget = {
            title = "Cloud Run instance memory / configured limit (all operations share this capacity)"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/container/memory/utilizations\" AND resource.labels.service_name=monitoring.regex.full_match(\"team5-calendar-(demo|verify)\")"
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_99", crossSeriesReducer = "REDUCE_MAX", groupByFields = ["resource.labels.service_name", "resource.labels.revision_name"] }
                  }
                }
              }]
            }
          }
        }
      ])
    }
  })
  depends_on = [google_project_service.telemetry]
}

output "dashboard_url" {
  value = local.dashboard_url
}
