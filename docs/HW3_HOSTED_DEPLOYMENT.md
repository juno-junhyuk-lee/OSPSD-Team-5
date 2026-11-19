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

## 0. Repository owner: allow the branch and update CI access

1. In GitHub, Settings > Environments > `calendar-demo` > Deployment branches,
   add `hw3/milestone-1`.
2. Apply `infra/ci` for the environment. It adds `refs/heads/hw3/milestone-1` to
   the Workload Identity trusted refs (otherwise the Google login fails) and
   grants the deployer `roles/secretmanager.viewer` on the five workflow
   secrets, so the CI Terraform plan can read their metadata (otherwise 403).
   CI gets no access to those secret values. Apply this after step 1 below has
   created the secrets, or the IAM bindings fail on missing secrets.

### After the move to the `OSPSD-Team-5` organization

On 2026-11-19 the repository moved from `juno-junhyuk-lee/OSPSD-Team-5` to
`OSPSD-Team-5/OSPSD-Team-5`. The Deploy job guard and the `infra/ci` default now
name the new repository, but the existing Workload Identity provider still
trusts the old owner, so Google login fails until a project administrator
re-applies `infra/ci` for `demo`. Use the same commands as
[DEPLOYMENT.md](DEPLOYMENT.md) (Bootstrap CI) with:

```sh
export TF_VAR_github_repository_id=1372508104 # unchanged by the move
export TF_VAR_github_owner_id=358853205       # was 66204402 (personal account)
```

The plan should update only the WIF provider attribute condition and the
deployer `workloadIdentityUser` member. The OIDC subject becomes
`repo:OSPSD-Team-5@358853205/OSPSD-Team-5@1372508104:environment:calendar-demo`.

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

### Hosted evidence (2026-11-19)

Service: `https://team5-calendar-demo-dnuukwp5ga-uc.a.run.app`
(`POST /workflows/scheduled-issues`), environment `demo`. Foundations, secrets
and the first Team 3 run were done by Juno; the runs below were done by Niriti
with Claude Code assistance, using the same pinned secret versions as the
service. Each record's inspection reads Trello, Google Calendar and Dropbox
directly with the operator's credentials (not through our endpoint); the
Dropbox read uses the storage package selected for that run.

| Run | Commit / image | Deploy run | Result | Record | Cleanup |
| --- | --- | --- | --- | --- | --- |
| Team 3 (Juno) | `f201764` / `sha256:3d536559…` | [44583149056](https://github.com/OSPSD-Team-5/OSPSD-Team-5/actions/runs/44583149056) | `201`; card, event, summary present with matching SHA-256 | [record](evidence/HW3_HOSTED_WORKFLOW_team3_20261119-130334.json) | [all absent](evidence/HW3_HOSTED_WORKFLOW_team3_20261119-130334_CLEANUP.json) |
| Team 1 | `e44a105` / `sha256:d8ca8a72…` | [44602278015](https://github.com/OSPSD-Team-5/OSPSD-Team-5/actions/runs/44602278015) | `201`; card, event, summary present with matching SHA-256 | [record](evidence/HW3_HOSTED_WORKFLOW_team1_20261119-115503.json) | [all absent](evidence/HW3_HOSTED_WORKFLOW_team1_20261119-115503_CLEANUP.json) |
| Team 3 (same image) | `e44a105` / `sha256:d8ca8a72…` | [44603372843](https://github.com/OSPSD-Team-5/OSPSD-Team-5/actions/runs/44603372843) | `201`; card, event, summary present with matching SHA-256 | [record](evidence/HW3_HOSTED_WORKFLOW_team3_20261119-115812.json) | [all absent](evidence/HW3_HOSTED_WORKFLOW_team3_20261119-115812_CLEANUP.json) |
| Controlled storage failure (Team 3) | `e44a105` / `sha256:d8ca8a72…` | [44603958321](https://github.com/OSPSD-Team-5/OSPSD-Team-5/actions/runs/44603958321) | `502`, `code: provider_error`, `step: summary`, `leftovers: []`; inspection found no card, event or summary | [record](evidence/HW3_HOSTED_STORAGE_FAILURE_20261119-120143.json) | [all absent](evidence/HW3_HOSTED_STORAGE_FAILURE_20261119-120143_CLEANUP.json) |

**Configuration-only swap.** Deploy 44603372843 changed only the
`STORAGE_IMPLEMENTATION` environment variable and reused the pushed image.
`gcloud run revisions describe` on `team5-calendar-demo-00010-ccc` (Team 1)
and `team5-calendar-demo-00011-jdz` (Team 3) shows the same image digest
`sha256:d8ca8a721d3b9f3cfa92bc10de8fb8301ecde1f7945ee5efc567533ad89944fc`
and exactly one environment difference:
`STORAGE_IMPLEMENTATION team1_dropbox -> team3_dropbox`. Juno's Team 3 run
used the earlier `f201764` image; PR #61 (repository move fix) created
`e44a105`, so both swap runs were repeated on that one image.

**Controlled failure.** Followed section 6 on `demo`: uploaded the file
`/ospsd-team5-hw3-failure-target`, deployed with that `STORAGE_ROOT_PATH`
(revision `00012-jmw`), ran with `--expect storage_failure`, then restored
`STORAGE_ROOT_PATH=/ospsd-team5-hw3` (Deploy
[44604506844](https://github.com/OSPSD-Team-5/OSPSD-Team-5/actions/runs/44604506844),
revision `00013-5jf`, same image) and deleted the target file. The
app folder afterwards holds only the empty `ospsd-team5-hw3` folder. The
package classified the path conflict as a definite failure, so the workflow
deleted the event and then the issue before answering.

**Discarded attempt.** `HW3_HOSTED_WORKFLOW_team1_20261119-115349.json` is kept
for completeness but is not evidence of Dropbox inspection: Git Bash rewrote the
operator's `STORAGE_ROOT_PATH` into a Windows path, so its pre-cleanup summary
check looked in the wrong place (`present: false`). The service itself returned
`201`. Its cleanup ran with the corrected root, found the summary with a
matching hash, deleted all three resources and confirmed absence. The Team 1
run above was repeated with the fix. Operators on Windows Git Bash should set
`MSYS2_ENV_CONV_EXCL='*'` before running the helper.

Not done: nobody viewed these records in the Trello, Google Calendar or Dropbox
web pages; checks are API reads by the helper.

Current state: `STORAGE_IMPLEMENTATION=team3_dropbox`,
`STORAGE_ROOT_PATH=/ospsd-team5-hw3`, revision `team5-calendar-demo-00013-5jf`.
