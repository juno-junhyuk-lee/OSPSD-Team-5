terraform {
  required_version = "~> 1.13.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }

  # An administrator initializes this root with calendar/ci/<environment>.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = "us-central1"
}
