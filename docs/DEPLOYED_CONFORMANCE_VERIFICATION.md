# Deployed shared conformance verification

Owner/operator: Juno Lee, with Codex assistance. Recorded November 11, 2026.
The harness was run by Codex using existing authorized credentials; this is not
an independent teammate verification or a published release.

## Revision and result

| Item | Observed value |
| --- | --- |
| Application/configuration commit | `191b006c1bed59796f36321eb6f905d4768ba85d` |
| Deployment | [Deploy run 43100667215](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/43100667215) |
| Environment | `demo`, project `ospsd-team5`, region `us-central1` |
| Endpoint | `https://team5-calendar-demo-dnuukwp5ga-uc.a.run.app` |
| Ready revision, read back after testing | `team5-calendar-demo-00005-ld8` |
| Image digest | `sha256:e8061e066395fca3753831467a0760de44b94c4bfda058bef39254f74ceb8961` |
| Run window | November 11, 2026, 21:24:54–21:25:14 UTC (16:24:54–16:25:14 EST) |
| Result | 33 passed, exit 0; one existing Starlette TestClient deprecation warning |
| Independent Google cleanup search | 0 matching events before, 0 after; no new remaining events |

The deployment manifest and Cloud Run API agree on the revision/image. The
application was not redeployed for this check. The test harness was uncommitted
on `doc/hw2-final-design-md`, based on the application commit above. Exact input
SHA-256 values at the passing run:

- `tests/test_shared_conformance.py`: `f59e4555d017828324ac8e55510035f7eacacd1bdbf8e77087cd5360ce6c0d53`
- `tests/conformance_support.py`: `929a61083449fcb4fd48d720a0cc9e88f4b13db3619ef2a3e628df46aacfdd05`

Do not relabel this as a run of the later harness commit or final release.

## What the 33 checks establish

The tagged `CalendarServiceConformance` suite is inherited without changing the
shared package or production service. A test-only `HttpCalendarService` sends
normal calls through deployed HTTPS and translates the shared HTTP error envelope
back to `CalendarError` for the Python suite.

- Eight inherited normal-operation/not-found cases use deployed HTTP and real
  Google Calendar, including repeated creation, replacement/read-back, deletion,
  and missing-event errors.
- Fourteen inherited provider-failure cases still use local controlled adapters.
  They check Team 5's shared error translation, not injected failures in demo.
- Two inherited invalid-input cases check shared Python request models locally.
- One extension changes the start to a different instant and checks both PUT's
  response and subsequent GET; the tagged suite's original start is equivalent
  to its create start and cannot establish that guarantee alone.
- Eight HTTP extensions exercise POST/PUT unknown, missing, and legacy fields
  (422) and empty/malformed POST JSON (400) against the deployed service.

Thus 17 cases exercise deployed HTTP, 14 use controlled failures, and two check
models locally. No production fault-injection switch was added. The initial
harness run misclassified expected POST 422 responses as uncertain creation;
the guard was corrected and the final run above passed without application edits.

## Cleanup and regression checks

The local fixture override registers missing-event IDs before deleting them.
Teardown attempts every unique tracked ID, ignores already-deleted events, and
reports aggregate failures only after all attempts. The HTTP bridge captures
known create IDs before response-model validation. It does not retry writes.
If a create transport failure leaves no ID, inspect the test calendar before
another run; automated cleanup cannot identify an unknown write with certainty.

Offline regressions cover initial-delete failure, continued cleanup after
provider/unexpected failures, already-deleted events, invalid create responses
with known IDs, no retry after uncertain creation, strict Boolean retry advice,
and detection of an ignored start update.

For the recorded run, independent Google SDK queries used `q=Conformance`,
`showDeleted=false`, and January 7, 2030 UTC as the event-time window. The complete
result contained zero items before and after testing. No unrelated events were
deleted. OAuth and bearer values were read privately from their pinned Secret
Manager versions, kept out of output, and the temporary bearer file was removed.

## Reproduce

Use Python 3.14 and the locked dependencies. Obtain the demo bearer file through
the team's private credential process; do not put it in the repository or shell
history. This command creates and deletes real test events:

```sh
uv sync --frozen
CALENDAR_DEPLOYED_CONFORMANCE=1 \
CALENDAR_LIVE_CONFORMANCE=0 \
CALENDAR_VERIFY_URL=https://team5-calendar-demo-dnuukwp5ga-uc.a.run.app \
CALENDAR_VERIFY_BEARER_FILE=/absolute/private/path/demo-key \
uv run pytest -v \
  tests/test_shared_conformance.py::TestDeployedCalendarServiceConformance
```

Only the remote bearer is required by the pytest command; direct Calendar OAuth
access is needed separately for an independent cleanup search. Tests use no
automatic retry and will not follow redirects. Health/readiness must pass before
the service fixture yields. Offline CI runs the equivalent HTTP harness on fake
Google and explicitly disables both live flags.

## Fresh log and trace evidence

Cloud Logging returned 86 application outcome entries for the run window,
with no next page. Both examples identify release `191b006`:

| Case | UTC time | Log | Trace |
| --- | --- | --- | --- |
| Create success, 201 | 21:25:10.209786 | [Log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Fa746fb15347308dc25c936efd9d0e3a5%22?project=ospsd-team5) | [Trace](https://console.cloud.google.com/traces/explorer;traceId=a746fb15347308dc25c936efd9d0e3a5;spanId=a2ebe4bb098994ad?project=ospsd-team5) |
| Invalid create, 400 | 21:25:13.447158 | [Log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2F0b578707e0569072ee8bee32ae6183fa%22?project=ospsd-team5) | [Trace](https://console.cloud.google.com/traces/explorer;traceId=0b578707e0569072ee8bee32ae6183fa;spanId=ea83b199a6b1bf7c?project=ospsd-team5) |

Both traces were retrieved through Cloud Trace. Success includes
`calendar.create` and `google.calendar.events.insert`; invalid input includes
only `calendar.create`. Use November 11, 21:24:54–21:25:14 UTC and release
`191b006c1bed59796f36321eb6f905d4768ba85d` in the
[dashboard](https://console.cloud.google.com/monitoring/dashboards/custom/c25e66c8-e3e3-44bc-af2b-6707ca37a175?project=ospsd-team5).
This check retrieved logs/traces; it did not re-execute dashboard chart queries
or repeat the historical provider-failure injection.

## Local checks

After the conformance and documentation changes: Ruff lint/format, strict mypy,
and `git diff --check` passed. Full offline pytest: 693 passed, 58 opt-in tests
skipped, one existing warning. These results are local; CI for the new commit
must run after the team pushes it.

## Remaining release work

Commit and review the harness/docs, verify matching CI/deployment on the selected
submission revision, and repeat final verification as needed after changes.
An independent teammate must verify the annotated release tag before GitHub
Release publication. Grader access and the submission links remain team tasks.
