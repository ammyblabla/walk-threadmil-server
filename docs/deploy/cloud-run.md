# Deploying to Google Cloud Run

This is a one-time setup. After it's done, **every push to `main` deploys automatically**.

```
git push ─► GitHub Actions ─► test (ruff + pytest)
                         └──► deploy: build image ─► Artifact Registry ─► Cloud Run ─► smoke test
```

| Thing | Value |
|---|---|
| GCP project | `walk-treadmil` (number 101388019037) |
| Region | `asia-southeast1` (Singapore) |
| Cloud Run service | `walk-api` |
| Image repo | `asia-southeast1-docker.pkg.dev/walk-treadmil/walk/api` |
| Terraform state | `gs://walk-treadmil-tfstate` (prefix `server`) |

## Who owns what

- **Terraform** (`infra/terraform/`) creates and manages:
  - the Cloud Run service and its settings
  - the image repository in Artifact Registry
  - the service accounts
  - the keyless GitHub-to-GCP login (Workload Identity Federation)
  - the budget alert
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

## Step 2: Create the Terraform state bucket (once)

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

## Step 5: Deploy

Push to `main`, or open **Actions → ci → Run workflow**. Then check:

```bash
URL=$(terraform -chdir=infra/terraform output -raw service_url)
curl "$URL/healthz"          # {"status":"ok","env":"prod","version":"<commit sha>"}
curl "$URL/api/v1/home"
open "$URL/docs"
```

## Security notes

- Only pushes to **`main` of `ammyblabla/walk-threadmil-server`** can get a deploy token. This is enforced by the identity provider's `attribute_condition`.
- **The deployer** can only deploy to Cloud Run, push images to the `walk` repo, and run revisions as the runtime service account.
- **The runtime service account** has **no** project roles. When secrets arrive (Neon URL, Firebase, Garmin key), grant it `secretAccessor` on each secret individually.
- **The service is public** (`allUsers` invoker) because the app will enforce Firebase auth. Until then it only serves mock data.

## Cost

| Item | Free allowance | Our usage |
|---|---|---|
| Cloud Run (request-based) | 2M requests, 180k vCPU-s, 360k GiB-s each month | Tiny. It scales to zero when idle |
| Artifact Registry | 0.5 GB storage | About 5 images × ~80 MB compressed. A cleanup policy keeps the newest 5 |
| Cloud Build | not used | Images are built on GitHub's runners |

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
| Deploy job is **skipped** | The repo variables (Step 4) aren't set yet |
| `auth` step: *"unauthorized_client … attribute condition"* | You pushed from a branch other than `main`, or the repo was renamed. Update `github_repo` and re-apply |
| `Permission 'iam.serviceAccounts.actAs' denied` | Re-run `terraform apply`. The `deployer_acts_as_runtime` binding is missing |
| Budget resource fails: *"requires a quota project"* | `gcloud auth application-default set-quota-project walk-treadmil` |
| Budget fails with *permission denied* | Your account needs **Billing Account Administrator** (or Costs Manager) on the billing account |
