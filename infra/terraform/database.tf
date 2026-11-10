# ───────────── Neon Postgres connection strings ─────────────
# Terraform creates the secret *containers* and access rules only. The values are added
# out-of-band (see docs/deploy/cloud-run.md "Database") so passwords never land in TF state.
#   database-url         pooled endpoint (-pooler), used by the API
#   database-url-direct  direct endpoint, used by migrations (DDL, no PgBouncer)
locals {
  db_secrets = toset(["database-url", "database-url-direct"])
}

resource "google_secret_manager_secret" "db" {
  for_each  = local.db_secrets
  secret_id = each.value

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runtime_db" {
  for_each  = google_secret_manager_secret.db
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# ───────────── migrations: run by GitHub Actions before each deploy ─────────────
# CI reads database-url-direct and runs `alembic upgrade head` on the runner (Actions logs show
# the output). Only the deployer identity — reachable solely from main of this repo via WIF —
# may read this one secret. (A Cloud Run job was used first; jobs in asia-southeast1 failed with
# "exit code 0, Unknown error" and no logs, see docs/deploy/cloud-run.md.)
resource "google_secret_manager_secret_iam_member" "deployer_db_direct" {
  secret_id = google_secret_manager_secret.db["database-url-direct"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.deployer.email}"
}
