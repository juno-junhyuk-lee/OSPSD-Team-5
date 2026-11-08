# Level 3 independent walkthrough and Level 4 handoff

Owner: Jim Lo. Planned verifier and Level 4 recipient: Ka Pui Cheung.
Jim plans to invite Ka Pui; the walkthrough and its acceptance are **pending**.
No independent verification or final Level 3 sign-off is claimed here.

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
| A | 02:59:38 | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Fb49454506862e151bc19e7e7866ba2e6%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=b49454506862e151bc19e7e7866ba2e6?project=ospsd-team5) |
| B | 02:59:41 | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Ff2a765aeb27c51c738b8a54847950029%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=f2a765aeb27c51c738b8a54847950029?project=ospsd-team5) |
| C | 02:57:16 | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Facbf0393a219d301c633b49216030b27%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=acbf0393a219d301c633b49216030b27?project=ospsd-team5) |

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

Ka Pui should fill this in or provide equivalent observations in a linked PR
comment. Jim can transcribe the actual response and retain its source link.

- Verifier/date/time zone: **Pending**
- Dashboard, log and trace access: **Pending**
- Source comment or review link: **Pending**

| Observation | Request A | Request B | Request C |
| --- | --- | --- | --- |
| Operation, HTTP status and outcome | Pending | Pending | Pending |
| Caller/service/provider/none, with evidence | Pending | Pending | Pending |
| Release and serving revision | Pending | Pending | Pending |
| Matching log/trace ID | Pending | Pending | Pending |
| SERVER duration and Google child spans | Pending | Pending | Pending |
| Corresponding dashboard series/time window | Pending | Pending | Pending |
| Sensitive-data inspection | Pending | Pending | Pending |

- Problems or clarification needed: **Pending**
- Owner's corrections and verifier recheck, if needed: **Pending**
- Verifier's conclusion: **Pending**

Independent interpretation is complete when all three requests can be explained
from those links and any blocking access/documentation issue has been resolved.
Code-review approval alone does not record this walkthrough. Keep its status
pending until Ka Pui supplies actual observations.

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
- Delivery/acknowledgment and source link: **Pending**.
- Proposed eligible operations/outcomes and latency thresholds: **Pending;
  Level 4 owner to define**.
- No-data/reset/environment handling and alert test evidence: **Pending;
  Level 4 owner to define**.

## Reviewed deployment follow-up

After review/merge into `hw2/milestone-3`, the existing pipeline should deploy
the merged revision. Follow the [deployment runbook](DEPLOYMENT.md#level-2-automated-deployment-and-recovery)
and record the actual run, merge SHA, image digest, secret references and ready
revision/traffic, along with Google smoke/cleanup and fresh cloud observations.
Use the deployed manifest's release, not the historical parent SHA above.
These entries remain pending until that deployment actually happens:

| Evidence | Status/link |
| --- | --- |
| Level 3 PR and reviewed merge commit | Pending |
| Successful Deploy run and verified-release artifact | Pending |
| Google smoke/cleanup | Pending |
| Dashboard/log/trace for the reviewed deployment | Pending |

Independent historical interpretation, code review and reviewed-release
verification are separate evidence. See the
[cloud verification record](OBSERVABILITY_VERIFICATION.md) for the checks
already completed and the restored verify/demo state.
