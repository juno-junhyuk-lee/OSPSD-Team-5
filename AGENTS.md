# Contributor instructions

## Code and setup

- `app/main.py`: FastAPI scaffold; event lookup and route are pending.
- `app/models.py`: public Event response model.
- `tests/`: HTTP tests to be added by the implementation owner.
- [README.md](README.md): setup, API contract, and testing strategy.
- [Work plan](docs/WORK_PLAN.md): task owners and milestone dates.

Use the README setup and commands. Keep Level 1 to one read-only operation
with local data. Preserve its public contract for Level 2 and translate Google
fields before returning them. Do not commit credentials or add unnecessary layers.
Fast tests must run without internet or Google credentials.

## Working together

Agree on a task's owner, reviewer, expected behavior, and completion criteria
before starting. Work on one implementation task at a time. Report blockers or
urgent tasks to the team and agree on reassignment; leave unfinished work visible.

The owner implements the task, runs checks, and opens a linked PR. Another
teammate reviews the code, contract, tests, dependencies, and docs. The owner
resolves comments and merges after approval and passing checks. Disclose AI
assistance; each student must understand and verify their submitted work.
Discuss contract changes together and update tests and docs with the code.

Run `pytest` and `git diff --check` locally. Tests, linting, and type checking
must also run in CI; configuring those tools and documenting their local
commands remain pending. Do not report missing tests or checks as passing.

## Releases

Use `v0.1.0-alpha.1` for the review prerelease and `v0.1.0-beta.1` for the final
release; increment the suffix for fixes. Explain compatibility and setup changes
in PRs and release notes.

Before each release, name a coordinator and a different teammate as verifier.
The coordinator selects a checked commit and creates an annotated tag. The
verifier follows setup and runs tests and a provider workflow from a fresh
checkout of that tag. Publish a GitHub Release with changes, issue/PR links,
limitations, and matching verification/CI evidence. Use a different coordinator
for the final release. Merged work is only released once publication happens.

Never move published tags. Fix defective releases in a new version and tell
users whether to return to an earlier version or wait, including any external
state that reverting code would not restore. After the review release, record
one observation about the process and any adjustment.

## Comments

Keep comments short and explain only non-obvious behavior. Use direct phrases;
for simple definitions prefer `name = meaning`. Add detail only when requested.
