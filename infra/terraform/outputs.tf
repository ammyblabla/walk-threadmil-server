output "service_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "image_repo" {
  description = "Push images here: <image_repo>/api:<tag>"
  value       = local.image_repo
}

# ── Copy these into GitHub → Settings → Secrets and variables → Actions → Variables ──
output "github_variables" {
  value = {
    GCP_PROJECT_ID = var.project_id
    GCP_REGION     = var.region
    SERVICE_NAME   = var.service_name
    MIGRATE_JOB    = google_cloud_run_v2_job.migrate.name
    IMAGE_REPO     = local.image_repo
    WIF_PROVIDER   = google_iam_workload_identity_pool_provider.github.name
    DEPLOYER_SA    = google_service_account.deployer.email
  }
}
