# Member 2 real Google verification

Executed with Codex assistance on November 14, 2026, 15:11:35–15:11:39 EST.
Jim authorized creation and cleanup of disposable test events. This is an
agent-executed check, not independent teammate verification.

## Provenance and scope

- Branch: `hw3/member2-calendar`.
- Tested application commit: `05808ccc7c5753a2d343858d395fb5d4cda1acb3`.
- Shared contract: `v0.1.0-rc.1`, commit
  `1c1cad7a0732ddb242a05400d8833d94e4422424`.
- Python: 3.14.8, frozen dependencies.
- Settings: `CALENDAR_MODE=local`, `CALENDAR_IMPLEMENTATION=google`.
- Account: the existing Team 5 Google test account, primary calendar,
  `America/New_York`; authorization and calendar metadata checked before writes.
- Marker: `hw3-member2-f20c15e55ae3`.
- Transport: FastAPI TestClient in-process HTTP through normal dependencies
  and real Google adapters, plus independent Google SDK reads.
- No application source changes were made during the run. The new evidence
  files were untracked; later documentation commits do not change the tested code.

The existing `scripts.verify_put_live` workflow was used without modifying it.
Its historical event-title prefix is still `HW2 contract verification`; the
unique run marker above identifies this HW3 run. The test used one event and
also verified replacement and preservation of a non-shared description.

## Observed results

| Check | Result |
| --- | --- |
| Installed contract tag/commit | Match |
| Independent Google marker search before writes | 0 active events |
| Health / readiness | 200 / 204 |
| Create | 201; ID, title, start, end match |
| Read after create | 200; same ID and matching fields |
| Seed description directly in Google | Success |
| Replace / read after replacement | 200 / 200; same ID, updated fields match |
| Independent Google read | ID, title, times match; description preserved |
| Delete | 204 |
| Read after delete | 404 |
| Repeat delete | 404, as required by the contract |
| Independent Google marker search after cleanup | 0 active events |

All 14 Boolean checks passed, `failed_steps=[]`, process exit 0.
[Sanitized JSONL evidence](evidence/HW3_CALENDAR_LIVE_2026-11-14.jsonl)
contains timestamps, revision, marker, statuses, and Boolean checks; it contains
no OAuth tokens, authorization headers, event IDs, or unrelated calendar data.
Google may retain cancelled events in Trash; zero active matches does not claim
permanent erasure of provider history.

## Method and reproduction

Use the documented OAuth setup with the agreed test account and keep the local
authorization ignored by Git. The normal command is:

```sh
CALENDAR_MODE=local CALENDAR_IMPLEMENTATION=google \
  uv run python -m scripts.verify_put_live
```

For this run, a one-off Python wrapper called the existing `check_package`,
`verification_client`, `check_readiness`, and `verify_workflow` functions with
the marker above. It additionally queried Google before and in a `finally`
block after the workflow, using `events.list(calendarId="primary", q=run_id,
showDeleted=False, maxResults=2500)`, exhausting `nextPageToken` pages. All
Google requests used `num_retries=0`. It required zero matching active records
before starting and after cleanup, and exited via `Verification.finish()`.
Fresh runs must generate a new unique marker and record their own results.

No create was repeated. Known-ID cleanup was performed by the script's existing
`finally` path. No cleanup failure or uncertain write occurred in this run.

## Limits and remaining work

This establishes the Member 2 Calendar path against real Google. It does not
establish the deployed HTTPS endpoint, service restart behavior, the composed
issue/event/storage workflow, configuration-only storage swapping, or provider
failure behavior. Failure cases are covered separately by controlled tests.
The existing Starlette TestClient deprecation warning was observed.

Teammate review and the final deployed composed-workflow verification remain
pending. No branch push, PR creation, or deployment was performed for this run.
