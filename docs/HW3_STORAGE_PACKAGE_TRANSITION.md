# Storage package transition plan

Owner: Kristie (Member 4). November 16, 2026. Baseline: `f7c59d1`.
Codex assisted with inspection and this plan. This commit scope is documentation
only; implementation and verification items below remain pending.

## Decision and confirmed inputs

- Hari's help-channel clarification, supplied by Kristie: adding the other
  team's package as a dependency is a hard requirement. The planned implementation
  imports and uses that package for summary operations; merely installing it
  while keeping HTTP storage as the workflow path is not the completion target.
- John approved Team 3 commit
  `fde60d4fb648df6defb918ff815fe940c525adc7` and the explicit dependencies with
  `--no-sources` approach. No release tag contains the wrapper yet. Team 3 tests
  Python 3.12; our isolated Python 3.14 install/import probe is narrower evidence.
- Juno approved reuse of the existing Team5-Review scoped App Folder app.
  Its supplied permissions and callback match the package README. This approval
  does not establish OAuth completion, token validity or access to a particular
  Dropbox account. Confirm the intended account during authorization.
- Package operations use the authorized Team 5 account, not Team 3's endpoint
  or Dropbox folder. Use a dedicated HW3 folder within our app folder. Arrange
  independent inspection with an authorized Team 5 teammate; John need not watch
  Team 3's account for this run. Never put credentials or token contents in git.
- Team 1 has not replied with a supported package solution. This blocks the
  alternative-provider swap, not Team 3 implementation.

## Branch and PR snapshot

Read-only GitHub inspection on November 16:

| PR | Observed state | Consequence |
| --- | --- | --- |
| [#52](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/52) | Merged into `hw3/milestone-1`; merge `df2145d` | Issue package changes must eventually be integrated; do not reimplement them in storage work |
| [#53](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/53) | Open draft; head `hw3/member1-workflow` at `8a92484`; base still `hw3/issue-tracker` | Niriti owns updating its upstream relationship and workflow fixes |
| [#55](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/55) | Open draft; head `hw3/member4-storage` at `f7c59d1`; base `hw3/member1-workflow` | Continue small commits on the existing branch and PR |

No branch switch or immediate rebase is required for this documentation task.
Keep #55's base while #53 remains its unmerged prerequisite. When Niriti updates
the workflow branch, inspect changes before syncing. Once #53 merges, inspect
the merge method and diff before retargeting #55 to `hw3/milestone-1` and deciding
whether a rebase is needed. Kristie executes all branch/rebase/add/commit/push
commands; the assistant supplies commands only when necessary. Local tracking
currently points to `origin/hw3/member1-workflow`; this does not determine #55's
head branch and is not a reason to push to the workflow branch.

## Proposed change boundaries

These are coordination proposals to communicate, not acknowledgements from
Niriti or Ka Pui. Request review of the boundaries before overlapping edits.

| Area | Proposed owner and boundary |
| --- | --- |
| `pyproject.toml`, `uv.lock` | Kristie adds only storage package requirements; coordinate with issue/Calendar dependency owners before concurrent lockfile edits |
| Storage package construction/configuration and tests | Kristie owns provider creation, credential-location handling and sanitized pre-write configuration errors |
| `app/workflow_dependencies.py` | Kristie changes `get_summary_store` and storage imports; Niriti retains issue/Calendar wiring and overall dependency integration |
| `app/summary_storage.py`, storage tests | Kristie retains `SummaryStore` and shared `DocumentStorage` boundary, UTF-8 readback and known-path propagation; implements package-aware failure certainty |
| `app/workflow.py`, `tests/test_workflow.py` | Niriti owns request validation and orchestration; Kristie proposes only storage-related error/cleanup changes and regression tests, coordinating overlapping edits first |
| `app/storage_http.py`, `app/storage_client.py`, `app/storage_settings.py` | Kristie audits references and extracts reusable path validation before removing obsolete HTTP implementation; do not delete unrelated `httpx` dependencies |
| `scripts/verify_storage_live.py`, its tests and evidence | Kristie converts to package-backed checks with explicit execution and cleanup; keeps previous HTTP evidence historical |
| Storage docs, `docs/WORKFLOW.md` storage sections | Kristie updates implementation status, setup and handoff |
| Design, cross-vertical test plan, submission | Ka Pui coordinates; Kristie provides storage facts, blockers and evidence for review |

Preserve the public workflow schema, optional known summary path, no-write-retry
policy and newest-first compensation. Do not silently redesign issue/Calendar
contracts. Constructor/configuration failure must stop before issue/event writes;
uncertain creation or failed readback after creation must not be treated as a
definitely absent summary. See the [failure policy](HW3_STORAGE_FAILURE_POLICY.md).

## Small-commit sequence

1. **This scope: transition documentation and coordination draft.** Record
   decisions, branch state and proposed ownership. No code changes.
2. **Dependencies.** Pin Team 3 implementation/internal interface and shared
   contract; produce a lockfile and verify normal `uv sync --frozen` installation
   and imports with the complete Python 3.14 application environment. An ad-hoc
   pip success alone is not sufficient. Investigate source overrides within this
   scope; do not globally bypass dependency controls as an unexplained fix.
3. **Construction/configuration.** Build the package provider, establish explicit
   credential/token-file handling and map initialization errors before writes;
   test without real credentials or provider calls.
4. **Workflow wiring.** Inject the imported implementation into
   `DocumentSummaryStore`; verify UTF-8 readback and response behavior. Audit and
   remove obsolete HTTP code/references in a separate cleanup commit if needed.
5. **Failure policy implementation.** Test definite rejection, uncertain write,
   post-create readback failure and compensation/preservation. Reassess Ka Pui's
   connection-error concern at the package boundary; do not mechanically port
   HTTP exception classification.
6. **Authentication and live probe tooling.** App setup can proceed now. After
   installation, Kristie authorizes the intended account using the reused app;
   adapt the opt-in probe and offline tests, document isolated paths and cleanup.
7. **Live evidence.** Run package CRUD and then the composed workflow when all
   integrations are ready; record exact revisions, readback, independent account
   inspection and cleanup. Never label authentication-only checks as CRUD.
8. **Integration handoff.** Reconcile upstream changes, run required checks,
   update PR/design status and retain Team 1 swap as pending until verified.

## Review and completion checklist

- [ ] Real workflow summary operations call the imported Team 3 implementation.
- [ ] Frozen install, lint/format, strict typing and relevant offline/full tests
  pass for the integrated dependency set; record actual results.
- [ ] Python 3.14 real package execution is checked, or incompatibility is
  resolved with the team before changing the repository Python requirement.
- [ ] Known summary path behavior survives the transition.
- [ ] Package configuration failure and operation uncertainty satisfy cleanup
  rules; Ka Pui's failure-classification concern has explicit test evidence.
- [ ] Latest #52/#53 changes and stacked-PR relationship are reconciled.
- [ ] Team 5 account authorization, real package CRUD and full-workflow evidence
  are recorded separately from historical HTTP checks.
- [ ] Team 1 supplies a compatible package; configuration-only swap is verified.
- [ ] Ka Pui reviews the storage handoff and updates the cross-vertical design.

The listed review concerns come from prior team discussion. This plan is not a
claim that every review comment is resolved; reconcile the latest review items
again before marking #55 ready. Detailed installation findings and pinned source
links remain in [package research](HW3_STORAGE_PACKAGE_RESEARCH.md).
