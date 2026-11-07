# Deploy Team 5 Calendar to Cloud Run

Use the billing-enabled `ospsd-team5` project. Juno owns the deployment and
billing checks. Target teardown is February 28, 2027. The service scales to zero
when idle. Monitor billing and registry storage to stay within free allowances.

Install Docker with Buildx, Terraform 1.13.x, Google Cloud CLI, uv, jq, and OpenSSL.
Use a deployer that can manage the resources in `infra/`, act as the runtime
service account, and push images. For independent verification, use a fresh
checkout and select the `verify` environment in Step 2.

Steps 1–6 cover manual Level 1 deployment. For automated deployment and recovery,
see [Level 2](#level-2-automated-deployment-and-recovery).

## 1. Bootstrap once per project

Run from the repository root. Skip the login commands if both the CLI and
Application Default Credentials are already configured. Reuse the state bucket
if it already exists.

```sh
export PROJECT_ID=ospsd-team5
export STATE_BUCKET=your-globally-unique-state-bucket

gcloud auth login --update-adc
gcloud auth application-default set-quota-project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iam.googleapis.com storage.googleapis.com \
  --project "$PROJECT_ID"
gcloud auth configure-docker us-central1-docker.pkg.dev

gcloud storage buckets create "gs://$STATE_BUCKET" --project "$PROJECT_ID" \
  --location us-central1 --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update "gs://$STATE_BUCKET" --versioning
```

Grant authorized teammates access to read, update, and lock state. Keep state
and saved plans out of Git and CI artifacts.

## 2. Provision foundations

Start from a clean checkout of the selected commit. Review each saved plan
before applying it.

Set `CALENDAR_ENV=demo` for the main deployment or `CALENDAR_ENV=verify` for
the independent walkthrough. Use the same environment and state prefix through
teardown.

The foundations-only plan below is for a new environment. For an existing
service, always supply its matching release manifest; omitting it plans to
remove the service.

```sh
export TF_VAR_project_id="$PROJECT_ID"
export TF_VAR_environment="${CALENDAR_ENV:?Set CALENDAR_ENV to demo or verify}"

terraform -chdir=infra init \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config="prefix=calendar/${CALENDAR_ENV:?Set CALENDAR_ENV to demo or verify}"
terraform -chdir=infra plan -out=foundation.tfplan
terraform -chdir=infra apply foundation.tfplan
```

## 3. Add secrets and build the image

Authorize the shared test account with both Calendar scopes using
`uv run python scripts/google_calendar_auth.py`. In External / Testing,
refresh tokens expire after seven days. For a fresh grant close to the demo,
move the old `token.json` to a private location before running the script.
Keep the new `token.json` and the demo key private.
For the client JSON prerequisite, see
[shared authentication setup](../README.md#shared-google-calendar-authentication).

```sh
OAUTH_SECRET=$(terraform -chdir=infra output -json secret_ids | jq -r .oauth)
BEARER_SECRET=$(terraform -chdir=infra output -json secret_ids | jq -r .bearer)
export DEMO_KEY_FILE=/absolute/path/outside/the/repo/demo-key

(umask 077 && openssl rand -hex 32 > "$DEMO_KEY_FILE")
gcloud secrets versions add "$OAUTH_SECRET" --project "$PROJECT_ID" --data-file=token.json
gcloud secrets versions add "$BEARER_SECRET" --project "$PROJECT_ID" --data-file="$DEMO_KEY_FILE"

IMAGE=$(terraform -chdir=infra output -raw image_repository)
COMMIT=$(git rev-parse HEAD)
docker buildx build --platform linux/amd64 --provenance=false \
  --label "org.opencontainers.image.revision=$COMMIT" --load -t "$IMAGE:$COMMIT" .
docker push "$IMAGE:$COMMIT"
```

## 4. Deploy by digest

Use the digest printed by Docker and the version numbers printed by Secret
Manager. Keep the release manifest for later plans. Terraform tracks these
references separately from secret values.

```sh
DIGEST=sha256:paste-the-pushed-digest
OAUTH_VERSION=1
BEARER_VERSION=1
RELEASE_DIR=$(mktemp -d)
export RELEASE_VARS="$RELEASE_DIR/release.tfvars.json"

jq -n --arg commit "$COMMIT" --arg digest "$DIGEST" \
  --argjson oauth "$OAUTH_VERSION" --argjson bearer "$BEARER_VERSION" \
  '{release:{commit:$commit,digest:$digest,oauth_version:$oauth,bearer_version:$bearer}}' \
  > "$RELEASE_VARS"
terraform -chdir=infra plan -var-file="$RELEASE_VARS" -out=service.tfplan
terraform -chdir=infra apply service.tfplan
terraform -chdir=infra plan -var-file="$RELEASE_VARS" -detailed-exitcode
```

The final plan must show no changes and exit 0. Omitting the release manifest
plans to remove the service. For credential rotation, upload a new secret
version and apply with the updated manifest. Keep the active and last known-good
image digests and usable secret versions for rollback.

## 5. Verify and hand off

```sh
URL=$(terraform -chdir=infra output -raw service_url)
curl -fsS "$URL/health"
curl -fsS -o /dev/null -w '%{http_code}\n' "$URL/ready"
curl -sS -o /dev/null -w '%{http_code}\n' "$URL/calendars/primary"
CALENDAR_VERIFY_URL="$URL" CALENDAR_VERIFY_BEARER_FILE="$DEMO_KEY_FILE" \
  uv run python -m scripts.verify_put_live
```

Expect 200, 204, and 401, respectively. Readiness checks startup configuration.
The live workflow checks Google access and test-event cleanup. If POST has an
uncertain outcome, search the test Calendar by the printed run marker before
retrying. See the [shared verification guide](SHARED_CONTRACT_VERIFICATION.md)
for the separate conformance checks.

Have a teammate repeat setup, check a fresh instance, verify the no-change plan,
and tear down the disposable deployment. Record the commit, digest, sanitized
results, and any gaps in the instructions. Give Kristie the release manifest and
results for Level 2.

## 6. Tear down

If CI identity has been attached, remove its verify-only bootstrap resources
first as described in [the pipeline teardown](#7-handoff-and-teardown).

Clean up tagged events, then review the destroy plan for the intended state
prefix. For the independent walkthrough, confirm the backend prefix is
`calendar/verify` and every resource to be removed belongs to
`team5-calendar-verify`. Stop if the plan includes demo resources.

```sh
terraform -chdir=infra plan -destroy -var-file="$RELEASE_VARS" -out=destroy.tfplan
terraform -chdir=infra apply destroy.tfplan
```

Verify the service, registry, and secrets are gone. Keep the shared state bucket
until all environments are gone, then remove its object versions and the bucket.
Check for remaining charges. Retire only the OAuth grant dedicated to this
deployment and coordinate with anyone who shares it.

## Level 2: automated deployment and recovery

Owner: Kristie Lee. **Implementation/local checks complete; actual OIDC
permissions, Actions deployment, failed-release detection, and recovery remain
unverified.** Earlier manual Level 1 verification does not establish these results.
Keep execution evidence and review/handoff follow-ups in the PR.
Use only the disposable `verify` environment for the failure/recovery exercise.

### What runs

Checks covers lint, formatting, typing, offline/conformance tests, and both
Terraform roots. PR checks have no deployment credentials or live Google calls.
Deploy reuses these checks, deploys one immutable image, and requires real-provider
smoke and cleanup before publishing a verified release artifact.

Pushes to `hw2/milestone-3-level-2` target `verify`; `hw2/milestone-3` and `main`
target `demo`. Normal deployment requires `CALENDAR_DEPLOY_ENABLED=true`.
Manual rollback remains available when disabled. Deployment and rollback share
an environment concurrency group and Terraform state locking.

### 1. Prepare an existing Level 1 environment

Use Terraform **1.13.5** and the [manual deployment steps](#1-bootstrap-once-per-project) to
create a working `verify` service, registry, runtime account, OAuth secret, and
bearer secret. Do not run the foundations-only
plan against an existing service without its release manifest: `release=null`
would plan service deletion.

The manual seed deployment is required because CI can update an existing
service, not provision or administer its foundations. Keep the working image
and both usable secret versions. OAuth client preparation is described in
[README authentication](../README.md#shared-google-calendar-authentication).
No interactive Google login takes place in Actions.

The following shell examples require Bash, gcloud, Terraform, jq, and GitHub CLI
(`gh`) authenticated to this repository. They are not PowerShell syntax; use a
configured Bash shell or Cloud Shell, and verify Terraform's version first.

### 2. Bootstrap deployment identity as an administrator

Run from the repository root with project IAM/bootstrap privileges. This root
is separate from service state; the resulting CI identity cannot modify its
own WIF or IAM configuration. Obtain numeric GitHub IDs through an authenticated
API call rather than substituting repository names.

```sh
export PROJECT_ID=ospsd-team5
export STATE_BUCKET=ospsd-team5-terraform-state
export CALENDAR_ENV=verify
export REPOSITORY=juno-junhyuk-lee/OSPSD-Team-5
export TF_VAR_project_id="$PROJECT_ID"
export TF_VAR_state_bucket="$STATE_BUCKET"
export TF_VAR_environment="$CALENDAR_ENV"
export TF_VAR_github_repository_id=$(gh api "repos/$REPOSITORY" --jq '.id')
export TF_VAR_github_owner_id=$(gh api "repos/$REPOSITORY" --jq '.owner.id')

gcloud auth login --update-adc
terraform -chdir=infra/ci init -reconfigure \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config="prefix=calendar/ci/$CALENDAR_ENV"
terraform -chdir=infra/ci plan -out=ci-bootstrap.tfplan
terraform -chdir=infra/ci show ci-bootstrap.tfplan
```

Review that the plan creates only the selected environment's CI identity,
WIF trust, scoped IAM bindings, and required federation APIs. It must not
replace the service or change another environment's resources.

```sh
terraform -chdir=infra/ci apply ci-bootstrap.tfplan
terraform -chdir=infra/ci output -json github_environment_variables
```

The subject uses GitHub's immutable owner/repository ID format for this repository.
Terraform operation polling uses a project-level custom role granting only
`run.operations.get`; service update permissions remain scoped to the service.
WIF restricts access to the trusted repository, owner, environment, branches,
and push/manual events. No service-account JSON key is required. Bootstrap
`demo` separately before enabling its deployment branches.

### 3. Configure GitHub

The repository owner/admin configures **Settings → Environments**. Start with
`calendar-verify`; configure `calendar-demo` separately before enabling its
push targets. If you cannot access these settings, ask the repository owner.

Restrict deployment branches to the exact trusted branch names used above;
do not allow tags. If adding required reviewers, ensure someone is available
for both deployments and emergency rollback.

Add these **Environment variables**, using the administrator's Terraform output:

| Variable | Value |
| --- | --- |
| `GCP_PROJECT_ID` | `ospsd-team5` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Full provider name from Terraform output |
| `GCP_DEPLOYER_SERVICE_ACCOUNT` | Environment-specific deployer email from output |
| `TF_STATE_BUCKET` | Existing shared state bucket name |
| `CALENDAR_ENV` | `verify` or `demo`, matching the Environment name |
| `OAUTH_SECRET_VERSION` | Explicit positive version number; not `latest` |
| `BEARER_SECRET_VERSION` | Explicit positive version number; not `latest` |

Keep OAuth and bearer **values** in Secret Manager. The variables above contain
references only. Add `CALENDAR_DEPLOY_ENABLED=false` as a **repository Actions
variable**, not an Environment variable: the job condition reads it before the
environment is entered. Set it to `true` only when ready for normal deployments.
Before enabling it, consider all three push branches; integration/main pushes
target `demo`, so keep those pushes coordinated until demo setup is ready.

Manual `workflow_dispatch` requires `deploy.yml` on the **default branch**,
even when running another branch. See [GitHub's requirements](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

### 4. Deploy a working release

Use a clean committed revision, enable deployment, and push the trusted Level 2
branch, or run **Actions → Deploy → Run workflow**, selecting `verify` and
leaving `rollback_run_id` empty. Git operations remain the contributor's task.

The checked Terraform plan permits only an update/no-op of the existing
service. The workflow checks the ready revision and traffic, then runs
`scripts.verify_put_live`: readiness, POST/GET/PUT/GET, independent Google
read-back and description preservation, DELETE, and missing/repeated-delete checks.
Temporary secret files and plans are removed after the job.

Success produces:

- `verified-release-<env>-<workflow SHA>-<attempt>` containing
  `verified-release.json`: application commit/digest, configuration commit,
  pinned secret versions, ready revision, environment, and source-run identity.
- `smoke-results-<env>-<workflow SHA>-<attempt>` containing sanitized JSONL,
  including the run marker and cleanup checks.

Record the successful **Deploy run ID**, links, and artifacts before proceeding.
Artifacts have 14-day retention; rollback also requires the image and secret
versions to remain usable. A successful Checks run with `deploy` skipped is
not deployment or real-provider evidence.

### 5. Detect a faulty release in verify only

Scope: one `team5-calendar-verify` release and one smoke-created event. Keep demo
and other teams' services untouched. First confirm step 4 passed and its working
source run is retained. Stop if the target/project is wrong, cleanup cannot be
confirmed, or an uncertain write has not been inspected.

For a temporary test change, add `import os` to `app/main.py` and the following
at the start of `replace_event`, after its docstring:

```python
if os.environ.get("K_SERVICE") == "team5-calendar-verify":
    raise RuntimeError("Controlled verify-only PUT failure")
```

This deliberately breaks PUT only in the disposable hosted service, before its
provider write. It is an exercise patch, not a permanent fault-injection API.
Run formatting/lint/tests, commit and push on the trusted Level 2 branch, and
observe the pipeline. The expected result is successful image deployment but
failed PUT smoke, successful event cleanup, failed Deploy status, and **no new
verified-release artifact**. Save the failure run and sanitized results.

Do not call a PR-check failure proof of post-deployment detection. If checks
stop before deployment, fix the exercise setup rather than bypassing CI.

### 6. Restore and verify

Set `CALENDAR_DEPLOY_ENABLED=false` to stop further automatic deployments.
Manual recovery remains available. Run **Deploy → Run workflow** from a trusted
branch containing the recovery workflow, select `verify`, and enter the working
step-4 **Deploy run ID** in `rollback_run_id`.

Recovery validates the source run/artifact, restores its Terraform configuration,
image digest, and secret versions without rebuilding, and runs the same plan,
revision, smoke, and cleanup checks. The restored content may have a new Cloud
Run revision name.

For a no-change check, use a clean checkout of the restored **configuration
commit** and the downloaded recovery manifest:

```sh
# Set this to the downloaded manifest; run in the clean configuration checkout.
export VERIFIED_MANIFEST=/absolute/path/to/verified-release.json
export TF_VAR_project_id="$PROJECT_ID"
export TF_VAR_environment=verify
umask 077
export RELEASE_VARS=$(mktemp)
jq '{release}' "$VERIFIED_MANIFEST" > "$RELEASE_VARS"
terraform -chdir=infra init -reconfigure \
  -backend-config="bucket=$STATE_BUCKET" -backend-config="prefix=calendar/verify"
terraform -chdir=infra plan -var-file="$RELEASE_VARS" -detailed-exitcode
```

Use a private path for `RELEASE_VARS`. Exit 0/no changes confirms consistency;
exit 2 means differences remain. Never omit the release inputs.

Rollback restores application/configuration references, **not Calendar writes**,
revoked grants, deleted images, or disabled secret versions. If POST lost its
response, inspect the test calendar by the logged run marker before retrying.
The smoke does not retry POST/PUT; known-ID cleanup is attempted in `finally`.
For unconfirmed cleanup, inspect and remove only that run's test event. A failed
rollback must not be reported as recovery.

Remove the exercise patch before any later normal release. Keep automatic
deployment disabled until the branch is repaired and the next target is agreed.

### 7. Handoff and teardown

Keep working/failure/recovery run links, teammate review, and handoff follow-ups
in the PR. Pipeline smoke does not replace full deployed shared conformance.

After the entire verify exercise, an administrator first plans/destroys the
`infra/ci` state at `calendar/ci/verify` to remove its CI bindings and identity,
then follows [Level 1 teardown](#6-tear-down) using the restored
configuration and matching release manifest for `calendar/verify`. Review each
plan for verify-only resources. Shared project APIs remain enabled by design;
keep the state bucket, demo resources, and any OAuth grant shared with demo.
