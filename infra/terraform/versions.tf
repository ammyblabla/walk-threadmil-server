terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }

  # Bucket is passed at init time:
  #   terraform init -backend-config="bucket=walk-treadmil-tfstate"
  backend "gcs" {
    prefix = "server"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region

  # Billing Budgets API needs a quota project when using user credentials.
  user_project_override = true
  billing_project       = var.project_id
}
