# Storage package transition plan

Owner: Kristie (Member 4). November 16, 2026. Baseline: `f7c59d1`.
Codex assisted with inspection and this plan. This commit scope is documentation
only. Subsequent dependency, wiring and live storage-probe progress is recorded
below; composed-workflow verification remains pending.

## Dependency installation progress

Task 2 adds `dropbox-client-impl` and `cloud-storage-client-api` as direct project
requirements. Both root `[tool.uv.sources]` entries pin full commit
`fde60d4fb648df6defb918ff815fe940c525adc7` at their respective subdirectories.
The existing shared-contract tag `0.3.1` / commit `664afc9` is unchanged.

Unlike the earlier standalone pip experiment, normal project resolution succeeds
using these root source declarations. Operators do not need `--no-sources`,
manual pip installation or a change to CI's existing frozen-sync command:

```powershell
uv sync --frozen
```

The lockfile adds seven packages without changing existing package versions:
the two Team 3 distributions (`0.1.0`), Dropbox SDK `12.2.5`, python-dotenv `1.2.4`,
stone `3.5.5`, Jinja2 `3.1.6` and MarkupSafe `3.0.4`.

Frozen installation succeeded in both the current application environment and
a new external environment using Python 3.14.8 and the complete application
lockfile. In both environments an offline probe imported Team 5's summary module
and Team 3's implementation together, checked official `DocumentStorage` identity
with an injected placeholder, and confirmed missing credentials raise
`DropboxAuthError`. Distribution provenance matched both full Git pins.
The probe disabled dotenv loading, cleared Dropbox configuration, selected an
absent scratch token file and blocked socket/DNS access. It did not read real
credentials or perform provider operations. This is dependency/import evidence,
not method conformance, actual package workflow wiring or live Dropbox evidence.

Validation after the dependency update: Ruff lint passed, 115 files passed the
format check, strict mypy passed for 73 source files, and the full suite passed
with **903 passed, 58 opt-in tests skipped**. The existing Starlette TestClient
deprecation warning remains. The initial sandboxed pytest run stalled and was
interrupted; a normal-environment rerun completed in 10.20 seconds. No live test
was enabled. `git diff --check` also passed.

## Decision and confirmed inputs

### Task 3: package construction boundary

`app/storage_package.py` now supplies `package_summary_store()`, a scoped factory
for `DocumentSummaryStore` backed by the imported Team 3 implementation. It is
wired to `get_summary_store` by task 4. Dependency construction finishes before
the first workflow write.

Required runtime configuration:

| Variable | Requirement |
| --- | --- |
| `PYTHON_DOTENV_DISABLED` | Exactly `1`, set before provider import; prevents Team 3's implicit dotenv loading |
| `STORAGE_ROOT_PATH` | Valid isolated destination below the app root; `/` and traversal are rejected |
| `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET` | Nonblank app credentials supplied by the operator |
| `DROPBOX_REFRESH_TOKEN` | Nonblank refresh token, or use the token file below |
| `DROPBOX_TOKEN_FILE` | Explicit absolute path to OAuth JSON containing a nonblank string `refresh_token`, when no environment refresh token is supplied |

The environment refresh token takes precedence over the file. There is no
working-directory token-file fallback and no short-lived `DROPBOX_ACCESS_TOKEN`
fallback in this factory. OAuth login remains a separate operator command, not
an API action. No redirect URI is needed for ordinary runtime construction.
The provider CLI's default `.dropbox_token.json` filename is now gitignored as
an additional guard; the recommended token location remains outside the repo.

The factory constructs the official SDK with a 30-second timeout and both SDK
error/rate-limit retry counts set to zero, then injects it into Team 3's
`DropboxClient` and `DropboxDocumentStorage`. This keeps real storage operations
inside Team 3's package while controlling credentials and SDK lifetime locally.
The SDK is closed on context exit and if wrapper construction fails.

Local settings/file/import/construction failures produce a fixed-message
`SummaryStorageError(configured=False, may_have_applied=False, retryable=False)`.
They contain no raw provider error text, token value or local file path. Errors
from operations after the store is yielded are not reclassified as configuration
failures. Token revocation, expiry and granted scopes cannot be established
without provider contact; they are not validated by this offline constructor.
Task 4 maps configuration errors into the workflow's existing public error
shape before issue/event writes. Operation certainty refinement remains task 5.

Offline tests cover invalid settings and token files, precedence, secret-safe
settings representation, real SDK/package construction with network disabled,
disabled retries, sanitized constructor failures, SDK cleanup and preservation
of operation errors. No real credentials or provider operations were used.
Task 3 validation: 21 new offline tests passed; the full suite reported
**924 passed, 58 skipped**, with the existing Starlette TestClient warning.
Ruff lint/format, strict mypy (75 source files) and `git diff --check` passed.

### Task 4: workflow package wiring

`get_summary_store` now enters `package_summary_store()` before yielding the
workflow dependency. Initialization errors map to the existing sanitized
503 response (`step=summary`, `leftovers=[]`, `retryable=false`); operation errors
after entry are not caught by that mapping. The SDK lifetime covers the request.

Controlled HTTP workflow tests use the actual imported Team 3 wrapper and a fake
lower-level provider client. They check UTF-8 upload/readback, opaque ID and path
fallback, conflict compensation, uncertain failure/readback preservation, known
summary paths and SDK closure. HTTP storage transport calls are forbidden by
the test. Missing settings and a failing SDK constructor return 503 before any
issue/event write. These are offline checks, not real Dropbox evidence.

HTTP modules remain temporarily: `storage_path` is imported by the summary and
configuration boundaries, and legacy adapter tests still use HTTP directly.
The opt-in probe is converted to package operations by task 6. Audit/extract
path validation and review remaining callers before removing
those modules in a separate cleanup scope. No HTTP fallback exists in the
current workflow. Task 5's package failure-certainty implementation follows below.
Task 4 validation: 77 focused tests passed; full suite **928 passed, 58 skipped**,
with the existing Starlette TestClient warning. Ruff lint/format, strict mypy
and `git diff --check` passed.

### Task 5: failure certainty and cleanup

Package-specific classification now recognizes typed pre-send connection timeout
and new-connection failure evidence through the pinned Team 3 cause chain.
Generic connection failures remain uncertain. Confirmed upload dominates all
subsequent readback failures. Unexpected package errors or malformed metadata
are sanitized as uncertain failures with the known summary path.

The generic summary boundary uses an explicit list of definite shared rejections;
unknown shared exceptions no longer implicitly mean no write. The workflow's
public response schema, retry policy and orchestration code are unchanged.
See [implemented package classification](HW3_STORAGE_FAILURE_POLICY.md#implemented-package-classification-task-5)
for exact rules and limitations. Ka Pui can review the implementation/tests;
this does not record approval or live fault-injection evidence.
Validation: 13 new SDK-boundary regression cases; full suite **941 passed,
58 skipped**, with the existing Starlette TestClient warning. Ruff lint/format,
strict mypy and `git diff --check` passed. No real credentials/provider calls.

- Hari's help-channel clarification, supplied by Kristie: adding the other
  team's package as a dependency is a hard requirement. The planned implementation
  imports and uses that package for summary operations; merely installing it
  while keeping HTTP storage as the workflow path is not the completion target.
- John approved Team 3 commit
  `fde60d4fb648df6defb918ff815fe940c525adc7` and the explicit dependencies with
  `--no-sources` approach. No release tag contains the wrapper yet. Team 3 tests
  Python 3.12; our isolated Python 3.14 install/import probe is narrower evidence.
- Juno approved reuse of the existing Team5-Review scoped App Folder app.
  Its supplied permissions and callback match the package README. This approval
  does not establish OAuth completion, token validity or access to a particular
  Dropbox account. Confirm the intended account during authorization.
- Package operations use the authorized Team 5 account, not Team 3's endpoint
  or Dropbox folder. Use a dedicated HW3 folder within our app folder. Arrange
  independent inspection with an authorized Team 5 teammate; John need not watch
  Team 3's account for this run. Never put credentials or token contents in git.
- Team 1 has not replied with a supported package solution. This blocks the
  alternative-provider swap, not Team 3 implementation.

## Authorization and probe progress

### Task 6: authorization guide and package probe tooling

The [authorization guide](HW3_STORAGE_AUTH.md) provides Team5-Review app/account
checks, external absolute token-file setup, session environment variables,
operator-only OAuth login and the dedicated app-folder test path. App reuse is
approved; authorization and live storage verification were subsequently reported
by Kristie in task 7 below.

`scripts/verify_storage_live.py` now uses Team 3 package operations through the
same scoped `package_document_storage` SDK factory as the workflow. Its UUID
scratch-file cleanup policy is deliberately separate from production recovery.
It records installed distribution versions/Git provenance, Python, application
HEAD and source/lockfile hashes. It refuses existing output files and still
requires `--execute`; no endpoint URL or HTTP transport is used.

Offline probe tests cover success, preexisting files, conflict, uncertain upload,
readback mismatch, cleanup failures (including untyped failures), health and
construction failures, explicit execution, evidence preservation, provenance and
exit status. CLI tests mock the probe; provider tests use the real Team 3 wrapper
with a fake lower-level client and SDK. No OAuth, account check or real file
operation was executed. Historical HTTP evidence is unchanged.
Validation: 15 probe tests and 21 package-construction tests passed. Full suite:
**948 passed, 58 skipped**, with the existing Starlette TestClient warning.
Ruff lint/format, strict mypy and the probe-specific mypy check using
`--explicit-package-bases` passed; `git diff --check` passed.

## Live verification progress

### Task 7: live storage probe evidence

Kristie ran the package probe at application base `50ad496`, reporting OAuth
success for the intended Team 5 account, the prepared test folder and exit code 0.
[Recorded JSON](evidence/HW3_STORAGE_TEAM3_PACKAGE_20261116-211419.json) shows
health, upload/UTF-8 readback, duplicate conflict, byte preservation and final
absence all passed on November 16, 2026, 21:14:20–21:14:27 America/New_York.
All six source hashes match the checkout; the recorded payload hash, 104-byte
size, path and reference are internally consistent. Package Git pins match the
approved Team 3 revision and existing shared contract. No credential file was
opened or secret values requested during review.

The storage-only probe did not establish composed-workflow execution or direct
inspection. Subsequently Kristie completed a local real-provider workflow at
`e2616dd`, followed by successful issue/Calendar/summary readback and cleanup:
see [workflow evidence](WORKFLOW.md#local-real-provider-workflow-evidence).
The local composition portion of task 7 is now complete. Independent account
inspection/cleanup confirmation, deployed execution and Team 1 swap remain
pending. Preserve both original execution records and their distinct scopes.

## Branch and PR snapshot

Read-only GitHub inspection on November 16:

| PR | Observed state | Consequence |
| --- | --- | --- |
| [#52](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/52) | Merged into `hw3/milestone-1`; merge `df2145d` | Issue package changes must eventually be integrated; do not reimplement them in storage work |
| [#53](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/53) | Open draft; head `hw3/member1-workflow` at `8a92484`; base still `hw3/issue-tracker` | Niriti owns updating its upstream relationship and workflow fixes |
| [#55](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/55) | Open draft; head `hw3/member4-storage` at `f7c59d1`; base `hw3/member1-workflow` | Continue small commits on the existing branch and PR |

No branch switch or immediate rebase is required for this documentation task.
Keep #55's base while #53 remains its unmerged prerequisite. When Niriti updates
the workflow branch, inspect changes before syncing. Once #53 merges, inspect
the merge method and diff before retargeting #55 to `hw3/milestone-1` and deciding
whether a rebase is needed. Kristie executes all branch/rebase/add/commit/push
commands; the assistant supplies commands only when necessary. Local tracking
currently points to `origin/hw3/member1-workflow`; this does not determine #55's
head branch and is not a reason to push to the workflow branch.

## Proposed change boundaries

These are coordination proposals to communicate, not acknowledgements from
Niriti or Ka Pui. Request review of the boundaries before overlapping edits.

| Area | Proposed owner and boundary |
| --- | --- |
| `pyproject.toml`, `uv.lock` | Kristie adds only storage package requirements; coordinate with issue/Calendar dependency owners before concurrent lockfile edits |
| Storage package construction/configuration and tests | Kristie owns provider creation, credential-location handling and sanitized pre-write configuration errors |
| `app/workflow_dependencies.py` | Kristie changes `get_summary_store` and storage imports; Niriti retains issue/Calendar wiring and overall dependency integration |
| `app/summary_storage.py`, storage tests | Kristie retains `SummaryStore` and shared `DocumentStorage` boundary, UTF-8 readback and known-path propagation; implements package-aware failure certainty |
| `app/workflow.py`, `tests/test_workflow.py` | Niriti owns request validation and orchestration; Kristie proposes only storage-related error/cleanup changes and regression tests, coordinating overlapping edits first |
| `app/storage_http.py`, `app/storage_client.py`, `app/storage_settings.py` | Kristie audits references and extracts reusable path validation before removing obsolete HTTP implementation; do not delete unrelated `httpx` dependencies |
| `scripts/verify_storage_live.py`, its tests and evidence | Kristie converts to package-backed checks with explicit execution and cleanup; keeps previous HTTP evidence historical |
| Storage docs, `docs/WORKFLOW.md` storage sections | Kristie updates implementation status, setup and handoff |
| Design, cross-vertical test plan, submission | Ka Pui coordinates; Kristie provides storage facts, blockers and evidence for review |

Preserve the public workflow schema, optional known summary path, no-write-retry
policy and newest-first compensation. Do not silently redesign issue/Calendar
contracts. Constructor/configuration failure must stop before issue/event writes;
uncertain creation or failed readback after creation must not be treated as a
definitely absent summary. See the [failure policy](HW3_STORAGE_FAILURE_POLICY.md).

## Small-commit sequence

1. **This scope: transition documentation and coordination draft.** Record
   decisions, branch state and proposed ownership. No code changes.
2. **Dependencies.** Pin Team 3 implementation/internal interface and shared
   contract; produce a lockfile and verify normal `uv sync --frozen` installation
   and imports with the complete Python 3.14 application environment. An ad-hoc
   pip success alone is not sufficient. Investigate source overrides within this
   scope; do not globally bypass dependency controls as an unexplained fix.
3. **Construction/configuration.** Build the package provider, establish explicit
   credential/token-file handling and map initialization errors before writes;
   test without real credentials or provider calls.
4. **Workflow wiring.** Inject the imported implementation into
   `DocumentSummaryStore`; verify UTF-8 readback and response behavior. Audit and
   remove obsolete HTTP code/references in a separate cleanup commit if needed.
5. **Failure policy implementation.** Test definite rejection, uncertain write,
   post-create readback failure and compensation/preservation. Reassess Ka Pui's
   connection-error concern at the package boundary; do not mechanically port
   HTTP exception classification.
6. **Authentication and live probe tooling.** App setup can proceed now. After
   installation, Kristie authorizes the intended account using the reused app;
   adapt the opt-in probe and offline tests, document isolated paths and cleanup.
7. **Live evidence.** Run package CRUD and then the composed workflow when all
   integrations are ready; record exact revisions, readback, independent account
   inspection and cleanup. Never label authentication-only checks as CRUD.
8. **Integration handoff.** Reconcile upstream changes, run required checks,
   update PR/design status and retain Team 1 swap as pending until verified.

## Review and completion checklist

- [ ] Real workflow summary operations call the imported Team 3 implementation.
- [ ] Frozen install, lint/format, strict typing and relevant offline/full tests
  pass for the integrated dependency set; record actual results.
- [ ] Python 3.14 real package execution is checked, or incompatibility is
  resolved with the team before changing the repository Python requirement.
- [ ] Known summary path behavior survives the transition.
- [ ] Package configuration failure and operation uncertainty satisfy cleanup
  rules; Ka Pui's failure-classification concern has explicit test evidence.
- [ ] Latest #52/#53 changes and stacked-PR relationship are reconciled.
- [ ] Team 5 account authorization, real package CRUD and full-workflow evidence
  are recorded separately from historical HTTP checks.
- [ ] Team 1 supplies a compatible package; configuration-only swap is verified.
- [ ] Ka Pui reviews the storage handoff and updates the cross-vertical design.

The listed review concerns come from prior team discussion. This plan is not a
claim that every review comment is resolved; reconcile the latest review items
again before marking #55 ready. Detailed installation findings and pinned source
links remain in [package research](HW3_STORAGE_PACKAGE_RESEARCH.md).
