# Draft: team5-calendar 0.1.0 release

Status: release preparation only. No implementation tag or GitHub Release has
been created. The stable-contract follow-up is committed and pushed at
`d19165f9b5e17ed5b63f1d21328513d61334da46`, under review in
[PR #57](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/57). The
[package README](../packages/team5-calendar/README.md) provides its pinned GitHub
installation command; that review candidate is available before release.

## Changes for consumers

- Install Team 5's Google implementation in another API service as
  `team5_calendar`, without importing or shadowing a consumer's `app` package.
- Construct `create_calendar_service(token_file=...)` with the consumer's own
  external OAuth grant; runtime refresh stays in memory.
- Use stable `calendar-contract` tag `v0.1.0`, commit
  `db73e6261a93b0c3cc6aa0a48c4687f742aacc9b`. Consumers using the matching
  revision can drop their `rc.1` override after upgrading this implementation.
- Preserve `title/start/end`, the shared CRUD protocol/errors, and non-retryable
  uncertain writes. Python 3.14 or newer is required.

## Proposed published install

Use only after the tag exists:

```sh
pip install "team5-calendar @ git+https://github.com/juno-junhyuk-lee/OSPSD-Team-5.git@team5-calendar-v0.1.0#subdirectory=packages/team5-calendar"
```

Use [the package guide](CALENDAR_PACKAGE.md) for matching uv source configuration,
Google setup, shared errors, and the [verification record](CALENDAR_PACKAGE_VERIFICATION.md).

## Publication checklist

- Choose the final reviewed commit after the stable-contract follow-up is approved.
- Name a coordinator and a different teammate verifier under the repo release rules.
- Run the required checks, build artifacts, and fresh uv/pip consumer installation
  from the selected revision; associate matching CI/evidence links with it.
- Have the verifier reproduce setup and a provider workflow from the selected
  release candidate with direct Google checks and cleanup.
- Create a new annotated `team5-calendar-v0.1.0` tag at that checked commit.
- Verify installation from that actual GitHub tag, then publish a GitHub Release
  with PR #57, compatibility/setup, limitations, and matching verification evidence.
- Give Teams 1 and 4 the immutable install command and request their reproduction.

Never move the published tag. Corrections require a new version. Installing or
reverting code does not undo Google Calendar writes. Docker image execution and
the complete deployed three-vertical workflow are separate verification work.
The prior live Google evidence used `rc.1`; do not present it as a new stable-tag run.

AI assistance: Codex assisted with preparation and checks. Students retain
responsibility for review, understanding, and verification.
