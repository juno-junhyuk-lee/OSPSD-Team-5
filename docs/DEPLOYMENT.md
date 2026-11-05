# Deploy Team 5 Calendar to Cloud Run

Use the billing-enabled `ospsd-team5` project. Juno owns the deployment and
billing checks. Target teardown is February 28, 2027. The service scales to zero
when idle. Monitor billing and registry storage to stay within free allowances.

Install Docker with Buildx, Terraform 1.13.x, Google Cloud CLI, uv, jq, and OpenSSL.
Use a deployer that can manage the resources in `infra/`, act as the runtime
service account, and push images. For independent verification, use a fresh
checkout and select the `verify` environment in Step 2.

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
curl -fsS "$URL/healthz"
curl -fsS -o /dev/null -w '%{http_code}\n' "$URL/readyz"
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
