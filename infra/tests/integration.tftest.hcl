mock_provider "google" {
  mock_resource "google_secret_manager_secret" {
    defaults = {
      id = "projects/ospsd-team5/secrets/mock"
    }
  }
}

variables {
  project_id  = "ospsd-team5"
  environment = "verify"
  release = {
    commit         = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    digest         = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    oauth_version  = 2
    bearer_version = 3
  }
  integration = {
    storage_implementation = "team3_dropbox"
    storage_root_path      = "/ospsd-team5-hw3"
    trello_list_id         = "0123456789abcdef01234567"
    secret_versions = {
      trello_api_key        = 4
      trello_token          = 5
      dropbox_app_key       = 6
      dropbox_app_secret    = 7
      dropbox_refresh_token = 8
    }
  }
}

run "workflow_settings_and_pinned_secrets" {
  command = plan

  assert {
    condition = keys(google_secret_manager_secret.runtime) == [
      "bearer", "dropbox-app-key", "dropbox-app-secret", "dropbox-refresh-token",
      "oauth", "trello-api-key", "trello-token",
    ]
    error_message = "Each workflow credential needs its own Secret Manager secret."
  }

  assert {
    condition     = length(google_secret_manager_secret_iam_member.runtime) == 7
    error_message = "The runtime service account must read every workflow secret."
  }

  assert {
    condition = {
      for env in google_cloud_run_v2_service.calendar[0].template[0].containers[0].env :
      env.name => env.value if env.value != null && env.value != ""
      } == {
      CALENDAR_MODE                = "hosted"
      CALENDAR_ENV                 = "verify"
      CALENDAR_TELEMETRY_PROJECT   = "ospsd-team5"
      CALENDAR_RELEASE             = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      CALENDAR_TOKEN_FILE          = "/var/secrets/oauth/token.json"
      CALENDAR_BEARER_FILE         = "/var/secrets/bearer/key"
      ISSUE_TRACKER_IMPLEMENTATION = "team4_trello"
      TRELLO_LIST_ID               = "0123456789abcdef01234567"
      STORAGE_IMPLEMENTATION       = "team3_dropbox"
      STORAGE_ROOT_PATH            = "/ospsd-team5-hw3"
      PYTHON_DOTENV_DISABLED       = "1"
    }
    error_message = "Plain settings must match the integration manifest exactly."
  }

  assert {
    condition = {
      for env in google_cloud_run_v2_service.calendar[0].template[0].containers[0].env :
      env.name => "${env.value_source[0].secret_key_ref[0].secret}@${env.value_source[0].secret_key_ref[0].version}"
      if length(env.value_source) > 0
      } == {
      TRELLO_API_KEY        = "team5-calendar-verify-trello-api-key@4"
      TRELLO_TOKEN          = "team5-calendar-verify-trello-token@5"
      DROPBOX_APP_KEY       = "team5-calendar-verify-dropbox-app-key@6"
      DROPBOX_APP_SECRET    = "team5-calendar-verify-dropbox-app-secret@7"
      DROPBOX_REFRESH_TOKEN = "team5-calendar-verify-dropbox-refresh-token@8"
    }
    error_message = "Credentials must come from pinned Secret Manager versions."
  }
}

run "team1_swap_changes_only_the_selector" {
  command = plan

  variables {
    integration = {
      storage_implementation = "team1_dropbox"
      storage_root_path      = "/ospsd-team5-hw3"
      trello_list_id         = "0123456789abcdef01234567"
      secret_versions = {
        trello_api_key        = 4
        trello_token          = 5
        dropbox_app_key       = 6
        dropbox_app_secret    = 7
        dropbox_refresh_token = 8
      }
    }
  }

  assert {
    condition = [
      for env in google_cloud_run_v2_service.calendar[0].template[0].containers[0].env :
      env.value if env.name == "STORAGE_IMPLEMENTATION"
    ] == ["team1_dropbox"]
    error_message = "The swap must select Team 1 storage."
  }
}

run "hw2_release_has_no_workflow_settings" {
  command = plan

  variables {
    integration = null
  }

  assert {
    condition     = length(google_cloud_run_v2_service.calendar[0].template[0].containers[0].env) == 6
    error_message = "A release without integration must keep the HW2 container settings."
  }
}

run "rejects_unknown_storage" {
  command = plan

  variables {
    integration = {
      storage_implementation = "team2_dropbox"
      storage_root_path      = "/ospsd-team5-hw3"
      trello_list_id         = "0123456789abcdef01234567"
      secret_versions = {
        trello_api_key        = 4
        trello_token          = 5
        dropbox_app_key       = 6
        dropbox_app_secret    = 7
        dropbox_refresh_token = 8
      }
    }
  }

  expect_failures = [var.integration]
}
