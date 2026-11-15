# Using Team 5 Calendar from another service

The `team5-calendar` package lets a consumer such as Team 1 import Team 5's
Google implementation into its own API service. It lives in this repository at
`packages/team5-calendar`; a separate implementation repository is unnecessary.
The consumer deploys its combined API through its own pipeline.

## Contract and implementation

| Dependency | Responsibility |
| --- | --- |
| `calendar-contract` v0.1.0-rc.1, commit `1c1cad7a0732ddb242a05400d8833d94e4422424` | Shared models, errors, four-method protocol, conformance suite |
| `team5-calendar` 0.1.0 candidate | Google authorization and Calendar operations, imported as `team5_calendar` |

The implementation uses the shared types directly. It does not modify the
agreement among Teams 2, 5, and 7 or put Google-specific code in the contract
repository. Team 5's existing `get_calendar_service` FastAPI dependency remains
the internal handoff for the composed workflow. External consumers use the
ordinary Python factory below instead of importing Team 5's `app` package.

The [package README](../packages/team5-calendar/README.md) contains the proposed
Git installation and OAuth commands. This candidate is unpublished; the
`COMMIT_TO_BE_REPLACED` install placeholder must be replaced with a reviewed
commit or new immutable implementation tag before it is sent as an install
instruction. Existing published tags, including `v0.1.0-beta.6`, are not moved.
Implementation versioning is separate from the shared contract version.

Python 3.14 or newer is required, including in the consumer's dependency
metadata. The implementation explicitly declares the tagged contract source;
Team 5's `[tool.uv.sources]` settings are not automatically inherited by another
project. If a consumer also declares the contract directly, both declarations
must resolve to the same source/revision.

## Google setup and credential ownership

Use a dedicated test Google account whose primary calendar may be changed.
Create or use an agreed Google Cloud project with Calendar API enabled and a
Desktop OAuth client. For an External app in Testing, register the test account
as an allowed test user. Store the downloaded client JSON outside the repository
and run the package's explicit authorization helper:

```sh
python -m team5_calendar.authorize \
  --client-secrets /absolute/private/credentials.json \
  --token-file /absolute/private/token.json
```

Sign in with the consumer's test account. The client JSON identifies the OAuth
application; the resulting token authorizes the selected Google account. A
Team 5 API bearer token serves a different purpose and is not used here.
Testing-mode grants can expire and require reauthorization. Provider methods
never open a browser or silently select Team 5's account.

Supply the token path explicitly when constructing the service. In deployment,
mount that file from the consumer's protected secret configuration. Do not place
credentials in package source, wheels, images, logs, PRs, or verification output.
Runtime token refresh remains in memory, so installed directories can be
read-only. Missing, expired, revoked, or insufficient authorization produces a
shared operation error; repair authorization before retrying work.

## Consumer example

The factory is independent of FastAPI. A consumer may construct it in its own
dependency/configuration module and inject the returned shared protocol into
its workflow. Business code then depends on the four methods below, so choosing
another conforming implementation belongs in configuration/factory selection.

```python
from uuid import uuid4

from calendar_contract import CalendarService, CreateEvent, ReplaceEvent
from team5_calendar import create_calendar_service

service: CalendarService = create_calendar_service(
    token_file="/absolute/private/token.json"
)
marker = f"team1-calendar-check-{uuid4().hex}"
created = service.create(
    CreateEvent(
        title=marker,
        start="2030-01-07T15:00:00Z",
        end="2030-01-07T15:30:00Z",
    )
)
try:
    observed = service.get(created.id)
    assert observed.id == created.id and observed.title == marker
    replacement = service.replace(
        created.id,
        ReplaceEvent(
            title=f"{marker} updated",
            start="2030-01-07T16:00:00Z",
            end="2030-01-07T16:30:00Z",
        ),
    )
    assert replacement.id == created.id
finally:
    service.delete(created.id)
```

The example creates and deletes real test data. Inspect the same event directly
in Google before cleanup when collecting milestone evidence. Record the tested
implementation commit, contract revision, marker, result, and cleanup outcome.
After successful deletion, `get` and repeated `delete` raise shared
`CalendarError` with `ErrorCode.NOT_FOUND`.

Inputs use `title`, `start`, and `end`; `Event` adds `id`. Times are RFC 3339
strings with explicit offsets and end after start. Compare timestamps by instant,
since Google may normalize offsets; whole seconds are the portable choice.
Listing, all-day events, attendees, and provider URLs are not promised by the
shared core.

## Errors, retries, and cleanup

Operation failures raise `calendar_contract.CalendarError`. Inspect `code` and
`retryable`; translate those into your API's public error model at your boundary.
Invalid shared request construction raises Pydantic `ValidationError` before
the operation. Google SDK errors and credentials stay inside the implementation.

An uncertain create/replace raises `PROVIDER_ERROR` with `retryable=False`.
Never automatically repeat it: Google may already have accepted the write.
If a create returns no ID, use the unique marker to inspect the test calendar
before another attempt. A known event ID permits targeted read/cleanup. Report
cleanup errors and any unresolved external state rather than claiming success.
Stopping a workflow or restoring code does not undo provider changes.

## Verify installation outside this repository

Build a wheel and install it into a fresh consumer environment. Run these
commands from the Team 5 repository root, then leave that checkout:

```sh
uv build --wheel packages/team5-calendar --out-dir /tmp/team5-calendar-dist
TEAM5_CONSUMER=$(mktemp -d)
uv venv --python 3.14 "$TEAM5_CONSUMER/.venv"
uv pip install --python "$TEAM5_CONSUMER/.venv/bin/python" \
  /tmp/team5-calendar-dist/team5_calendar-0.1.0-py3-none-any.whl
cd "$TEAM5_CONSUMER"
mkdir app
touch app/__init__.py
"$TEAM5_CONSUMER/.venv/bin/python" -c \
  'from calendar_contract import CalendarService; from team5_calendar import create_calendar_service; print("imports passed")'
```

The consumer deliberately has its own `app` package. Installation and imports
must work without adding the Team 5 checkout to `PYTHONPATH` or copying its
`app/` directory. The external token example above should then work in this
environment. A successful import alone does not establish real Google access.

Run the shared `CalendarServiceConformance` suite against the implementation
using isolated controlled providers, with separate real-provider checks. Keep
failure-injection hooks in test fixtures rather than adding methods to the
production protocol. Passing Team 5's HTTP tests alone does not establish that
another project's installed package works.

## Release and handoff status

The [November 15 verification record](CALENDAR_PACKAGE_VERIFICATION.md) documents
the built wheel, clean consumer installation, pinned Git fixture, unchanged
contract checks, and real Google create/read/replace/delete/cleanup. To repeat the
automated install boundary check:

```sh
uv build --wheel packages/team5-calendar --out-dir /tmp/team5-calendar-dist
uv run python scripts/check_calendar_wheel.py \
  /tmp/team5-calendar-dist/team5_calendar-0.1.0-py3-none-any.whl
```

This document describes the package candidate under review. Record actual
build, clean-consumer, conformance, and Google results in the implementation
verification record before describing them as complete. A new immutable tag and
release require review and separate authorization; no published install version
is claimed here.

The final handoff to Team 1 consists of the fixed install revision, exact import
and factory example, supported Python version, OAuth/token setup, shared error
semantics, and observed create/read/cleanup evidence. Team 1 still needs to run
and verify its own complete three-vertical workflow after integration.
