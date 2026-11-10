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

# ───────────── migrations: Cloud Run job, executed by CI before each deploy ─────────────
resource "google_cloud_run_v2_job" "migrate" {
  name                = "${var.service_name}-migrate"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.runtime.email
      max_retries     = 0
      timeout         = "300s"

      containers {
        # Placeholder; CI sets the same image it is about to deploy (see lifecycle).
        image   = "us-docker.pkg.dev/cloudrun/container/hello"
        command = ["alembic"]
        args    = ["upgrade", "head"]

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "ENV"
          value = "prod"
        }
        env {
          name = "DATABASE_URL" # direct (non-pooled) endpoint for DDL
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.db["database-url-direct"].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.apis, google_secret_manager_secret_iam_member.runtime_db]
}
