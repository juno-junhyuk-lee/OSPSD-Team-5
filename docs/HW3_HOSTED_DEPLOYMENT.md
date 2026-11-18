# HW3 hosted workflow deployment

Owner: Niriti, with Claude Code assistance. This change wires the Trello and
Dropbox settings into Cloud Run and adds a hosted run/cleanup helper. It does not
record a deployment or live run yet; evidence is added after the steps below.

## What changed

| Area | Change |
| --- | --- |
| `infra/main.tf` | Five new Secret Manager secrets per environment (`trello-api-key`, `trello-token`, `dropbox-app-key`, `dropbox-app-secret`, `dropbox-refresh-token`), runtime accessor grants, and container env: plain workflow settings plus secret env vars pinned to explicit versions |
| `infra/variables.tf` | Optional `integration` object: `storage_implementation`, `storage_root_path`, `trello_list_id`, `secret_versions`. Null keeps the HW2 container unchanged |
| `scripts/deploy_release.py` | Release manifests carry the integration block; `check-plan` and `check-service` reject unpinned, plain-text or mismatched credentials and wrong settings; rollback restores the recorded block |
| `.github/workflows/deploy.yml` | Reads the settings from GitHub Environment variables, trusts `hw3/milestone-1`, and reuses an already pushed commit image so a configuration-only redeploy keeps the same digest |
| `scripts/verify_workflow_hosted.py` | `run` posts one marked request to the hosted service and inspects all three providers; `cleanup` deletes only that run's resources and confirms absence |

Container settings when `integration` is set:

| Variable | Source |
| --- | --- |
| `ISSUE_TRACKER_IMPLEMENTATION` | fixed `team4_trello` |
| `TRELLO_LIST_ID` | `integration.trello_list_id` |
| `STORAGE_IMPLEMENTATION` | `integration.storage_implementation` (`team3_dropbox` or `team1_dropbox`) |
| `STORAGE_ROOT_PATH` | `integration.storage_root_path` |
| `PYTHON_DOTENV_DISABLED` | fixed `1` (required by the storage package factory) |
| `TRELLO_API_KEY`, `TRELLO_TOKEN`, `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN` | Secret Manager, version from `integration.secret_versions` |

The storage factory accepts `DROPBOX_REFRESH_TOKEN` directly, so no Dropbox token
file is mounted. Secret values never enter Terraform state or the manifest.

## 1. Administrator: apply the new foundations (once per environment)

CI refuses foundation changes, so a deployer with project access applies them.
Supply the current release manifest so the existing service is kept:

```sh
export TF_VAR_project_id=ospsd-team5 TF_VAR_environment=demo
terraform -chdir=infra init -backend-config="bucket=ospsd-team5-terraform-state" \
  -backend-config="prefix=calendar/demo"
terraform -chdir=infra plan -var-file="$RELEASE_VARS" -out=hw3-foundations.tfplan
terraform -chdir=infra apply hw3-foundations.tfplan
```

Expect five secrets and five IAM members to be created and the service to stay
unchanged (no `integration` in the old manifest).

## 2. Add secret versions

Use the Team 5 Trello test account and the Team5-Review Dropbox app
([storage auth](HW3_STORAGE_AUTH.md)). Read values without echoing them, and
never paste them into chat, git or evidence:

```sh
for name in trello-api-key trello-token dropbox-app-key dropbox-app-secret dropbox-refresh-token; do
  read -rs -p "$name: " value; echo
  printf '%s' "$value" | gcloud secrets versions add "team5-calendar-demo-$name" \
    --project ospsd-team5 --data-file=- --format='value(name)'
  unset value
done
```

Note each printed version number.

## 3. GitHub Environment variables (`calendar-demo`)

| Variable | Value |
| --- | --- |
| `STORAGE_IMPLEMENTATION` | `team3_dropbox` for the first run |
| `STORAGE_ROOT_PATH` | `/ospsd-team5-hw3` |
| `TRELLO_LIST_ID` | the 24-character test list ID |
| `TRELLO_API_KEY_SECRET_VERSION`, `TRELLO_TOKEN_SECRET_VERSION`, `DROPBOX_APP_KEY_SECRET_VERSION`, `DROPBOX_APP_SECRET_SECRET_VERSION`, `DROPBOX_REFRESH_TOKEN_SECRET_VERSION` | versions from step 2 |

Setting environment variables needs repository admin. Leaving
`STORAGE_IMPLEMENTATION` empty deploys without the workflow settings.

## 4. Deploy the integrated commit

Merge this branch into `hw3/milestone-1`; the push runs Deploy against `demo`.
The run summary prints the release commit, image digest and
`Storage implementation: team3_dropbox`. The existing Calendar smoke test must
pass before the release is marked verified.

## 5. Team 3 run, then Team 1 run

Configure the operator terminal as in [storage auth](HW3_STORAGE_AUTH.md), with
`TRELLO_*`, the local Google `token.json`, `CALENDAR_VERIFY_URL` (the printed
service URL) and `CALENDAR_VERIFY_BEARER_FILE`. Then:

```powershell
uv run python -m scripts.verify_workflow_hosted run --storage team3_dropbox `
  --expect created --deploy-run-id <run id> `
  --output docs/evidence/HW3_HOSTED_WORKFLOW_team3_<timestamp>.json
```

The record keeps response IDs, a SHA-256 of the returned Markdown, and an
independent pre-cleanup inspection (Trello card by exact title, Calendar event by
marker, Dropbox summary bytes compared by hash). A teammate can inspect the
provider records now. Then:

```powershell
uv run python -m scripts.verify_workflow_hosted cleanup `
  --record docs/evidence/HW3_HOSTED_WORKFLOW_team3_<timestamp>.json `
  --output docs/evidence/HW3_HOSTED_WORKFLOW_team3_<timestamp>_CLEANUP.json
```

Cleanup runs summary, then event, then card, and fails unless all three are absent
afterward.

Swap: change only the `STORAGE_IMPLEMENTATION` variable to `team1_dropbox`, and
rerun Deploy with `workflow_dispatch` on `hw3/milestone-1` (environment `demo`).
The step summary should say `Reusing image ...@<same digest>`. Confirm the new
revision differs only in that variable:

```sh
gcloud run revisions describe <old> --region us-central1 --format=json > old.json
gcloud run revisions describe <new> --region us-central1 --format=json > new.json
diff <(jq -S '.spec.containers[0].env' old.json) <(jq -S '.spec.containers[0].env' new.json)
```

Repeat the run and cleanup with `--storage team1_dropbox`.

## 6. Controlled storage failure

Goal: the summary step fails definitely after the issue and event exist, so the
workflow compensates. Configuration only, no code change:

1. In the Team5-Review app folder, upload a small **file** named
   `ospsd-team5-hw3-failure-target` (a file, not a folder).
2. Set `STORAGE_ROOT_PATH` to `/ospsd-team5-hw3-failure-target` and rerun Deploy.
   Writing `<file>/scheduled-issue-....md` is rejected as a path conflict by both
   storage packages, before any bytes are stored.
3. Run with the failure expectation:

   ```powershell
   uv run python -m scripts.verify_workflow_hosted run --storage <current> `
     --expect storage_failure --deploy-run-id <run id> `
     --output docs/evidence/HW3_HOSTED_STORAGE_FAILURE_<timestamp>.json
   ```

   Expected (confirm from the record, not assumed): status 502,
   `step: "summary"`, `leftovers: []`, and the pre-cleanup inspection shows no
   Trello card and no Calendar event for the marker because the workflow already
   deleted the event and then the issue. If the packages classify the failure as
   uncertain instead, `leftovers` lists issue/event `created` and summary
   `uncertain`, and the inspection shows them; record that outcome as is and run
   `cleanup` on the record.
4. Restore `STORAGE_ROOT_PATH=/ospsd-team5-hw3`, rerun Deploy, and delete the
   failure-target file.

## Verification status

Offline: Python release checks, Terraform plan tests with a mocked provider
(`infra/tests/integration.tftest.hcl`), and helper tests with fake providers.
Foundations, secrets, deployment and live runs are still pending.
