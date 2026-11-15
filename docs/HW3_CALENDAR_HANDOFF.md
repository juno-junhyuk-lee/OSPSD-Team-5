# HW3 Member 2: Calendar handoff

Owner: Jim Lo. AI assistance: Codex assisted with implementation, tests, and
documentation. Student review and teammate PR review remain required.

## Integration proposal and boundary

Reuse `get_calendar_service` from `app/calendar_service_dependencies.py` through
FastAPI `Depends`, as Member 1's PR #53 already does. It returns the tagged
`CalendarService` protocol backed by Team 5's `GoogleCalendarService`. Do not
call the dependency function without supplying its arguments: FastAPI resolves
the four operation providers. Do not create another Calendar HTTP adapter for
our in-process workflow or call Google directly from the orchestrator.

The contract remains `calendar-contract` tag `v0.1.0-rc.1`, commit
`1c1cad7a0732ddb242a05400d8833d94e4422424`; install with `uv sync --frozen`.
Python 3.14 is required by this application. No dependency update is needed.

| Call | Input | Result |
| --- | --- | --- |
| `create` | `CreateEvent(title, start, end)` | `Event(id, title, start, end)` |
| `get` | Provider event ID | Same four-field Event |
| `replace` | Event ID and `ReplaceEvent(title, start, end)` | Updated Event with same ID |
| `delete` | Event ID | None; absent/already deleted raises `NOT_FOUND` |

Times are RFC 3339 strings with offsets and end after start. Use whole seconds
for portable verification and compare instants, not offset formatting. Unknown
fields and legacy `start_time`/`end_time` are rejected. Google writes trim titles.
The shared core covers timed events and does not promise listing, provider URLs,
descriptions, attendees, or an idempotency key.

## Configuration and credentials

| Setting | Meaning |
| --- | --- |
| `CALENDAR_IMPLEMENTATION=google` | Explicit Team 5 implementation selection; default is google for compatibility |
| `CALENDAR_MODE=local` | Default: existing local OAuth setup |
| `CALENDAR_MODE=hosted` | Existing deployment startup validation and bearer authentication |
| `CALENDAR_TOKEN_FILE` | Hosted OAuth token file mounted from secret storage |
| `CALENDAR_BEARER_FILE` | Hosted API access key file; separate from Google OAuth |
| `CALENDAR_RELEASE` | Hosted full application commit SHA |

Only `google` is supported by this selector. Unknown or empty values fail with a
sanitized, non-retryable `CalendarError(PROVIDER_UNAVAILABLE)` before provider
calls. This is an explicit configuration boundary, **not evidence of switching
to another team's Calendar**. The team's planned swap demonstration belongs to
Member 4's storage integration. Extending Calendar selection requires a reviewed
implementation of the same protocol; test overrides are not a deployment swap.

Keep the existing Google account configured in the execution layer. Local setup
uses ignored `credentials.json`/`token.json` files via the existing auth script;
never commit or paste them into evidence. Hosted tokens remain in secret storage.
Both paths operate on the configured account's primary calendar. API bearer
authentication does not select a different user's Google account.

The factory is lightweight: successful dependency construction does not prove
Google authorization is usable. Local token errors can occur during `create`,
after Member 1 has created an issue. Hosted startup validates configuration,
but remote expiry/revocation can still happen later. Member 1 must handle these
as step failures and apply its documented recovery policy.

## Failure handoff to Member 1

| Calendar create outcome | Shared error | Orchestrator action |
| --- | --- | --- |
| Permission explicitly denied | `ACCESS_DENIED`, false | Stop; handle earlier issue under the recovery policy |
| Missing/rejected OAuth | `PROVIDER_UNAVAILABLE`, false | Repair authorization; no blind retry |
| Failure before write or explicit quota rejection | `PROVIDER_UNAVAILABLE`, true | No automatic write retry; account for earlier issue and cleanup first |
| Write sent but response lost/malformed | `PROVIDER_ERROR`, false | Outcome uncertain; keep references, inspect Google before another create |

`retryable` is the Calendar operation's advice, not permission to repeat the
whole composed workflow. Google insertion uses `num_retries=0`. Never translate
an uncertain create into a retryable workflow error or assume no event exists
because no ID returned. No transaction spans the providers.

Member 1 owns compensation. After a definite storage failure, its policy deletes
the confirmed event, then the issue. Calendar `NOT_FOUND` during cleanup counts
as already removed. Other deletion failures must remain visible. A delete timeout
can mean deletion succeeded; report uncertainty and reconcile by known ID.
After an uncertain storage write, preserve event/issue references for inspection.

PR #53 currently emits plain errors on some dependency/validation paths despite
advertising workflow errors with `step` and `leftovers`. Its owner must resolve
that HTTP contract issue; Member 2 does not alter the workflow error handlers.

## Verification and evidence

Run the repository lint, format, strict typing, and offline tests. New
`tests/test_calendar_configuration.py` checks the real dependency chain with
controlled Google transport, default/explicit selection, cleanup, and invalid
configuration without provider calls. Existing service, conformance, and provider
failure tests cover shared translation and before/after-write distinctions.

For PR #53 integration, retain its real workflow and Calendar dependencies while
substituting only issue/storage and Google transport in tests. Check successful
creation, explicit rejection, uncertain create without retry/issue deletion,
definite storage failure cleanup, and uncertain storage preserving resources.
These checks establish wiring and policy, not live Google behavior.

Reuse `scripts.verify_put_live` for Calendar-only live verification. It changes
real test data and independently reads Google through the SDK. Use the documented
OAuth setup and a disposable test account. A full deployed workflow remains a
separate check once Members 1, 3, and 4 finish their integrations.

Record the application commit (and any uncommitted changes), contract tag,
environment, run marker, response status, provider checks, and cleanup result.
For the composed workflow, capture its returned event ID privately, independently
check title/start/end in Google, then delete the test event and verify absence.
Do not publish tokens, headers, account details, or unrelated event contents.
If creation is uncertain without an ID, search the unique run marker in Google
before another attempt; do not claim cleanup succeeded without evidence.

## Outstanding work

### November 14 offline checkpoint

Base: `hw3/milestone-1` commit `7859542`; candidate consists of this document,
the README pointer, the Calendar selector, and its five new configuration tests.
Python 3.14.8 with frozen dependencies: 698 passed, 58 opt-in tests skipped.
Ruff lint/format, strict mypy (59 source files), and `git diff --check` passed.
The existing Starlette TestClient deprecation warning remains.

In an isolated checkout of PR #53 commit `8a92484`, applying the candidate
Calendar dependency file passed seven additional controlled integration cases:
success, uncertain create, definite storage failure cleanup, three explicit
Google rejection cases (401/403/429), and uncertain storage preservation. These
review probes are outside this branch because the workflow and issue contract
have not merged into its base. They must become maintained integration tests
when that dependency lands. Two separate schema probes reproduce PR #53's known
422/503 response mismatch; they were excluded from the seven passing cases,
not reported as passing. No real-provider or deployed execution was performed.

- Review this proposal with the team and fold it into Member 5's DESIGN.md.
- Obtain teammate review of Jim's changes and the PR #53 integration evidence.
- Calendar-only real-provider verification passed on November 14 at `05808cc`;
  see [the run record](HW3_CALENDAR_VERIFICATION.md). Teammate verification remains
  separate.
- After integration/deployment, record the complete workflow's Google evidence
  and cleanup. Historical HW2 runs do not establish HW3 completion.
- Member 1 owns deployment branch/IAM configuration; the current pipeline does
  not deploy `hw3/milestone-1` automatically.
