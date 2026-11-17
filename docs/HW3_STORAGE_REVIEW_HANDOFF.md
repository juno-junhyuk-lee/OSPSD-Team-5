# Storage review and design handoff

Owner: Kristie (Member 4), with Codex assistance. Read-only review on November 16,
2026, at local `904691d`. This update changes documentation only; it does not
submit reviews, update PRs, send messages or record teammate approval.

## Local and remote state

| Item | Observed state | Action |
| --- | --- | --- |
| Local storage branch | `904691d`; upstream packages integrated at `e2616dd`, local live workflow evidence committed | Ready to share for review; HTTP cleanup remains a separate commit |
| [#55](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/55) | Open draft, base `hw3/member1-workflow`, remote head `f7c59d1`; description still HTTP/900 tests | Kristie pushes the intended storage branch after committing, then updates description from the draft below; recheck diff and CI |
| [#53](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/53) | Open draft at `8a92484`, base still `hw3/issue-tracker` | Niriti reconciles merged #52/#57 and targets the intended milestone branch; coordinate overlapping workflow changes |
| [#56](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/56) | Open draft, base `hw3/milestone-1`, head `b844f9b`; storage design still HTTP | Ka Pui updates storage facts and open questions using this handoff |

GitHub #55 review submissions, inline comments and issue comments all returned
empty lists. That does not erase prior team-chat feedback or mean approval.
The first four concerns below come from the prior discussion supplied in this
session, not new GitHub review records. The current #56 comment from Juno asks
for correct Trello status mapping, stable Calendar details and updated storage;
its current design already incorporates the first two.

Merging upstream into our branch does not update #53 or change #55's base.
Keep #55 stacked while #53 is unmerged; after #53 integration, inspect the diff
before retargeting to `hw3/milestone-1`. Local tracking points to the workflow
branch: use an explicit storage-branch push, not an unqualified push. Remote CI
on `f7c59d1` cannot establish checks for the unpushed package implementation.

## Concern-by-concern disposition

| Concern | Current evidence / implementation | Disposition |
| --- | --- | --- |
| Does HTTP count as consuming Team 3? | [Hari's clarification](https://nyu-cwf8604.slack.com/archives/C0C11UFNQSE/p1794828716412749): package dependency is mandatory. Workflow now imports/uses Team 3 at `fde60d4` | Implemented locally; reviewer must see updated #55 head |
| Connection refusal incorrectly treated as uncertain | Package-specific typed cause chain recognizes ConnectTimeout and NewConnectionError; generic connection errors remain uncertain; post-upload read failures preserve resources | Implemented and regression-tested; request Ka Pui's review, not automatic approval |
| Summary ID null despite known destination | Optional `leftovers[].path` carries a known path separately from ID; omitted when unknown | Implemented/tested; no API claim that path proves existence |
| Old #52 integration / rebase needed | Merged milestone upstream into storage at `e2616dd`; Trello package, issue contract 1.1.0 and stable Calendar package coexist with storage | Local integration complete; remote sharing/#53 coordination pending |
| All failures must report the failed step | Semantic workflow validation returns a WorkflowError, but structural request errors still use the generic 400/422 handler; issue dependency configuration still returns generic 503 | Open Niriti follow-up; do not claim #55 fixes all error envelopes |
| Live workflow verification | Real local FastAPI request returned 201; fresh issue read, Calendar read, summary byte comparison and all cleanup absence checks passed | Local real-provider evidence complete; deployed execution is separate |
| Team 1 configuration-only swap | Inspected Team 1 package has namespace/metadata/interface gaps; supported solution still awaited | Open Kristie/Team 1 dependency; no implemented storage selector or verified package swap yet |
| HTTP leftovers in repository | Runtime workflow does not use HTTP storage, but path helper and legacy tests still reference HTTP modules | Separate cleanup commit; retain historical evidence |
| Independent review/provider inspection | No independent human inspection was performed in the recorded runs | Open; do not count programmatic readback as teammate approval |

No new code fix is bundled into this documentation scope. Any additional error
schema work belongs in a coordinated implementation commit with Niriti.

## Changes needed in #56's storage design

1. Replace `HttpDocumentStorage` and the Team 3 hosted-service hop with
   `SummaryStore -> DocumentSummaryStore -> Team 3 DropboxDocumentStorage ->
   DropboxClient -> injected Dropbox SDK -> authorized Team 5 Dropbox account`.
   The implementation/internal interface pin is full commit
   `fde60d4fb648df6defb918ff815fe940c525adc7`; no wrapper release tag yet.
2. Preserve shared contract Git tag `0.3.1` / commit `664afc9`, while distinguishing
   its distribution metadata version `0.2.0`. Normal project frozen sync works;
   the initial standalone pip `--no-sources` workaround is not our setup command.
3. Replace storage endpoint/bearer settings with `STORAGE_ROOT_PATH`,
   `PYTHON_DOTENV_DISABLED=1`, app key/secret and explicit refresh-token configuration
   (environment or absolute token file). Dropbox credentials now belong to Team
   5. Hosted secrets and deployment wiring are pending, not already provisioned.
4. Close the HTTP-allowance question using Hari's answer. Replace the URL-only
   Team 1 swap question with compatible package/factory/selector work; no actual
   package selector exists yet. Keep swap blocked rather than claiming readiness.
5. Describe typed pre-send failure versus uncertain write and failed readback.
   No SDK write retries; definite rejection compensates event then issue;
   uncertain outcomes retain resources and the known path. The current real
   store returns `retryable=false`; align the earlier `retryable=true` example
   or clearly label it hypothetical. Use the [failure policy](HW3_STORAGE_FAILURE_POLICY.md).
6. Add [local composed evidence](WORKFLOW.md#local-real-provider-workflow-evidence)
   and the separate package probe, retaining independent inspection, deployed
   success/failure runs and swap as pending. Programmatic reads are direct
   provider/package checks, not an independent observer's confirmation.
7. Keep #53's structural-validation/issue-configuration envelope gap open.
   Also qualify the blanket claim that missing Google credentials always fail
   before any write: the current Google dependency is lazy and authorization
   can fail during event creation, after which the issue is compensated.

Do not edit Ka Pui's design branch from this storage task. Send these findings
for incorporation and record actual responses/reviews when received.

## Evidence and validation boundaries

The integrated code passed frozen sync, Ruff lint/format, strict mypy and
**948 passed, 58 skipped** at the previous implementation scope. The real
workflow ran at `e2616dd`; evidence was committed at `904691d`. This documentation
review ran no new provider operation and does not claim fresh CI/test results.
The generated PR-description draft is [here](HW3_STORAGE_PR_DESCRIPTION.md).
