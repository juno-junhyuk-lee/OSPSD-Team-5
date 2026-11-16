# Calendar package consumer verification

Owner: Jim Lo, executed with Codex assistance on November 15, 2026.
This is an agent-executed consumer simulation with Team 5's authorized Google
test account, not an independent Team 1 or teammate run.

## Candidate and installation

- Branch: `hw3/calendar-package`, based on `df2145d` (includes merged #54/#52).
- Tested implementation commit: `b223c6b03310f98dce4be1da8ed7cd37773ca520`.
- Distribution/import: `team5-calendar` 0.1.0 / `team5_calendar`.
- Shared contract remains `v0.1.0-rc.1`, resolved commit
  `1c1cad7a0732ddb242a05400d8833d94e4422424`.
- Python 3.14.8. Root uses its frozen dependency lock; independent installation
  resolves the package's declared runtime dependencies without that root lock.

`uv build packages/team5-calendar` produced both sdist and wheel successfully.
The wheel SHA-256 was
`0b2f37649fc972ca2816f4528716b3ca6d46fb42d5928ccad6a6218347d5b1c6`.
Package code was unchanged throughout the checks. Later verification/docs commits
do not replace the tested implementation revision.

The maintained `scripts/check_calendar_wheel.py` installed that wheel and all
declared dependencies in a fresh temporary environment outside the repository.
It passed:

- The consumer's own `app` package remained importable and was not shadowed.
- `team5_calendar` and `calendar_contract` loaded from the consumer's installed
  environment, with no Team 5 checkout on its Python search path.
- No Team 5 application, FastAPI, or telemetry SDK was imported.
- The factory constructed without credentials; all four operations rejected
  missing/malformed authorization with shared non-retryable errors (eight checks),
  with socket connections blocked during these checks.
- The wheel contains only the namespaced package, typing marker, and metadata;
  no root app, infrastructure, or credentials were included.

Pinned Git/subdirectory installation also passed using a temporary Git fixture
containing exactly the package exported from `b223c6b`. Fixture commit:
`5d4b2925e8c5ccc4f722f6c134e64085766adf7f`. The initial transfer directly from
the linked worktree stalled and was stopped; it is not counted as a passing
install. The temporary fixture avoids that local transfer issue while exercising
the same package layout and dependency metadata. At that checkpoint no remote push had occurred. The subsequent GitHub install
check is recorded separately below.

The independent consumer resolved Pydantic 2.14.3 and Google API Core 2.44.0;
the application lock retains its previously pinned versions. Both environments
used the same tagged Calendar contract and explicit package dependencies.

## Real Google through the installed consumer package

Run began November 15 at 22:55:28 UTC (17:55:28 EST).
Marker: `team5-package-ae57006e1cbd`.
The independent consumer retained its own `app` package and called the installed
public factory with an absolute external OAuth token path. It did not run the
Team 5 HTTP server, use a Team 5 bearer, or read credentials from site-packages.

| Check | Observed result |
| --- | --- |
| Independent Google marker search before writes | No active matches |
| Factory create and get | Success, same ID and values |
| Independent Google SDK read | ID, title, start, and end match |
| Factory replace and get | Same ID, updated title and time instants |
| Factory delete | Success |
| Read and repeated delete after cleanup | Shared `NOT_FOUND` |
| Independent Google search after cleanup | **0 active matching events** |
| External OAuth token bytes after run | Unchanged |

All ten recorded Boolean checks passed; process exit was 0. No uncertain write
or cleanup failure occurred. No unrelated data was changed. Cancelled events may
remain in provider history; this verifies absence of active matching events.

[Sanitized live evidence](evidence/CALENDAR_PACKAGE_LIVE_2026-11-15.jsonl)
records the package revision, fixture revision, script checksum, marker, and
checks without credentials, event IDs, account details, or private event data.
The runner was then-uncommitted `scripts/verify_calendar_package_live.py`, whose
SHA-256 is recorded in the evidence. Controlled tests separately check its
failure and cleanup paths.

Reproduce from an external environment with the installed package:

```sh
python /path/to/Team5/scripts/verify_calendar_package_live.py \
  --token-file /absolute/private/token.json --allow-writes
```

This runner imports only the installed package/shared contract, standard library,
and Google SDK. It needs no Team 5 `app` imports. The optional setup command
`python -m team5_calendar.authorize` is tested with a controlled browser flow;
the real run reused an existing grant rather than initiating a new OAuth login.

## Automated checks and practical limits

Final frozen-environment checks passed: **772 tests passed, 58 opt-in checks
skipped**, Ruff lint/format, strict mypy (79 source files plus four scripts),
and `git diff --check`. The existing Starlette TestClient warning remains. Package checks
include the unchanged shared conformance suite through the public factory,
concurrent token isolation, external path precedence over hosted settings,
in-memory refresh, malformed token handling, uncertain writes without retry,
and the explicit OAuth CLI. Existing HTTP/provider/tracing checks also pass.

Dockerfile and build context now include the local package before `uv sync`.
The path dependency is non-editable so the installed module survives the runtime
image's separate filesystem stage. An actual Docker build could not run because
the local Docker daemon was not running; deployment/image execution is not
claimed. The CI wheel check was added but has not run remotely before push.

This does not establish the complete deployed three-vertical workflow, Team 1's
own deployment/account setup, or independent teammate verification. New tags,
release publication and Team 1 reproduction remain after review.

## Post-push GitHub installation

After the user approved pushing the candidate, an independent consumer installed
`team5-calendar` directly from GitHub at pinned commit
`b1d6e7fa2bea4cfbab16d6e5a195a2a445885ba2`, using
`#subdirectory=packages/team5-calendar`. uv resolved and built the package with
its declared runtime dependencies. Installed distribution metadata confirmed
the exact Git commit. The consumer retained its own `app`, imported the package
from its virtual environment, loaded no Team 5 application or FastAPI, and
received the expected shared error for absent authorization. All checks passed.

[Sanitized GitHub-install evidence](evidence/CALENDAR_PACKAGE_GITHUB_INSTALL_2026-11-15.json)
is separate from the prior live Google run; no new provider writes were needed
for this installation check. Subsequent documentation changes do not relabel
that tested commit or the original wheel/live evidence.

## November 16: stable-contract follow-up (uncommitted)

Juno's follow-up candidate on `hw3/calendar-package`, based on
`df6bb55cc4fa577a880add58cc9d7d4d809119cd`, repins both active dependency
declarations to stable `calendar-contract` tag `v0.1.0`, commit
`db73e6261a93b0c3cc6aa0a48c4687f742aacc9b`. The package remains version 0.1.0;
its factory and Google operation behavior are unchanged. Historical sections
above describe their original `rc.1` runs and are not relabeled.

Comparison of the two contract tags found no changes to Event, request models,
timestamp/title validation, CalendarService, or CalendarError/ErrorCode. The
stable release adds HTTP conformance support and cleans up an unintended root
export. The active provenance check now rejects the old commit even though both
contract distributions report version 0.1.0; a regression case covers this.

With Python 3.14.2, frozen sync and forced non-editable package reinstallation,
the final suite reported **773 passed, 58 skipped**. Ruff lint/format, strict
application/package/script mypy, and whitespace checks passed. Both sdist and
wheel built successfully. The existing TestClient warning remains.

Independent installations used the new wheel and an explicit direct dependency
on stable `calendar-contract`, without an override:

- **uv:** a fresh consumer project ran `uv lock` and `uv sync --frozen`, then
  verified installed module locations, its own `app` namespace, framework
  independence, exact stable contract commit, and eight shared authorization
  failures with provider network connections blocked.
- **pip:** a separate seeded environment installed the wheel and explicit stable
  contract together and passed the same consumer checks.

[Sanitized consumer evidence](evidence/CALENDAR_PACKAGE_STABLE_CONSUMER_2026-11-16.json)
records the uncommitted candidate's base, source hashes, wheel checksum, actual
contract commit, and both installers' results. No Google writes or OAuth setup
were performed for this follow-up. The prior live Google run remains evidence
for its original `rc.1` candidate, not a new stable-contract provider run.

The stable candidate is not committed/pushed, has no new GitHub CI result, and
has no published immutable implementation tag. Remote installation from the
old pinned SHA still installs the older `rc.1` metadata. Final reviewed-commit
checks, independent verifier reproduction, actual-tag installation, and GitHub
Release publication remain on the [release checklist](CALENDAR_PACKAGE_RELEASE.md).
