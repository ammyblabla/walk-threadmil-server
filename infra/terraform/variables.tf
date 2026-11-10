variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run and Artifact Registry. asia-southeast1 = Singapore (closest to Bangkok)."
  type        = string
  default     = "asia-southeast1"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "walk-api"
}

variable "github_repo" {
  description = "GitHub repo (owner/name) allowed to deploy via Workload Identity Federation."
  type        = string
  default     = "ammyblabla/walk-threadmil-server"
}

variable "billing_account" {
  description = "Billing account ID for the budget alert (e.g. 017D4D-XXXXXX-XXXXXX). Empty = no budget."
  type        = string
  default     = ""
}

variable "budget_amount" {
  description = "Monthly budget alert amount, in the billing account's currency (THB)."
  type        = number
  default     = 50
}
