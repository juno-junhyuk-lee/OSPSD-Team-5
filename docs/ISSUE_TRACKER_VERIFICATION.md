# Member 3: live Trello verification

Executed November 15, 2026, starting 20:56:56 UTC (15:56:56 EST), with Codex
assistance after Juno supplied the agreed test-list configuration in ignored
`.env.trello`. This is agent-executed provider verification, not an independent
teammate walkthrough or the deployed composed workflow.

## Provenance

- Branch: `hw3/issue-tracker`.
- Base commit: `fb5dad8385b3438cc1538cc92c19fd322d7e9639`.
- Candidate: uncommitted package migration, dependency factory, tests, lockfile,
  CI script-typing check, documentation, and `scripts/verify_issue_tracker_live.py`.
- Implementation: `team-4-issue-tracker-trello` 1.0.0, tagged commit
  `c88ce2fd287f2524ba09ad5d94faf3983fdac08d`.
- Contract: `issue-tracker-contract` 1.1.0, tagged commit
  `18fb7ae6f9c9cf5dbfed7208114d036a582ba54c`.
- Python 3.14.2, locked dependencies; `ISSUE_TRACKER_IMPLEMENTATION` defaulted
  to `team4_trello`.
- Marker: `team5-hw3-62ea2efa31de41bf9d9dfa50b6a73738`.

The base commit alone contains the old HTTP adapter; it is not the tested source
by itself. The dirty-tree flag and migration scope above identify the candidate.
Later commits publish that migration, not a new live run.

## Results

| Check | Observed result |
| --- | --- |
| Independent Trello list preflight | Matching configured list, not closed |
| Create through our dependency and imported Team 4 package | Success, matching title |
| `get_issue(id, fresh=True)` | Same ID/title |
| Independent HTTP read directly from Trello | Matching ID/title and configured list |
| Delete through imported provider | Success |
| Independent HTTP read after deletion | 404, confirming removal |
| Overall process | Exit 0 |

One test card was created once and deleted once. The script's known-ID cleanup
ran in `finally`; no timeout, uncertain write, or cleanup failure occurred.
It made no assertions about the number or contents of unrelated cards. No other
card was modified or deleted.

[Sanitized JSONL evidence](evidence/HW3_ISSUE_TRACKER_LIVE_2026-11-15.jsonl)
contains provenance, checks, and marker, without credentials, card/list IDs,
headers, or unrelated Trello data.

## Reproduction and limits

This command changes the configured Trello test list:

```sh
uv run --env-file .env.trello python -m scripts.verify_issue_tracker_live --allow-writes
```

Each run generates a fresh marker. Independent read-back uses a separate
`httpx.Client` directly against Trello, rather than calling Team 4's provider
again. No stored/HTTP-cached result is used. This does not establish a human
board inspection; arrange teammate reproduction separately.

The full deployed issue/Calendar/storage workflow, configuration-only storage
swap, secret provisioning in deployment, and all real provider-failure modes
remain separate evidence. Controlled tests cover failure handling offline.
