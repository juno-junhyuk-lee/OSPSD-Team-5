# HW3 storage integration

Owner: Kristie Lee (Member 4). This is the storage contribution to Member 5's
DESIGN.md and the operator handoff. Internal and outside-team design reviews
remain pending. Codex assisted with inspection, implementation, tests and HTTP
verification; the student owner remains responsible for understanding the work.

## Status and evidence

Current package setup and probe commands:
[Team 5 Dropbox authorization](HW3_STORAGE_AUTH.md).

Package integration is now required following Hari's clarification reported by
Kristie. The workflow now uses Team 3's imported package through the scoped
factory described in the [package transition plan](HW3_STORAGE_PACKAGE_TRANSITION.md).
Use its runtime configuration table; the HTTP setup sections below describe the
previous adapter and probe, not the current workflow setup. HTTP evidence below
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
The adapter implements all eight abstract methods: create, replace, download,
metadata, list, move, delete and provider health. Reads return shared FileInfo
or bytes; provider SDK types and error messages do not cross our boundary.

Member 1 owns the summary template, filename, orchestration, compensation and
deployment. Kristie (Member 4) owns transport, settings, storage validation and evidence.
The existing internal handoff is `(name, markdown)`, not `(path, bytes)`; the
bridge supplies the root and encoding without changing the public response.
`summary.id` is an opaque provider ID, or the path when the contract returns
`id=None`. It is not guaranteed to be a URL. To locate a workflow file, combine
the configured root with `summary_name(issue, event)` from `app/workflow.py`.

## Configuration and use

| Variable | Meaning |
| --- | --- |
| `STORAGE_BASE_URL` | Required API base URL. HTTPS, or HTTP on loopback for local testing/tunnels |
| `STORAGE_ROOT_PATH` | Required isolated folder such as `/ospsd-team5-hw3`; root `/` and traversal are refused |
| `STORAGE_TIMEOUT_SECONDS` | Default 30; finite, greater than zero and at most 120 |
| `STORAGE_BEARER_TOKEN` | Optional caller token, supplied outside Git; not needed by Team 3's documented public test service |

Credentials are never part of URLs or evidence. Provider Dropbox credentials
stay on the storage team's service. Our HTTP client closes after success or
failure, does not retry, does not follow redirects and ignores environment proxy
settings. Team 3's public test service must contain synthetic, non-sensitive data.

```powershell
uv sync --frozen
$env:STORAGE_BASE_URL = 'https://cloud-storage-service-test-gyesjhieva-uc.a.run.app'
$env:STORAGE_ROOT_PATH = '/ospsd-team5-hw3'
uv run python -m scripts.verify_storage_live --execute --output storage-run.json
```

The explicit `--execute` flag is required: the probe creates/deletes one UUID-named
file. It checks the path is absent first, never deletes an occupied/conflicting
path, reconciles uncertain uploads through cleanup, and records cleanup failures.
It leaves the configured folder intact. Use a fresh output filename to preserve
older records. The output includes source hashes, API outcomes and file metadata.

To run the composed endpoint locally, also configure the issue service and Google
credentials following [the workflow](WORKFLOW.md) and existing Calendar setup,
then run `uv run uvicorn app.main:app`. A request to
`POST /workflows/scheduled-issues` uses `title`, `start` and `end`. Hosted mode
requires the existing caller authentication. Member 1 must add the integration
settings to the managed deployment configuration: exporting local variables does
not configure Cloud Run, and the current Terraform service does not wire storage
settings. This storage branch does not deploy or modify infrastructure.

## Decisions and failure behavior

See the [failure certainty and cleanup plan](HW3_STORAGE_FAILURE_POLICY.md) for
current behavior, Ka Pui's pre-send failure feedback, and HTTP/package regression
criteria. It is a follow-up plan; the connection-failure implementation is unchanged.

| Decision | Constraint, alternative and accepted tradeoff |
| --- | --- |
| Depend on shared contracts and HTTP | Allows endpoint-only swaps; importing a team's SDK would tie the workflow to its provider. Revisit when the shared protocol changes, reporting mismatches to its owners. |
| Read back every summary | Adds one read and latency, but verifies contents before success. Metadata-only success would be cheaper and weaker. Revisit for larger documents. |
| Treat provider failures as uncertain writes | Timeouts/5xx/invalid write responses may follow a completed upload. Automatic retries could duplicate work. Revisit only with agreed idempotency and certainty guarantees. |

Bad connection/root settings return 503 with `step=summary` and `leftovers=[]`
before any issue/event write. Definite storage rejections, such as conflict,
become the existing 502 summary failure and trigger event-then-issue compensation.
The existing file is never overwritten or deleted. A lost response, malformed
upload metadata, failed download or mismatched bytes produces a non-retryable
502 with possible summary state; the workflow keeps its issue and event.
Reconcile the known destination before retrying. An uncertain summary leftover
now includes `path` when known, while keeping `id=null` when no provider ID is
reported. The path comes from the locally constructed root and filename, not
remote error messages. If the store does not supply a path, the field is omitted.
No URL or credential is added. Readback errors and mismatched contents also carry
the destination. This additive field leaves success responses, retry advice and
compensation behavior unchanged and can be supplied by HTTP or package stores.

Controlled endpoint tests cover these paths. The real probe covers only the
successful storage path and conflict; it is not the required controlled failure
demonstration through the deployed composed API. Member 1's separately reviewed
validation/issue-configuration schema fixes remain outside this storage change.

## Real implementation swap

Team 3's [HW2 service documentation](https://github.com/Shreyas191/OSPSD-Team-3/blob/3411cdf8d5723a6ebda3e6799ab3e1384819767f/README.md)
publishes the test endpoint above. Its current submission implementation is on
`hw2`, not `main`; the exact running revision still needs owner confirmation.

Team 1's [deployment guide](https://github.com/Dayana20/sandbox/blob/6567b262559df46c85371182573cc1242b17c031/docs/DEPLOYMENT.md)
exposes port 8000 only on the OCI VM's loopback. Its README lists localhost
examples, not an external API URL. The `hw2-milestone3` code has the shared route
shapes, but its docs reference contract 0.2.0; live compatibility is unverified.

1. Obtain Team 1's reachable HTTPS endpoint or supported tunnel, running revision,
   any caller authentication, approved scratch folder and direct-provider contact.
2. Record the application commit. Change only storage URL, required credentials
   and folder configuration, then restart/redeploy. Do not change workflow or
   adapter code. Existing files remain in the old service; no migration occurs.
3. Run the same probe with a fresh evidence output. Then run a fresh complete
   scenario through the deployed composed endpoint for each configuration.
4. Compare stored bytes with the returned Markdown; confirm issue/event/file
   records independently in all providers and record cleanup with their owners.
5. Attach both configurations' evidence, matching application commit and review
   responses to the final submission. Report mismatches rather than adding
   silent provider-specific branches or claiming a successful swap.

Suggested request to Team 1 (draft, not sent):

> Hi Team 1, I'm Kristie (Member 4) from Team 5. For HW3's configuration-only storage swap,
> could you share your reachable endpoint or supported tunnel, running revision,
> caller authentication requirements and a scratch folder? We found the shared
> routes on hw2-milestone3, but the deployment guide lists VM-local port 8000.
> We'd also like a contact for direct Dropbox verification and cleanup.

Suggested request to Team 3 (draft, not sent):

> Hi Team 3, our summary probe passed against your test endpoint, including exact
> byte comparison, conflict and cleanup. Could we confirm the running revision
> and coordinate a /ospsd-team5-hw3 scratch location plus direct Dropbox inspection
> during our full workflow run? Please arrange access securely, without tokens in chat.
