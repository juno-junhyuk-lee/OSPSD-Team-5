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
