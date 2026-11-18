locals {
  region = "us-central1"
  name   = "team5-calendar-${var.environment}"

  # HW3 workflow credentials. Each is passed to the container as an env var
  # pinned to the release manifest's secret version; values never enter state.
  integration_secrets = {
    trello_api_key        = "TRELLO_API_KEY"
    trello_token          = "TRELLO_TOKEN"
    dropbox_app_key       = "DROPBOX_APP_KEY"
    dropbox_app_secret    = "DROPBOX_APP_SECRET"
    dropbox_refresh_token = "DROPBOX_REFRESH_TOKEN"
  }
  integration_settings = var.integration == null ? {} : {
    ISSUE_TRACKER_IMPLEMENTATION = "team4_trello"
    TRELLO_LIST_ID               = var.integration.trello_list_id
    STORAGE_IMPLEMENTATION       = var.integration.storage_implementation
    STORAGE_ROOT_PATH            = var.integration.storage_root_path
    # Team 3's package calls load_dotenv on import; the app requires the opt-out.
    PYTHON_DOTENV_DISABLED = "1"
  }
}

resource "google_artifact_registry_repository" "images" {
  location      = local.region
  repository_id = local.name
  format        = "DOCKER"
}

resource "google_service_account" "runtime" {
  account_id   = local.name
  display_name = "Team 5 Calendar (${var.environment}) runtime"
}

resource "google_secret_manager_secret" "runtime" {
  for_each  = toset(concat(["oauth", "bearer"], [for key, _ in local.integration_secrets : replace(key, "_", "-")]))
  secret_id = "${local.name}-${each.key}"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = google_secret_manager_secret.runtime
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_service" "calendar" {
  count               = var.release == null ? 0 : 1
  name                = local.name
  location            = local.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  # The app verifies the demo bearer before routing requests.
  invoker_iam_disabled = true

  scaling {
    min_instance_count = 0
    max_instance_count = 1
  }

  template {
    service_account                  = google_service_account.runtime.email
    max_instance_request_concurrency = 1
    timeout                          = "90s"

    containers {
      image = "${local.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/calendar@${var.release.digest}"

      ports {
        container_port = 8080
      }

      resources {
        limits = { cpu = "1", memory = "512Mi" }
        # Background OTLP workers must run after the HTTP response ends.
        cpu_idle = false
      }

      env {
        name  = "CALENDAR_MODE"
        value = "hosted"
      }
      env {
        name  = "CALENDAR_ENV"
        value = var.environment
      }
      env {
        name  = "CALENDAR_TELEMETRY_PROJECT"
        value = var.project_id
      }
      env {
        name  = "CALENDAR_RELEASE"
        value = var.release.commit
      }
      env {
        name  = "CALENDAR_TOKEN_FILE"
        value = "/var/secrets/oauth/token.json"
      }
      env {
        name  = "CALENDAR_BEARER_FILE"
        value = "/var/secrets/bearer/key"
      }

      dynamic "env" {
        for_each = local.integration_settings
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.integration == null ? {} : local.integration_secrets
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.runtime[replace(env.key, "_", "-")].secret_id
              version = tostring(var.integration.secret_versions[env.key])
            }
          }
        }
      }

      volume_mounts {
        name       = "oauth"
        mount_path = "/var/secrets/oauth"
      }
      volume_mounts {
        name       = "bearer"
        mount_path = "/var/secrets/bearer"
      }

      startup_probe {
        http_get {
          path = "/ready"
        }
        period_seconds    = 5
        timeout_seconds   = 2
        failure_threshold = 12
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds  = 30
        timeout_seconds = 2
      }
    }

    volumes {
      name = "oauth"
      secret {
        secret = google_secret_manager_secret.runtime["oauth"].secret_id
        items {
          version = tostring(var.release.oauth_version)
          path    = "token.json"
        }
      }
    }

    volumes {
      name = "bearer"
      secret {
        secret = google_secret_manager_secret.runtime["bearer"].secret_id
        items {
          version = tostring(var.release.bearer_version)
          path    = "key"
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.runtime]
}
