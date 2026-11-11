# Level 3 independent walkthrough and Level 4 handoff

Owner: Jim Lo. Independent verifier and Level 4 recipient: Ka Pui Cheung.
Ka Pui completed the independent walkthrough and approved `325515a` in
[PR #49](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/49#pullrequestreview-5816656698) on November 7, 2026 (America/New_York).
The reviewed Level 3 merge and later Level 4 merge have passed deployment;
fresh merged-revision logs/traces are linked in the follow-up below.

## Independent walkthrough

Use an account with viewing access to Monitoring dashboards, Logging and Trace
in `ospsd-team5`. These historical observations require no deployment, API
bearer, Calendar OAuth files or new Calendar writes. If access or a link fails,
record it in the worksheet and ask the project owner to resolve viewing access.

Open the [dashboard](https://console.cloud.google.com/monitoring/dashboards/custom/c25e66c8-e3e3-44bc-af2b-6707ca37a175?project=ospsd-team5).
Select **November 7, 2026, 21:55–22:01 EST** (November 8, 02:55–03:01 UTC).
Inspect the `create` panels for the three requests below, then compare the
`get`, `replace` and `delete` panels from the same workflow. Use `verify` and
release `900c32858390d6f8c5b49b7ff9efc5bcf381f161` for these historical series.
That release label identifies the candidate's parent; the
[verification record](OBSERVABILITY_VERIFICATION.md#candidate-and-scope) pins the
actual candidate source fingerprint, image and revisions. It is not a claim
that the later commit was deployed.

| Request | UTC time | Outcome log | Trace |
| --- | --- | --- | --- |
| A | 02:59:38 | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Fb49454506862e151bc19e7e7866ba2e6%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=b49454506862e151bc19e7e7866ba2e6;spanId=8fc4a61494326f02?project=ospsd-team5) |
| B | 02:59:41 | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Ff2a765aeb27c51c738b8a54847950029%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=f2a765aeb27c51c738b8a54847950029;spanId=b7e0c1cb2cdfcc53?project=ospsd-team5) |
| C | 02:57:16 | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Facbf0393a219d301c633b49216030b27%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=acbf0393a219d301c633b49216030b27;spanId=66e24f876780b2ae?project=ospsd-team5) |

Use only the dashboard and linked logs/traces to explain each request, without
the implementation or an explanation from its author. In Logs Explorer, set the
same historical time window. A dashboard point aggregates requests; match its
time, operation, release and outcome to the log, then use the exact trace ID.
An aggregate point is not a unique request identifier.

For each request, explain the operation and result, the serving release and
revision, whether the cause belongs to the caller/service/provider, and where
time was spent. Identify any Google child spans, or explain their absence.
Confirm the log and trace IDs agree, and inspect the exported fields for
sensitive content. The SERVER span's remaining time also includes uninstrumented
work; it must not be described as CPU time.

Current-time gaps are expected because verify was restored after testing. A
missing chart is not proof of zero errors or good health. Record inaccessible
or expired observations as incomplete; a fresh bounded verify run would then
need coordination. Do not repeat the provider-failure injection just to read
existing evidence.

### Verifier worksheet

These observations summarize [Ka Pui's review](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/49#pullrequestreview-5816656698); they are the
verifier's findings, not an owner-performed substitute.

- Verifier/date/time zone: Ka Pui Cheung, November 7, 2026, America/New_York.
- Evidence window: 21:55–22:01 EST; this is the request window, not the review time.
- Access: dashboard, Logs Explorer and Trace Explorer worked with the team
  account. Ka Pui reported that their NYU account did not have project access.
- Source: PR #49 review linked above, on commit `325515a`.

| Observation | Request A | Request B | Request C |
| --- | --- | --- | --- |
| Operation, HTTP status and outcome | create / POST, 201, success | create / POST, 422, invalid_input | create / POST, 503, provider_unavailable |
| Failure source and evidence | none; successful events.insert | caller; no Google child span | provider; OAuth refresh child ERROR, no insert |
| Release / environment | 900c328… / verify | 900c328… / verify | 900c328… / verify |
| Serving revision | team5-calendar-verify-00010-kbk | team5-calendar-verify-00010-kbk | team5-calendar-verify-00009-62d |
| Log/trace correlation | Verifier confirmed matching IDs | Verifier confirmed matching IDs | Verifier confirmed matching IDs |
| SERVER and child duration | 538 ms; insert 516 ms (96%) | 4.4 ms; no child | 83 ms; OAuth refresh 76 ms (91%) |
| Dashboard in the evidence window | create traffic and latency, success | create traffic/errors/latency, invalid_input | create traffic/errors/latency, provider_unavailable |
| Sensitive-data inspection | No event fields, tokens or credentials | No request body or validation details | No OAuth/secret contents or raw provider error |

Exact trace IDs and SERVER span IDs are in the links above, checked against
exported trace records. The review used abbreviated IDs; these links preserve
the complete recorded IDs rather than expanding the abbreviations by guesswork.

Verifier's conclusion: all three requests can be explained using the dashboard,
logs and traces alone; no blocking issue. Ka Pui also reported local Ruff, mypy
and 652 tests passing. The review explicitly marked the following notes optional.

Owner's documentation follow-up:

- A/B used recovered revision `00010-kbk`; C used failure-injection revision
  `00009-62d`. The same parent release label does not identify a unique revision.
  Check the outcome log's Cloud Run resource labels for the serving revision.
- `900c328…` is the candidate's parent, not a claim that the reviewed merge was
  deployed. Use the source fingerprint and image in the verification record.
- The workflow's GET after DELETE intentionally returns 404 `not_found`.
  This is recorded in the workflow evidence; the aggregate dashboard alone
  cannot identify a particular request as that cleanup check.
- Trace URLs now include the recorded SERVER `spanId`, following Ka Pui's
  report that `traceId` alone opened Explorer without selecting the trace.

Independent interpretation is complete. Re-review of these documentation edits
is pending; the reviewed merge's deployment evidence remains a separate step.

## Level 4 metric reference

Ka Pui owns SLI/SLO definitions, the error-budget policy and alert verification.
The following describes existing signals; it does not select those policies.

| Shared method | HTTP operation | Metric operation / log contract_operation |
| --- | --- | --- |
| create | POST /events | create |
| get | GET /events/{event_id} | get |
| replace | PUT /events/{event_id} | replace |
| delete | DELETE /events/{event_id} | delete |

PATCH (`patch`), calendar metadata (`get_calendar`), `health`, `ready` and
`http_other` are separate labels. Explicitly select the four common operations
when defining a shared-contract SLI.

| Signal | Stored metric type after prometheus.googleapis.com/ | Unit and interpretation |
| --- | --- | --- |
| Completed requests | calendar.requests/counter | Cumulative requests; includes successful, rejected and failed HTTP requests |
| Failed requests | calendar.request.errors/counter | Cumulative requests whose outcome is not success; categorized by outcome/source |
| Latency | calendar.request.duration/histogram | Seconds from request middleware entry through response handling; separate outcomes |
| Saturation | calendar.request.saturation/histogram | Active common-operation requests at entry / concurrency limit 1 |

The first three metrics carry `operation`, `outcome`, `failure_source`,
`http.response.status_code`, `release` and `environment`. Saturation carries
only operation, release and environment. The SDK resource also separates
process instances; preserve reset handling before aggregating counters.
Resource IDs, raw paths and trace IDs are not metric labels.

Outcomes include `success`, `invalid_input`, `not_found`, `access_denied`,
`provider_error`, `provider_unavailable`, `http_error` and `internal_error`.
Sources are `none`, `caller`, `provider` and `service`; source is diagnostic,
not an SLO eligibility rule. For example, not-found is categorized as caller,
but whether it belongs in a denominator is Ka Pui's policy decision.

Example Monitoring filter for the recorded historical GET traffic:

```text
resource.type="prometheus_target"
AND metric.type="prometheus.googleapis.com/calendar.requests/counter"
AND metric.labels.operation="get"
AND metric.labels.environment="verify"
AND metric.labels.release="900c32858390d6f8c5b49b7ff9efc5bcf381f161"
```

The current dashboard uses 60-second alignment and sums per-series counter
rates. Histograms use `ALIGN_DELTA`, followed by percentile reduction, grouped
by release/environment and, for latency, outcome. Histogram percentiles are
bucket estimates, not exact request durations. For a latency SLI, choose a
threshold and count eligible requests meeting it; p95 alone is not a count
of good requests. Do not average success and error latency together.

Metrics export every 30 seconds; traces batch every second. Backend ingestion
can lag. A new counter needs a usable baseline before a rate is meaningful.
An absent error series can mean no error was recorded, insufficient samples or
missing telemetry; it is not automatically zero. Keep no-data handling explicit.
Do not sum different releases or demo/verify environments into one objective
without an explicit aggregation policy.

The concurrency ratio samples request entry and is not time-weighted occupancy
or a queue-length measure. Cloud Run memory utilization is instance-wide and
shared by operations. Neither is an availability SLI by itself. A wrong 2xx
response can still be labeled success by HTTP telemetry; conformance and real
provider read-back remain separate correctness checks. Uncertain POST/PUT
results must retain retryable=false; an alert does not authorize retrying them.

### Level 4 handoff receipt

- Recipient: Ka Pui Cheung.
- Walkthrough document received and used: [Ka Pui’s PR review](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/49#pullrequestreview-5816656698).
- Level 4 policy and implementation: [SLIs, SLOs, error budget and alerts](SLO.md), Terraform in `infra/observability/slo.tf`.
- Eligible operations/outcomes and latency threshold: defined in [SLO.md](SLO.md#slis-and-objectives-28-day-rolling-window).
- No-data/reset/environment handling: defined in [SLO.md](SLO.md#no-data-resets-and-retries). Cloud apply verified 2026-11-08 (see [SLO.md](SLO.md#verification)); alert test done 2026-11-11 (see [SLO.md](SLO.md#alert-test-2026-11-11)).

## Reviewed deployment follow-up

The reviewed Level 3 merge `8ad2e64` passed
[Deploy run 42535452049](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/42535452049).
After Level 4 merged, `191b006` passed the pipeline again. Use the deployed
manifest's release, not the historical parent SHA above.

| Evidence | Status/link |
| --- | --- |
| Level 3 PR and reviewed merge commit | PR #49 approved at 325515a; merged as `8ad2e64` |
| Successful Deploy run and verified-release artifact | [Run 43100667215](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/43100667215), Level 4 merge `191b006` |
| Google smoke/cleanup | Passed in that run; ready revision `team5-calendar-demo-00005-ld8` |
| Fresh log/trace for the merged deployment | [November 11 deployed conformance observations](DEPLOYED_CONFORMANCE_VERIFICATION.md#fresh-log-and-trace-evidence); dashboard chart queries were not repeated in that check |

Independent historical interpretation, code review and reviewed-release
verification are separate evidence. See the
[cloud verification record](OBSERVABILITY_VERIFICATION.md) for the checks
already completed and the restored verify/demo state.
