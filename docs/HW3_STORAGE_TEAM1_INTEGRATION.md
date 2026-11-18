# Team 1 package integration progress

Owner: Kristie (Member 4), with Codex assistance. November 17, 2026.
Dependency-scope baseline: `3eaa34c` after Kristie merged #58 and fast-forwarded
the local storage branch. Dependency installation and provider selection are now
implemented locally; real configuration-only swap evidence is still pending.

## Pinned candidate and shared installation

- Distribution: `team1-dropbox-storage==0.1.0`.
- Repository: `Dayana20/sandbox`, subdirectory `packages/team1_dropbox`.
- Approved candidate supplied by Yashwanth:
  `784be97fc111338c6746b9d7288bf84a333a9b16`.
- Import: `from team1_dropbox import Team1DropboxStorage`.
- Constructor supports `Team1DropboxStorage(client=sdk)`, allowing our scoped,
  no-retry SDK and existing explicit refresh-token configuration to be reused
  in the next implementation scope. No Team 1 credentials are required.
- Team 3 remains pinned at `fde60d4fb648df6defb918ff815fe940c525adc7`.

Install normally with `uv sync --frozen`; no manual pip command is needed.
The root project declares both implementation packages and one official shared
contract. Team 1's candidate is packaged under its own namespace, resolving the
earlier generic `app` collision at the old service revision. Those historical
findings must not be applied to this new package.

## Dependency reconciliation

Initial resolution failed because the two providers declare the same shared
contract with Git URLs differing by `.git`. Matching the root source spelling
alone did not resolve the transitive conflict. A narrowly scoped
`tool.uv.override-dependencies` entry unifies only `cloud-storage-api` at Git
tag `0.3.1` and subdirectory `src/cloud_storage_api`. The lock still resolves
commit `664afc92f7cc0b2ee51cde6ddfa088cc3b37206c`; its distribution version is
`0.2.0`. No contract revision or SDK version requirement is bypassed.

Team 1 requires Dropbox SDK exactly `12.1.0`; Team 3 permits it. The new lock
therefore changes `dropbox` from `12.2.5` to `12.1.0` and `stone` from `3.5.5`
to `3.3.9`, adding `ply==3.11` and `six==1.17.0`. Other integration contract pins
remain unchanged. Recheck the source override when upgrading either provider.

uv warns that Team 1's repository-root pyproject lacks a project table. The
target subdirectory nevertheless built and installed the named distribution;
this was not an installation failure or a fallback `app==0.0.0` installation.

## Verification and limits

Frozen installation succeeded in the current environment and a separate empty
Python 3.14.8 environment using the full application lockfile. In both, an
offline probe imported the Team 5 summary module and both implementations,
constructed both with a synthetic SDK client, verified official `DocumentStorage`
identity/no abstract methods, and checked installed Git provenance. The probe
cleared inherited Dropbox configuration, disabled dotenv and blocked network
access. It read no credential file and performed no provider operation.

With SDK `12.1.0`, the existing full suite passed: **896 passed, 58 skipped**,
including Team 3 construction, workflow failure/cleanup and probe tests. Ruff
lint/format, strict mypy, the probe-specific mypy check and `git diff --check`
passed. The existing Starlette TestClient warning remains. The known #53
validation-precedence gap is unchanged; passing this suite does not resolve it.

This proves installation/import/construction compatibility, not method
conformance, Team 1 failure certainty or real CRUD. Next scopes add provider
selection, verify both error mappings and probe provenance, then perform the
actual configuration-only swap and record new real-provider evidence. Existing
Team 3 evidence uses its original lock/SDK and remains historical.

## Step 3: configuration-based selection

`PackageStorageSettings` reads `STORAGE_IMPLEMENTATION`, accepting
`team3_dropbox` (default) and `team1_dropbox` only. The factory imports and builds
only the chosen implementation using the same SDK, credential snapshot, token
file behavior, timeout and disabled retries. Unknown direct settings or invalid
environment selector values fail before SDK construction. Constructor failure
closes the SDK and returns a sanitized configuration error; it never triggers
fallback to the other implementation.

Team 3 retains its typed cause-chain summary classification. Team 1 uses the
generic conservative shared-contract classification for now, so Team 3-specific
exception-chain assumptions cannot accidentally classify Team 1 failures.
Provider-specific failure refinements and the cross-provider probe/error matrix
remain step 4. The probe already records the selected implementation label and
both installed package provenances to avoid falsely identifying a Team 1 run as
Team 3. This metadata update is not a claim of a live Team 1 run.

Offline tests verify default/explicit selection, actual implementation types,
real SDK initialization without network, no fallback on either constructor
failure, invalid-selector pre-write errors, client cleanup and a real Team 1
wrapper through the normal workflow route with controlled SDK upload/download.
No credential file or live provider was used by these tests.
Step 3 validation: **908 passed, 58 skipped**, including 12 added selector/wiring
cases. Ruff lint/format, strict mypy, probe-specific mypy and `git diff --check`
passed; the existing Starlette TestClient warning remains.

Source: [Team 1 README at the pinned candidate](https://github.com/Dayana20/sandbox/blob/784be97fc111338c6746b9d7288bf84a333a9b16/packages/team1_dropbox/README.md).

## Step 4: failure matrix and probe provenance

Team 1 now has a provider-specific summary-store subclass. It recognizes only
typed Requests ConnectTimeout or ConnectionError wrapping urllib3 NewConnectionError
through its pinned backend's direct shared-error cause. Team 3 retains its
separate shared -> builtin -> SDK chain check. SDK retry counts remain zero.
Both preserve unknown outcomes and treat earlier successful creation as dominant
over any later readback failure. A local SDK validation exception that Team 1
maps to generic ProviderError stays uncertain; no message-based inference or
provider-source patch is used to pretend otherwise.

The workflow regression matrix exercises BOTH real imported implementations
with controlled SDK failures: connection establishment, unknown connection/read
failure, applied upload with lost reply, definite conflict/permission rejection,
malformed metadata, unexpected errors, readback 404/mismatch and cleanup failures.
It checks no write retries, no summary deletion/probe during recovery, known
leftover paths, event-before-issue compensation and NOT_FOUND cleanup semantics.

Probe tests separately use a controlled shared DocumentStorage boundary under
each selector, testing scratch ownership, duplicate conflict/byte preservation,
uncertain-upload cleanup and cleanup failure records. CLI tests verify both
selected implementation labels, installed Team 1/Team 3 commit provenance,
successful/failed exit status and evidence preservation. The workflow/constructor
tests cover actual provider wiring; the probe matrix alone is not package CRUD
conformance. No live provider calls or evidence-file changes occurred in step 4.
Validation: **940 passed, 58 skipped** (32 additional matrix/provenance cases).
Ruff lint/format, strict mypy, probe-specific mypy and `git diff --check` passed.
The existing Starlette TestClient deprecation warning remains. The known #53
validation-precedence issue is outside this storage scope and still requires
the final upstream workflow update.

## Step 6: local configuration-only swap evidence

Kristie executed the checks at unchanged application commit
`bf66e7f77c314a4e7b219706a58fba5a622b4c03`, Python 3.14.8, with the joint
lockfile/SDK `12.1.0`. Both implementations were already installed. The operator
helper changed only `STORAGE_IMPLEMENTATION` between provider runs and checked
that root/credential values, source manifest and application commit stayed the
same. Each request used a unique synthetic title and generated new resources;
the requested event time instants were the same. No source change/reinstall was
used to switch providers.

| Evidence | Result |
| --- | --- |
| [Team 3 probe](evidence/HW3_STORAGE_SWAP_20261117-230617-13ddc1a8_team3_dropbox.json) | Health, upload/exact UTF-8 readback, conflict, byte preservation and cleanup passed |
| [Team 1 probe](evidence/HW3_STORAGE_SWAP_20261117-230617-13ddc1a8_team1_dropbox.json) | Same checks passed under the same source hashes and installed package provenance |
| [Paired local workflows](evidence/HW3_WORKFLOW_SWAP_20261117-233215-29b1f2af.json) | Team 3 then Team 1 each returned 201, passed issue/Calendar/summary readback, and confirmed all three resources absent after cleanup |

Storage probes ran November 17, 2026, 23:06:19–23:06:33 America/New_York.
The successful workflow pair ran 23:32:18–23:32:32 (November 18, 04:32 UTC).
An initial Trello authentication issue was resolved before the successful pair;
its diagnostic record is archived locally outside the repository. It is not
evidence of the required controlled storage-failure demonstration.

Readback used the imported issue provider with `fresh=True`, the Calendar
package and the selected storage implementation. All matching checks preceded
cleanup, which ran summary -> event -> issue with absence checks. Review verified
shared commit/source manifests, package pin records, helper hash, distinct IDs,
title/time equivalence, summary paths and downloaded-content hashes against the
returned Markdown. Original JSON files were not edited.

The one-off operator helper lives in ignored `.venv`; its source hash is recorded
and matched during review, but its source is not included in the committed
evidence. This is local FastAPI TestClient execution with real providers, not a
deployed endpoint test or an independent human inspection. The record explicitly
sets `pending_final_53_fix=true`; final #53 validation/hosted-auth follow-up,
post-sync regression checks, independent inspection and deployment verification
remain separate tasks. No new live operation was performed during documentation
review, and no credential values were requested or recorded.
