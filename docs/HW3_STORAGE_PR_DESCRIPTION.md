## Summary

Connect scheduled-issue summaries to Team 3's imported Dropbox implementation,
verify exact UTF-8 readback before success, and preserve write certainty during
workflow cleanup. Local real-provider composition and cleanup passed.

Related: #52, #53, #54, #56, #57.

**Base:** `hw3/member1-workflow`, while #53 remains unmerged.

## Why

The workflow must consume another team's implementation as a package dependency.
This replaces the earlier HTTP storage path and uses the authorized Team 5
Dropbox account. The alternative Team 1 package swap remains unverified.

## What changed

- Pin Team 3 implementation/internal interface at `fde60d4` and the shared
  contract at Git tag `0.3.1`; retain reproducible `uv sync --frozen` installation.
- Construct a scoped SDK with explicit credentials, no implicit dotenv loading
  and disabled SDK retries; inject it into Team 3's implementation.
- Wire the normal summary dependency to package operations and compare exact
  downloaded bytes before returning success.
- Fail local storage configuration before writes; distinguish typed pre-send
  failures from uncertain creation and post-upload readback failures.
- Keep known leftover paths separate from provider IDs; sanitize errors and
  compensate only after definite failure.
- Convert the opt-in probe to package operations, preserve historical evidence,
  and document OAuth, cleanup, live evidence and remaining integration work.
- Integrate merged Trello/Calendar package changes; adapt the workflow fake to
  issue contract 1.1.0 and make the OAuth permission test portable on Windows.

- [x] Added or updated functionality
- [x] Fixed a bug
- [x] Refactored existing code
- [x] Updated documentation/tests

## How I tested this

- [x] Current suite after HTTP cleanup: **892 passed, 58 opt-in tests skipped**.
  Removed 70 obsolete HTTP-only cases and added 14 provider-independent path cases;
  package/workflow/probe regression coverage remains.
- [x] Added/updated package construction, workflow failure and probe tests.
- [x] Manually verified real providers using the local FastAPI route.

```text
uv sync --frozen --reinstall-package team5-calendar
Ruff lint and format check: passed
Strict mypy: passed
Package probe: create/readback, conflict, byte preservation, cleanup passed
Local composed request: 201
Provider readback: issue, Calendar event and summary passed
Cleanup: summary, event and issue confirmed absent
```

The existing Starlette TestClient deprecation warning remains. The package-probe
script also passed its explicit-package-bases mypy check after cleanup.
Local checks/evidence are not deployed verification or remote CI.
No independent human provider inspection or live fault injection is claimed.

## Screenshots / output (if applicable)

- `docs/evidence/HW3_STORAGE_TEAM3_PACKAGE_20261116-211419.json`
- `docs/evidence/HW3_WORKFLOW_LOCAL_5ef8b3616f30459a83bfc0f94463e0e3.json`
- `docs/evidence/HW3_WORKFLOW_LOCAL_5ef8b3616f30459a83bfc0f94463e0e3_READBACK_CLEANUP.json`
- `docs/HW3_STORAGE.md`, `docs/WORKFLOW.md`, `docs/HW3_STORAGE_REVIEW_HANDOFF.md`

## Checklist

- [ ] Final diff/CI rechecked after publishing local commits and reconciling #53
- [x] Code builds and runs locally
- [x] No debug code or credentials added by the storage implementation
- [x] Docs/README updated for package setup and evidence

## Notes for reviewers

Student owner: Kristie Lee (Member 4).

AI assistance: Codex; the student owner remains responsible for review and understanding.

Review focus: package boundary and credential lifecycle, typed pre-send evidence,
conservative uncertainty/readback handling, known paths and scratch cleanup.

Remaining work / next owner:

- HTTP storage cleanup is implemented locally: shared path validation moved to
  `storage_paths.py`; legacy adapter/settings/tests removed; historical evidence retained.
- Kristie / Team 1: obtain a compatible supported package, implement provider
  selection and demonstrate the configuration-only swap.
- Kristie / authorized Team 5 teammate: independent contents/cleanup inspection.
- Niriti: structural validation and issue-configuration errors still need
  `step`/`leftovers`; reconcile #53's upstream relationship and deployment setup.
- Integration owners: configure hosted credentials and run deployed success,
  cleanup and required controlled-failure checks; local success is not deployment.
- Ka Pui: update #56's storage architecture, credentials, open questions and
  verification status, then complete internal/outside-team design reviews.
- After #53 integration, inspect the diff and retarget to `hw3/milestone-1`.

This PR does not resolve all #53 error envelopes or complete the storage swap.
