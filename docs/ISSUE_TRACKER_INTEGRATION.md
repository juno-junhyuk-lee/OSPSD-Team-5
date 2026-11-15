# HW3 Member 3: Team 4 Trello integration

## Architecture and ownership

Following Tyler's November 15 clarification of the TA's integration expectation,
our service imports Team 4's implementation package and uses our own Trello test
account/list. It no longer calls Team 4's hosted API. Member 3 owns this dependency,
configuration, tests, and issue verification. Member 1 owns orchestration,
Markdown, public error translation, compensation, and deployment. Member 5 owns
the combined design and independent review; any free teammate may review the PR.

```text
Our composed workflow
  -> issue_tracker_contract.IssueProvider
  -> team_4_issue_tracker_trello.TrelloIssueProvider (Team 4's package)
  -> Trello using Team 5's credentials and test list
```

The previous HTTP adapter and endpoint configuration are superseded. This
component has no public route of its own and does not establish the complete
deployed issue/Calendar/storage workflow.

## Tagged dependencies

| Package | Revision | Resolved commit |
| --- | --- | --- |
| `team-4-issue-tracker-trello` 1.0.0 | `team-4-issue-tracker-trello-v1.0.0` | `c88ce2fd287f2524ba09ad5d94faf3983fdac08d` |
| `issue-tracker-contract` 1.1.0 | `issue-tracker-contract-v1.1.0` | `18fb7ae6f9c9cf5dbfed7208114d036a582ba54c` |

Both come from [Team 4's repository][team4]. `pyproject.toml` uses `rev` with
the published tag names, as Team 4 documents, to match the implementation's
direct contract dependency. `uv.lock` records their commits. Python 3.14 remains
our application requirement. Install with `uv sync --frozen`.

The implementation depends on the contract and standard-library HTTP access;
it brings no FastAPI app, Google SDK, or automatic telemetry integration.

## Configuration

| Variable | Meaning |
| --- | --- |
| `ISSUE_TRACKER_IMPLEMENTATION` | `team4_trello` (default and only supported choice) |
| `TRELLO_API_KEY` | Our test-account app's API key |
| `TRELLO_TOKEN` | Our test-account read/write token |
| `TRELLO_LIST_ID` | Our test list's full 24-character lowercase hexadecimal ID |

Keep local values in ignored `.env.trello`. The factory reads the process
environment; it does not load files automatically. Load the file explicitly
with `uv run --env-file .env.trello ...`. Never commit it. Hosted deployment
must supply the same settings through secrets, owned by Member 1; no credentials
are included in images, documentation, or evidence. Use the [package setup
instructions][package] for Trello app/token setup.

`get_issue_provider` retains the shared dependency entry point Member 1 already
uses. Before yielding an imported provider, it validates required configuration
without contacting Trello. Missing/malformed settings raise shared
`SERVICE_NOT_CONFIGURED`, `may_have_applied=False`. This prevents obvious
configuration failures after workflow writes begin. Expired/rejected tokens,
an inaccessible list, and remote outages can still fail during operations.
Calendar-only startup remains independent of these settings.

The provider reads environment variables on each operation, opens/closes its own
connections, and has a no-op `close()`. The factory calls `close()` on normal or
exceptional dependency exit. Do not change credentials during a workflow. The
provider's fixed timeout is controlled by its package, not our former HTTP
timeout setting.

## Shared interface and Member 1 handoff

```python
from typing import Annotated

from fastapi import Depends
from issue_tracker_contract import IssueProvider

from app.issue_tracker_dependencies import get_issue_provider

IssueDependency = Annotated[IssueProvider, Depends(get_issue_provider)]
```

| Method | Result |
| --- | --- |
| `create_issue(title)` | `Issue(id, title)` |
| `get_issue(id, fresh=False)` | `Issue(id, title)` |
| `update_issue(id, IssueUpdate(...))` | Updated `Issue` |
| `delete_issue(id)` | None, or shared `NOT_FOUND` if absent |
| `list_issues(limit=...)` | At most `limit` issues, newest first |

`fresh=True` now works: the imported provider has no cache and reads Trello on
each call. The former hosted HTTP API's lack of cache bypass no longer limits
this path. Listing comes from Team 4's implementation; the scheduled-issue
workflow does not need to add a listing step. Update controlled providers in
workflow tests to satisfy the 1.1.0 interface where required.

Validate user requests with shared `IssueCreate`/`IssueUpdate` before writes.
The provider assumes its caller validated the title and listing limit; do not
rely on it to enforce HTTP request validation. Issue titles must contain a
non-space character and be at most 256 characters. The result does not guarantee
a clickable Trello URL. Provider-specific ID validation stays in their package.

Member 1 must catch **issue-contract** `ServiceError`, distinct from our local
application error class, and translate it into our public error shape with the
failed workflow step and any remaining resources. The package preserves
`may_have_applied`: do not discard that flag or equate a timeout with no card.

## Failure and recovery decisions

**Reuse the implementation directly.** This satisfies the clarified composition
approach and avoids dependence on another team's hosting/cache behavior. The
tradeoff is owning Trello credentials and upgrading our contract to 1.1.0. The
HTTP adapter is removed to avoid maintaining two competing milestone paths.

**Validate settings at dependency resolution.** Package construction is lazy;
our preflight catches missing settings before Member 1 starts writing. It does
not prove remote authorization. A provider health check would add latency and
still could not guarantee the next write; operation errors remain necessary.

**Keep write uncertainty and avoid automatic retries.** The imported provider
attempts creation once. Explicit Trello rejection and provably unsent connections
can report `may_have_applied=False`; lost responses and timeouts can report True.
Later-step compensation/reconciliation is Member 1's responsibility. Never retry
the entire workflow solely because one provider says a single operation is safe.

Team 4's tagged-creation helpers are extensions, not our workflow's current
idempotency policy. They are not enabled here. Optional tracing is also left
disabled; no automatic exception/event/body capture is introduced.

## Controlled and live verification

Offline tests inject controlled responses at Team 4's transport while retaining
the actual imported implementation and our normal dependency. They cover CRUD,
external-change visibility on fresh reads, listing, configuration preflight,
errors, write certainty, no creation retry, cleanup, and dependency substitution.
Verification-script tests cover success, read failure, unknown creation,
cleanup failure, wrong-list preflight, and explicit write opt-in.

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy scripts/verify_issue_tracker_live.py
uv run pytest -v
git diff --check
```

The live script creates and deletes a real card; only run it against the agreed
test list:

```sh
uv run --env-file .env.trello python -m scripts.verify_issue_tracker_live --allow-writes
```

It preflights the list through a separate Trello HTTP client, creates one uniquely
marked `team5-hw3-...` card through our dependency, fresh-reads through Team 4's
provider, independently checks ID/title/list in Trello, and attempts known-ID
cleanup in `finally`. It independently verifies deletion with a direct 404.
It does not assert on list counts or delete unrelated cards. No automatic
creation or deletion retry occurs. After an uncertain creation without an ID,
it reports the unique marker for manual inspection instead of creating again
or claiming cleanup. Output excludes tokens, headers, IDs, and unrelated records.

Record the source revision, dirty-tree provenance, package commits, timestamps,
marker, actual checks, and cleanup. An independent API read is separate from an
independent teammate walkthrough. Neither establishes the deployed composed
workflow, storage swap, or all real-provider failure modes.

Local checks passed: frozen sync, Ruff lint/format, strict application and script
mypy, and whitespace checks. The full suite reported 718 passed and 58 opt-in
checks skipped, including 25 package-integration and verification-script cases.
The smaller total replaces the superseded HTTP adapter's 80 tests with tests
for the imported implementation. The existing TestClient warning remains.

The [November 15 live record](ISSUE_TRACKER_VERIFICATION.md) reports successful
creation, fresh read, independent Trello read-back, and confirmed cleanup. This
migration still needs renewed teammate review and integration into Member 5's
design. These results precede its commit/publication; GitHub CI is separate.

[team4]: https://github.com/Tyler-Arciniaga/OSPSD-Team-4
[package]: https://github.com/Tyler-Arciniaga/OSPSD-Team-4/tree/team-4-issue-tracker-trello-v1.0.0/team-4-trello-impl
