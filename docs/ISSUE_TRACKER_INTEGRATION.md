# HW3 Member 3: issue tracker integration

## Status and ownership

Member 3 owns the HTTP adapter, dependency configuration, controlled tests, and
issue-provider verification. Member 1 owns the composed endpoint, Markdown
summary, public failure mapping, and cross-service recovery. Member 5 owns the
overall design and independent integration review. Any available teammate can
review the PR; PR and design reviews are pending.

This change supplies an integration component, not a new public endpoint. It
does not deploy or modify Team 4's service, change Calendar routes, or establish
live Trello verification. Required internal and outside-team reviews remain
pending. This note is the issue-integration design contribution for the overall
HW3 `DESIGN.md`, which Member 5 will coordinate.

## Dependencies and architecture

The official `issue-tracker-contract==1.0.0` dependency comes from
[Team 4's tagged contract][contract-tag], subdirectory `contract`, tag
`issue-tracker-contract-v1.0.0`, commit
`e2528b1a8b55ea7c74df8d222b9e6555b9d87925`. `uv.lock` records the resolved
commit. Use Python 3.14 and `uv sync --frozen`, as for the Calendar service.

```text
Member 1's composed workflow
  -> issue_tracker_contract.IssueProvider
  -> HttpIssueProvider (our HTTP adapter)
  -> Team 4 API
  -> Team 4's configured issue provider (Trello for the planned verification)
```

The adapter imports the official `Issue`, `IssueCreate`, `IssueUpdate`, and
`ServiceError` types. There is no local copy of the contract or Trello SDK code.
Team 4 keeps its provider credentials; our integration uses their HTTP API.
Direct Trello account access for independent verification is arranged separately.

## Decisions

**Use HTTP to reuse Team 4's implementation.** The alternative is importing
their provider implementation and provisioning its credentials in our process.
HTTP keeps provider setup with its owner and makes the endpoint configurable.
The cost is an extra network boundary and HTTP behavior that cannot always
express every Python-interface capability. Revisit this choice if a required
shared capability cannot be exposed remotely. Do not silently weaken it.

**Use a request-scoped, bounded HTTP client.** `get_issue_provider` returns the
shared interface and closes the client after success or failure. This avoids
global clients and startup dependencies for existing Calendar-only operations.
A lifespan-owned pool could reduce connection overhead; revisit if measured
traffic justifies it. Defaults are 30 seconds per HTTP timeout phase, configurable
above zero and up to 120 seconds. This is not an overall workflow deadline.

**Do not retry writes.** A lost response does not prove that creation failed.
The adapter preserves conservative write uncertainty for Member 1's recovery
policy. Team 4's optional idempotency header is not enabled or relied upon;
its deployed persistence/restart guarantees need separate verification before
adoption. A create can therefore be attempted only once automatically.

## Configuration and handoff

```sh
export ISSUE_TRACKER_BASE_URL=https://ospsd-team4-issue-tracker.onrender.com
export ISSUE_TRACKER_TIMEOUT_SECONDS=30
```

The endpoint above is documented by Team 4; its current deployment revision,
availability, and test-data access must be verified before a live workflow.
There is no built-in team URL: a different deployment uses different settings.
A URL prefix such as `https://example.test/api/` is supported.

Remote URLs must use HTTPS. HTTP is allowed for loopback controlled services.
Embedded URL credentials, queries, fragments, and invalid timeout settings are
rejected with a sanitized shared `service_not_configured` error. Environment
proxy/netrc settings and redirects are not used. No outbound authentication is
assumed; if Team 4 requires caller authentication, implement and test its agreed
scheme with credentials supplied externally before using that deployment.

Member 1 can inject the dependency with:

```python
from typing import Annotated

from fastapi import Depends
from issue_tracker_contract import IssueProvider

from app.issue_tracker_dependencies import get_issue_provider

IssueDependency = Annotated[IssueProvider, Depends(get_issue_provider)]
```

The factory owns the client lifecycle. Direct users constructing
`HttpIssueProvider(client)` own and close that client themselves. The factory
reads configuration only when invoked, so Calendar startup does not require
issue settings. Tests can override `get_issue_provider` through ordinary FastAPI
dependency overrides and restore the previous overrides afterward.

| Shared call | Remote request | Result |
| --- | --- | --- |
| `create_issue(title)` | `POST /issues`, JSON `{"title": "..."}` | 201, shared `Issue` |
| `get_issue(id)` | `GET /issues/{encoded_id}` | 200, shared `Issue` |
| `update_issue(id, changes)` | `PATCH /issues/{encoded_id}`, shared update fields | 200, shared `Issue` |
| `delete_issue(id)` | `DELETE /issues/{encoded_id}` | 204, empty body |

Creation titles are validated with the shared rules before HTTP: 1–256
characters and at least one non-whitespace character. IDs are opaque and encoded
as a path segment; no Trello-specific ID pattern is imposed. Empty IDs, dot
segments, and control characters return `not_found` locally. Remote issue models
are validated strictly; empty IDs and mismatched get/update IDs are rejected.
The returned model provides `id` and `title`, not a guaranteed provider URL.

## Known contract limitation: fresh reads

The tagged Python interface requires `get_issue(id, fresh=True)` to bypass saved
results. Team 4's [HTTP documentation][http-api] states that GET may cache data
for 30 seconds and has no public cache-bypass parameter. Its HTTP GET handler
calls `provider.get_issue(issue_id)` without forwarding a freshness option.

This adapter therefore rejects `fresh=True` before HTTP with shared
`SERVICE_NOT_CONFIGURED`, cause `fresh_read_unsupported`. It does not claim full
behavioral conformance to the shared interface. Normal create/get/update/delete
operations are available; fresh-read support is an explicit open compatibility
item, not established evidence.

Reproduction for the owning team: inspect the tagged interface's `fresh=True`
guarantee and the HTTP GET handler's provider call; an ordinary GET cannot
guarantee observing an external edit within the cache window. Ask Team 4 for a
supported cache-bypass mechanism and add controlled/live checks once available.
No issue or message has been sent by this implementation. Direct Trello
verification is necessary for milestone evidence regardless of API read-back.

## Failures and recovery

The adapter raises **issue-contract** `ServiceError`, which is distinct from
`app.errors.ServiceError` and Calendar's error class. Member 1 must translate it
at the composition boundary into our public error model, identify the failed
step, and preserve write uncertainty. Do not register raw remote exceptions as
public HTTP responses or blindly forward remote error messages.

| Trigger | Shared outcome | State/recovery |
| --- | --- | --- |
| Invalid title/configuration | `invalid_input` / `service_not_configured`; `may_have_applied=False` | No HTTP call; correct input/configuration |
| Recognized remote rejection | Shared code and fixed local message | Handle the code; never retry automatically |
| Lost response, malformed success, or unexpected HTTP result on a write | `provider_error`; `may_have_applied=True` | A write may exist; reconcile directly before retrying |
| Transport/response failure on a read | `provider_error`; `may_have_applied=False` | The read itself changed nothing |
| Remote creation still in progress | `request_in_progress`; write uncertainty retained | Do not initiate another creation |
| Remote delete returns 204 with a body | `provider_error`; `may_have_applied=True` | Verify deletion directly |

Only known error codes with their documented HTTP statuses are preserved.
Unrecognized or inconsistent envelopes become `provider_error`. Remote bodies,
validation details, arbitrary messages, and headers are never copied into the
shared exception. The adapter adds no logs; the composed HTTP request should
produce the existing single sanitized outcome log. `provider_involved=True`
records an attempted remote-service call, not proof that Trello was contacted.

An HTTP failure does not expose the provider's internal `may_have_applied` flag.
The adapter treats remote 5xx writes conservatively as uncertain except for
`service_not_configured`, and also preserves uncertainty for in-progress writes.
Even a connection failure is treated conservatively on writes. There are no
local mirrors, automatic compensating deletes, or workflow-level retry records
in this component. Member 1 must account for these outcomes in recovery design.

## Verification plan and remaining evidence

Controlled tests use `httpx.MockTransport`: no internet, provider credentials,
or existing Trello cards. They cover request shapes, validation, IDs, errors,
write uncertainty, no retries/redirects, dependency substitution, configuration,
client cleanup, and the explicit freshness limitation. These are adapter tests,
not the shared HTTP conformance suite or evidence of live Trello operation.

Local checks on the uncommitted candidate based on HW2 commit `7859542` passed:
frozen dependency sync, Ruff lint/format, strict mypy, and whitespace checks.
The full suite reported 773 passed and 58 opt-in checks skipped, including 80
new offline issue-integration tests. GitHub CI and live verification are separate
pending evidence.

```sh
uv run pytest -v tests/test_issue_tracker_client.py tests/test_issue_tracker_dependencies.py
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -v
git diff --check
```

Before making live writes, arrange a dedicated test list and permission to
create/delete cards, access for direct Trello verification, endpoint availability,
and any caller authentication. Do not write into an unarranged shared list.

Live evidence is **pending**. Record the following when access is available:

1. Our checked commit and Team 4's observed deployed revision/endpoint.
2. A uniquely tagged test title and the create result (201, ID/title).
3. API read-back and direct Trello confirmation of the same ID/title.
4. Cleanup through delete, direct confirmation, and any known leftovers.
5. Sanitized actual results, date, verifier, and evidence links.

A 404 from the API alone does not establish cleanup across cached workers;
direct provider inspection is part of verification. Do not claim an issue was
never created after a timeout unless provider evidence establishes it.

[contract-tag]: https://github.com/Tyler-Arciniaga/OSPSD-Team-4/tree/issue-tracker-contract-v1.0.0/contract
[http-api]: https://github.com/Tyler-Arciniaga/OSPSD-Team-4/blob/f0054d5cc328133a46479c20de77ae029c422e29/docs/api.md#read-freshness-and-caching
