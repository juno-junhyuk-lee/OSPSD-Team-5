# HW3 storage integration

Owner: Kristie Lee (Member 4). This is the storage contribution to Member 5's
DESIGN.md and the operator handoff. Internal and outside-team design reviews
remain pending. Codex assisted with inspection, implementation, tests and HTTP
verification; the student owner remains responsible for understanding the work.

## Status and evidence

See the [review/design handoff](HW3_STORAGE_REVIEW_HANDOFF.md) for the local versus
remote PR snapshot, concern-by-concern status and proposed #56 updates.

Current package setup and probe commands:
[Team 5 Dropbox authorization](HW3_STORAGE_AUTH.md).

Package integration is now required following Hari's clarification reported by
Kristie. The workflow now uses Team 3's imported package through the scoped
factory described in the [package transition plan](HW3_STORAGE_PACKAGE_TRANSITION.md).
Use the package authorization guide for runtime configuration. HTTP evidence below
is historical and does not establish package integration. John approved Team 3
commit `fde60d4`; Juno approved reuse of the Team5-Review Dropbox app. Kristie
reports successful OAuth with the intended Team 5 account. The package storage
probe and local real-provider composed workflow passed. Independent inspection,
deployed workflow verification and the Team 1 swap remain pending.

Local composition at `e2616dd` returned 201, then passed issue fresh read,
Calendar readback, exact summary-byte verification and summary/event/issue
cleanup with absence checks. See [workflow evidence](WORKFLOW.md#local-real-provider-workflow-evidence)
for the creation and separate cleanup records. This does not turn the earlier
storage-only probe into deployed or independently inspected evidence.

### Package live verification

[Package evidence](evidence/HW3_STORAGE_TEAM3_PACKAGE_20261116-211419.json) ran
November 16, 2026, 21:14:20–21:14:27 America/New_York (November 17, 02:14 UTC),
at application base `50ad4960e3792f5fad9cf44cbfee17e3c48d32db`, Python 3.14.8.
Installed Team 3 implementation/internal interface both resolve to approved
`fde60d4fb648df6defb918ff815fe940c525adc7`; shared contract tag `0.3.1` resolves
to `664afc9` (distribution version `0.2.0`); Dropbox SDK is `12.2.5`.

Provider health, summary upload/exact UTF-8 readback, duplicate-create conflict,
original-byte preservation and cleanup all passed. The 104-byte UUID file under
`/ospsd-team5-hw3` was confirmed absent by package metadata lookup after deletion.
Kristie reports exit code 0. Review matched all six recorded source/lockfile
hashes against the current checkout, and independently reconstructed the probe
payload hash/size and checked the metadata path/reference for consistency.

Kristie did not observe the file in the Dropbox web UI. Direct contents inspection
and independent cleanup confirmation are therefore not established; retain the
JSON's `direct_provider_verification=pending`. The probe does not exercise
`POST /workflows/scheduled-issues`, deployed composition, Team 1 swapping or live
failure injection. No credential values were included in the evidence.

### Historical HTTP verification

The storage adapter is connected to the local scheduled-issue workflow. Team 3's
real test service passed summary creation, exact UTF-8 download comparison,
duplicate-create conflict, original-content preservation and cleanup. This does
not establish direct Dropbox inspection or deployed three-vertical success.

[Recorded evidence](evidence/HW3_STORAGE_TEAM3_LIVE_2026-11-15.json) ran November
15, 2026, 01:02:50–01:02:56 America/New_York (06:02 UTC). Its application base is
`736efc8`; hashes identify the exact application files and then-uncommitted probe.
Commit `0d13358` subsequently records that script, its tests and the evidence.
The recorded hashes identify the files tested at that time; later application
changes, including the optional failure-path field, are not new live evidence.
Do not rewrite the historical base commit merely because evidence was committed later.

Full offline checks after the probe implementation: 900 passed, 58 opt-in tests
skipped; Ruff lint/format, strict mypy and probe-script mypy passed. The existing
Starlette TestClient deprecation warning remains. No remote CI or release claim
is made for this local branch.

| Remaining evidence | Owner or dependency |
| --- | --- |
| Direct Dropbox contents inspection and independent cleanup confirmation | Kristie (Member 4) with an authorized Team 5 teammate on the selected account |
| Real configuration-only Team 1 package swap | Kristie (Member 4); supported package, namespace and shared-contract alignment pending Team 1 reply |
| Deployed composed workflow against both configurations | Kristie (Member 4) and Members 1 and 5 with the other integration owners |
| Integrated checks, design/code reviews and submission | Component owners and Member 5 |

## Architecture and contract

See [package feasibility research](HW3_STORAGE_PACKAGE_RESEARCH.md) for isolated
consumer installation findings and the remaining package-swap requirements.

```text
Member 1 workflow: issue -> Calendar -> Markdown and filename
  -> SummaryStore.save_summary(name, markdown)
     DocumentSummaryStore: configured folder + filename; UTF-8 encoding
       -> DocumentStorage.create(path, bytes)
          Team 3 DropboxDocumentStorage -> DropboxClient -> injected Dropbox SDK
       -> DocumentStorage.download(path); compare exact bytes
  <- StoredSummary.id -> combined workflow response
```

The official `cloud-storage-api` dependency comes from
[contract tag 0.3.1](https://github.com/Dayana20/ospsd26-cloud-storage/tree/0.3.1),
commit `664afc92f7cc0b2ee51cde6ddfa088cc3b37206c`, subdirectory
`src/cloud_storage_api`. Its internal package version is `0.2.0`.
Team 3's imported implementation provides all eight abstract methods: create, replace, download,
metadata, list, move, delete and provider health. Reads return shared FileInfo
or bytes; provider SDK types and error messages do not cross our boundary.

Member 1 owns the summary template, filename, orchestration, compensation and
deployment. Kristie (Member 4) owns package construction, settings, storage validation and evidence.
The existing internal handoff is `(name, markdown)`, not `(path, bytes)`; the
bridge supplies the root and encoding without changing the public response.
`summary.id` is an opaque provider ID, or the path when the contract returns
`id=None`. It is not guaranteed to be a URL. To locate a workflow file, combine
the configured root with `summary_name(issue, event)` from `app/workflow.py`.

## Configuration and use

Use [Team 5 Dropbox authorization](HW3_STORAGE_AUTH.md) for package environment
variables, OAuth and the opt-in probe. Normal installation is `uv sync --frozen`.
`STORAGE_ROOT_PATH` supplies the isolated app-folder destination; Dropbox
credentials belong to Team 5, not a remote storage service. The workflow owns
the SDK lifetime and disables automatic SDK retries. There is no endpoint URL,
HTTP storage fallback or `STORAGE_BEARER_TOKEN` configuration.

The probe requires `--execute` and a new evidence output path. It checks initial
absence, creates one UUID file, verifies exact UTF-8 bytes and conflict behavior,
then cleans only that scratch file and confirms absence. It leaves the folder
intact. This scratch cleanup policy differs from production recovery.

The local endpoint also requires Trello and Google configuration:
[workflow setup and evidence](WORKFLOW.md). Hosted bearer authentication and
Secret Manager/deployment configuration remain the deployment owners' work.
Local environment variables do not configure Cloud Run.

## Decisions and failure behavior

The [failure policy](HW3_STORAGE_FAILURE_POLICY.md) records the implemented
package rules and historical HTTP proposals. Known pre-send creation failures
or definite shared rejections compensate event then issue; unknown outcomes
preserve both and the possible summary. A successful upload followed by failed
readback stays uncertain. No writes are automatically retried.

Configuration failures return 503 before workflow writes. Operation failures
return 502. Known summary destinations are reported in optional leftover
`path`, separately from provider `id`; paths do not prove existence. Messages
and logs do not expose credentials or raw provider errors.

The obsolete HTTP adapter/transport/settings and their dedicated tests are now
removed. `app/storage_paths.py` owns provider-independent path validation;
package/summary modules and the probe no longer depend on an HTTP adapter.
Historical evidence is unchanged and retains its original source filenames and
hashes. Test counts recorded for earlier commits remain historical results.

## Real implementation swap

A Team 1 package swap is still pending. The inspected Team 1 source has generic
`app` namespace, packaging metadata and shared-interface mismatches; see
[package research](HW3_STORAGE_PACKAGE_RESEARCH.md). Obtain a supported compatible
package and construction API, implement provider selection, then verify the
same workflow under both configurations. A URL change is not the package swap,
and no completed selector or Team 1 live run is claimed.

Independent teammate inspection, deployed workflow/failure verification and
design/code review completion remain tracked in the
[review handoff](HW3_STORAGE_REVIEW_HANDOFF.md).
