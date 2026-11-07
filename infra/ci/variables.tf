variable "project_id" {
  type        = string
  description = "Project containing the existing Level 1 deployment."
}

variable "state_bucket" {
  type        = string
  description = "Existing Terraform state bucket name, without gs://."
}

variable "environment" {
  type        = string
  description = "Existing deployment to authorize; use separate CI state for each environment."

  validation {
    condition     = contains(["demo", "verify"], var.environment)
    error_message = "Select demo or verify."
  }
}

variable "github_repository" {
  type        = string
  default     = "juno-junhyuk-lee/OSPSD-Team-5"
  description = "Exact, case-sensitive GitHub owner/repository used in the OIDC subject."

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Supply owner/repository."
  }
}

variable "github_repository_id" {
  type        = string
  description = "Immutable numeric GitHub repository ID, not the repository name."

  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_id))
    error_message = "Supply the numeric repository ID returned by GitHub."
  }
}

variable "github_owner_id" {
  type        = string
  description = "Immutable numeric GitHub owner ID."

  validation {
    condition     = can(regex("^[0-9]+$", var.github_owner_id))
    error_message = "Supply the numeric repository owner ID returned by GitHub."
  }
}

variable "trusted_refs" {
  type = set(string)
  default = [
    "refs/heads/hw2/milestone-3-level-2",
    "refs/heads/hw2/milestone-3",
    "refs/heads/main",
  ]
  description = "Branches permitted to deploy; PR refs and tags are excluded."

  validation {
    condition     = length(var.trusted_refs) > 0 && alltrue([for ref in var.trusted_refs : startswith(ref, "refs/heads/") && length(ref) > 11])
    error_message = "Supply at least one full refs/heads/<branch> reference."
  }
}
