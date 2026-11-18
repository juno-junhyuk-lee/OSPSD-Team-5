variable "project_id" {
  type        = string
  description = "Dedicated, billing-enabled Team 5 GCP project."
}

variable "environment" {
  type        = string
  default     = "demo"
  description = "Resource name suffix. Use a separate state prefix for each environment."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,11}$", var.environment)) && !endswith(var.environment, "-")
    error_message = "Use up to 12 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "release" {
  type = object({
    commit         = string
    digest         = string
    oauth_version  = number
    bearer_version = number
  })
  default     = null
  description = "Null provisions the foundations only. Set a commit, image digest and secret version numbers to create the service."

  validation {
    condition = var.release == null ? true : (
      can(regex("^[0-9a-f]{40}$", var.release.commit)) &&
      can(regex("^sha256:[0-9a-f]{64}$", var.release.digest)) &&
      var.release.oauth_version >= 1 && floor(var.release.oauth_version) == var.release.oauth_version &&
      var.release.bearer_version >= 1 && floor(var.release.bearer_version) == var.release.bearer_version
    )
    error_message = "Supply a full commit SHA, a sha256 image digest and positive integer secret versions."
  }
}

variable "integration" {
  type = object({
    storage_implementation = string
    storage_root_path      = string
    trello_list_id         = string
    secret_versions = object({
      trello_api_key        = number
      trello_token          = number
      dropbox_app_key       = number
      dropbox_app_secret    = number
      dropbox_refresh_token = number
    })
  })
  default     = null
  description = "HW3 workflow settings. Null deploys the Calendar API without Trello or Dropbox configuration."

  validation {
    condition = var.integration == null ? true : (
      contains(["team3_dropbox", "team1_dropbox"], var.integration.storage_implementation) &&
      can(regex("^/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$", var.integration.storage_root_path)) &&
      can(regex("^[0-9a-f]{24}$", var.integration.trello_list_id)) &&
      alltrue([
        for version in values(var.integration.secret_versions) :
        version >= 1 && floor(version) == version
      ])
    )
    error_message = "Use team3_dropbox or team1_dropbox, an absolute storage root, a 24-character Trello list ID and positive integer secret versions."
  }
}
