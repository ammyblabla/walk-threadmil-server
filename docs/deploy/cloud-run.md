# Deploying to Google Cloud Run

This is a one-time setup. After it's done, **every push to `main` deploys automatically**.

```
git push ─► GitHub Actions ─┬► test       (ruff + pytest)
                            └► terraform  (fmt -check + validate, no GCP credentials)
                                   │ both pass, on main
                                   ▼
                              deploy: build image ─► Artifact Registry ─► alembic upgrade (on runner) ─► Cloud Run ─► smoke test
```

Terraform **is not applied by CI**. CI only checks that the `.tf` files are formatted and valid. Run `terraform apply` from your machine (Step 3) whenever you change `infra/`.

| Thing | Value |
|---|---|
| GCP project | `walk-treadmil` (number 101388019037) |
| Region | `asia-southeast1` (Singapore) |
| Cloud Run service | `walk-api` |
| Image repo | `asia-southeast1-docker.pkg.dev/walk-treadmil/walk/api` |
| Terraform state | `gs://walk-treadmil-tfstate` (prefix `server`) |
| Migrations | `alembic upgrade head`, run by GitHub Actions against Neon's direct endpoint |
| Database | Neon project `walk-treadmil` (`soft-wildflower-47108969`), `aws-ap-southeast-1`, Postgres 18, database and role `walk` |
| Auth | Firebase Auth in project `walk-treadmil` (Google sign-in) |

## Who owns what

- **Terraform** (`infra/terraform/`) creates and manages:
  - the Cloud Run service and its settings
  - the image repository in Artifact Registry
  - the service accounts
  - the keyless GitHub-to-GCP login (Workload Identity Federation)
  - the budget alert
  - the Secret Manager *containers* for the database URLs, and who may read them
- **GitHub Actions** only builds and deploys new **images**. Terraform ignores the image field, so the two never fight over it.

## Prerequisites (already done on this Mac)

```bash
brew install uv hashicorp/tap/terraform
brew install --cask google-cloud-sdk
gcloud auth login
```

Billing must be linked to the project:

```bash
gcloud billing projects describe walk-treadmil   # billingEnabled: true
```

## Step 1: Let Terraform use your Google login

Use either option:

```bash
# Option A (recommended): Application Default Credentials (opens a browser once)
gcloud auth application-default login
gcloud auth application-default set-quota-project walk-treadmil

# Option B: reuse your gcloud login for this shell only
export GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token)"   # valid ~1 hour
```

## Step 2: Bootstrap the project (once)

Terraform needs the Cloud Resource Manager API to read the project and set IAM before it can enable any other API, so enable that one by hand:

```bash
gcloud services enable cloudresourcemanager.googleapis.com --project=walk-treadmil
```

Then create the Terraform state bucket:

```bash
gcloud storage buckets create gs://walk-treadmil-tfstate \
  --project=walk-treadmil --location=asia-southeast1 \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://walk-treadmil-tfstate --versioning   # undo for bad applies
```

## Step 3: Apply Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars    # already filled for walk-treadmil; gitignored
terraform init -backend-config="bucket=walk-treadmil-tfstate"
terraform plan                                   # review: ~19 resources to add
terraform apply
```

The first apply deploys Google's **hello** placeholder image. The real API arrives with the first GitHub deploy in Step 5.

If `apply` fails with *"API … has not been used / is disabled"*, wait a minute for the API enablement to propagate, then run `terraform apply` again.

## Step 4: Give GitHub the deploy settings

```bash
terraform output github_variables
```

In GitHub, go to **ammyblabla/walk-threadmil-server → Settings → Secrets and variables → Actions → Variables tab → New repository variable**. Add each key and value from that output:

| Variable | Example value |
|---|---|
| `GCP_PROJECT_ID` | `walk-treadmil` |
| `GCP_REGION` | `asia-southeast1` |
| `SERVICE_NAME` | `walk-api` |
| `IMAGE_REPO` | `asia-southeast1-docker.pkg.dev/walk-treadmil/walk` |
| `WIF_PROVIDER` | `projects/101388019037/locations/global/workloadIdentityPools/github/providers/github-oidc` |
| `DEPLOYER_SA` | `github-deployer@walk-treadmil.iam.gserviceaccount.com` |

These are **variables, not secrets**. None of them are credentials: GitHub proves who it is to Google with a short-lived OIDC token, and no JSON key is stored anywhere.

With the GitHub CLI, this does the same thing:

```bash
terraform output -json github_variables | jq -r 'to_entries[] | "\(.key) \(.value)"' |
  while read k v; do gh variable set "$k" --body "$v" --repo ammyblabla/walk-threadmil-server; done
```

## Step 4b: Database (Neon) connection strings (once, or when the password rotates)

Terraform creates the secrets `database-url` and `database-url-direct`, but **not their values**, so passwords never land in Terraform state. Add or rotate the values with the Neon CLI (`neon login` first):

```bash
P=soft-wildflower-47108969
to_sqla() { sed -E 's#^postgres(ql)?://#postgresql+psycopg://#'; }

# API: pooled endpoint (-pooler host)
neon connection-string main --project-id $P --database-name walk --role-name walk --pooled | to_sqla |
  tr -d '\n' | gcloud secrets versions add database-url --project walk-treadmil --data-file=-

# Migrations: direct endpoint (DDL should not go through PgBouncer)
neon connection-string main --project-id $P --database-name walk --role-name walk | to_sqla |
  tr -d '\n' | gcloud secrets versions add database-url-direct --project walk-treadmil --data-file=-
```

Cloud Run reads `version = "latest"` when a revision starts, so **redeploy** (re-run the workflow) after rotating.

On a brand-new project the order matters: a revision that references a secret with **no versions** fails to start. So:
1. `terraform apply -target=google_secret_manager_secret.db -target=google_secret_manager_secret_iam_member.runtime_db`
2. Add the values (above).
3. `terraform apply`.

### Migrations

Every deploy runs `alembic upgrade head` **on the GitHub runner, before** traffic switches. It uses `database-url-direct`, masked in the logs, and the output is in the Actions log. If a migration fails, the deploy stops and the old revision keeps serving.

Only two identities can read `database-url-direct`: the runtime account and `github-deployer`. The deployer is reachable only from `main` of this repo, through Workload Identity Federation.

To run it by hand from your Mac:

```bash
DATABASE_URL="$(gcloud secrets versions access latest --secret database-url-direct --project walk-treadmil)" \
  uv run alembic upgrade head
```

> **Why not a Cloud Run job?** We tried one first (`walk-api-migrate`, 2026-11-10). In `asia-southeast1`, every job execution, including Google's own sample image, failed with *"exit code 0, Unknown error"* and no logs, while the same job ran fine in `us-central1`. This started right after billing was briefly unlinked. Running on the runner avoids that dependency and gives readable logs.

Write migrations to be **backward-compatible** (expand first, contract in a later deploy), because the old revision runs against the new schema for a moment.

## Step 5: Deploy

Push to `main`, or open **Actions → ci → Run workflow**. Then check:

```bash
URL=$(terraform -chdir=infra/terraform output -raw service_url)
curl "$URL/health"          # {"status":"ok","env":"prod","version":"<commit sha>"}
curl "$URL/api/v1/home"
curl -i "$URL/api/v1/me/profile"   # 401 without a Firebase ID token (503 would mean no DATABASE_URL)
open "$URL/docs"
```

## Security notes

- Only pushes to **`main` of `ammyblabla/walk-threadmil-server`** can get a deploy token. This is enforced by the identity provider's `attribute_condition`.
- **The deployer** can only deploy to Cloud Run, push images to the `walk` repo, and run revisions as the runtime service account.
- **The runtime service account** has **no** project roles. It has `secretAccessor` only on `database-url` and `database-url-direct`. Grant new secrets (e.g. a Garmin token key) one at a time.
- **The service is public** (`allUsers` invoker). Every data endpoint requires a valid **Firebase ID token** for project `walk-treadmil`. The app refuses `AUTH_MODE=dev` when `ENV=prod`.
- **Database passwords** live only in Secret Manager and Neon. They aren't in Terraform state, GitHub, or the image.

## Cost

| Item | Free allowance | Our usage |
|---|---|---|
| Cloud Run (request-based) | 2M requests, 180k vCPU-s, 360k GiB-s each month | Tiny. It scales to zero when idle |
| Artifact Registry | 0.5 GB storage | About 5 images × ~80 MB compressed. A cleanup policy keeps the newest 5 |
| Cloud Build | not used | Images are built on GitHub's runners |
| Secret Manager | 6 active versions, 10k accesses each month | 2 secrets, read once per instance start |
| Neon (free plan) | 0.5 GB storage, scale-to-zero compute | A few MB. The first query after idle takes about 0.5 s while compute wakes |

A **budget alert of 50 THB a month** emails the billing admins at 50%, 90% and 100%. It only **alerts** and does not stop charges. Change it with `budget_amount` in `terraform.tfvars`.

Expect a **cold start of about 1 to 3 seconds** after the service has been idle. Setting `min_instance_count = 1` removes it, but costs money.

## Tear down

```bash
cd infra/terraform && terraform destroy
gcloud storage rm -r gs://walk-treadmil-tfstate     # optional: the state bucket
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Google-branded **404** on `/healthz` | Cloud Run reserves some paths ending in `z` on `*.run.app`. Use `/health` (already the case) |
| Deploy job is **skipped** | The repo variables (Step 4) aren't set yet |
| `auth` step: *"unauthorized_client … attribute condition"* | You pushed from a branch other than `main`, or the repo was renamed. Update `github_repo` and re-apply |
| `Permission 'iam.serviceAccounts.actAs' denied` | Re-run `terraform apply`. The `deployer_acts_as_runtime` binding is missing |
| Budget resource fails: *"requires a quota project"* | `gcloud auth application-default set-quota-project walk-treadmil` |
| Everything returns **500/503**, `terraform` says *"absent billing account"* | Billing was unlinked. Choosing Firebase's **Spark** plan does this. Re-link with `gcloud billing projects link walk-treadmil --billing-account 017D4D-232C81-E4897E` (Firebase then shows **Blaze**) |
| Smoke test: `/me/profile` returns **503** | `DATABASE_URL` isn't wired: the secret has no version, or the service was created before it had one. Add the version and redeploy |
| Migration step fails: *password authentication failed* | The Neon password was rotated. Update both secrets (Step 4b) |
| Migration step fails: *Permission denied on secret* | The deployer lost `secretAccessor` on `database-url-direct`. Run `terraform apply` (`deployer_db_direct`) |
| Budget fails with *permission denied* | Your account needs **Billing Account Administrator** (or Costs Manager) on the billing account |
