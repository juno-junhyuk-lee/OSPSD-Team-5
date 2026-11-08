# Level 3 request observability

Owner: Jim Lo. Request metrics, outcome logs, explicit Google-call spans,
opt-in cloud export, saturation, and a Terraform dashboard are implemented.
Controlled tests and real deployed evidence are different checks. Independent
teammate interpretation and reviewed-release verification remain required;
implementation alone does not establish Level 3 completion.

## Request boundary

`RequestTelemetryMiddleware` surrounds caller authentication, validation, and
route execution. It attempts one JSON outcome log and one set of OpenTelemetry
measurements when an HTTP request ends. `app/errors.py` passes only the error
category and provider-context flag to that middleware instead of emitting a
second failure log. A standalone error handler without the middleware retains
its previous logging behavior.

The public error response, provider calls, and retry rules are unchanged.
Unexpected exceptions are recorded without their messages or traceback and
continue through the existing framework error handling. Response-model
validation failures count as `internal_error`, rather than successful requests.

The duration uses a monotonic clock, from middleware entry until the wrapped
application returns or raises. It includes authentication, validation, and
response handling; it is not an independent measurement of Google latency.
Provider-call timing is shown separately by the Google CLIENT spans.

## Metrics

| Instrument | Type / unit | Meaning |
| --- | --- | --- |
| `calendar.requests` | Counter / requests | Completed HTTP requests, including rejected and failed requests |
| `calendar.request.errors` | Counter / requests | Requests whose outcome is not `success` |
| `calendar.request.duration` | Histogram / seconds | Duration distribution, separated by outcome |
| `calendar.request.saturation` | Histogram / ratio | Active shared-operation requests at entry / instance concurrency limit 1 |

All instruments use the same finite labels: `operation`, `outcome`,
`failure_source`, and `http.response.status_code`. Cloud instruments also include
the sanitized commit `release` and allowlisted `environment` (`demo`, `verify`,
or `local`). Saturation has only operation and those cloud labels. They contain no resource IDs,
raw paths, query strings, request IDs, titles, or caller-provided labels.

| HTTP operation | Metric `operation` / log `contract_operation` | Existing log `operation` |
| --- | --- | --- |
| POST `/events` | `create` | `create_event` |
| GET `/events/{event_id}` | `get` | `get_event` |
| PUT `/events/{event_id}` | `replace` | `replace_event` |
| DELETE `/events/{event_id}` | `delete` | `delete_event` |
| PATCH extension | `patch` | `update_event` |
| Calendar metadata extension | `get_calendar` | `get_calendar` |

Saturation uses a process-local locked count of active common-operation
requests; every exit releases its slot, including validation and provider
failures. Health/readiness and extensions do not consume this measure. The
denominator matches Terraform's one concurrent request and Docker's one worker.
Change those settings and the measure together. Values above one indicate
overlap beyond that limit, not a percentage to clamp. Entry sampling captures
short requests; it does not measure average occupied time or queued requests.
No observations during idle time is a gap, not a zero or health assertion.

The four common labels match the shared Python interface method names. Keep this
mapping consistent when coordinating dashboards with Teams 2 and 7. Health and
readiness use `health` and `ready`; other routes use `http_other`. Separate these
from the four common operations in consumer dashboards and future SLI queries.

Shared error outcomes retain `invalid_input`, `not_found`, `access_denied`,
`provider_error`, and `provider_unavailable`. Unclassified HTTP client errors
use `http_error`; unexpected service failures use `internal_error`.
Successful/non-error HTTP responses use `success`. This does not prove semantic
correctness of every 2xx response; conformance and smoke checks remain necessary.

`failure_source` is `caller` for invalid input, missing resources, and rejected
caller authentication; `provider` for known provider failures; `service` for
local setup and unexpected failures; and `none` for successful requests. This is
a diagnostic classification, not the definition of future SLO eligibility.
For example, whether 404 belongs in an SLI denominator remains a Level 4 choice.

## Logs and correlation

Every outcome log includes `service`, `release`, `operation`,
`contract_operation`, `outcome`, `error`, `failure_source`, `provider`, `status`,
`duration_ms`, `request_id`, `trace_id`, and `span_id`. Successes are INFO, caller failures are WARN,
and service/5xx failures are ERROR. `provider` is the inherited error-context
flag, not a count of provider calls; it is null when no shared error was handled.

The release is the full lowercase commit SHA from `CALENDAR_RELEASE`, or `local`
when it is absent/invalid. Each request gets a new server-generated UUID and the
same `X-Request-ID` response header on responses that reach the middleware.
Caller-supplied IDs are not trusted or logged. A framework-generated 500 outside
this middleware may lack that header; its outcome log still has a request ID.
When the tracing SDK is available, `trace_id` and `span_id` identify the actual
request span, and `X-Trace-ID` carries that trace ID on responses that reach the
middleware. If tracing is unavailable they are null and the header is omitted.
Trace IDs are generated by the SDK, separately from request UUIDs.
Cloud logs add `severity` and Google's special trace/span fields, so Cloud
Logging can open the associated Cloud Trace. They do not reuse the platform's
caller-influenced trace header. Both IDs still appear in the JSON outcome.

## Request and provider traces

The application lifespan creates an app-owned `TracerProvider` with only the
service name and sanitized release as resource metadata. It samples every local
request. No global trace provider, automatic HTTP instrumentation, request-header
capture, or cross-service propagation is enabled. Incoming `traceparent` and
`baggage` do not supply the parent or exported attributes. These choices keep
caller-controlled data out of telemetry and leave cross-service tracing outside
this milestone's required scope.

Each HTTP request has one SERVER span named `calendar.<operation>`. It covers
authentication, validation, route execution, and response handling, and records
the same safe operation, outcome, source, and HTTP status as the log. HTTP 5xx
and unexpected service failures mark it ERROR. Caller 4xx results retain their
outcome attributes without marking the server span ERROR.

Within the request, explicit Google calls have CLIENT child spans:

| Span | Boundary |
| --- | --- |
| `google.calendar.events.insert` | POST SDK call |
| `google.calendar.events.get` | GET SDK call or PUT/PATCH pre-read |
| `google.calendar.events.patch` | PUT/PATCH write SDK call |
| `google.calendar.events.delete` | DELETE SDK call |
| `google.calendar.calendars.get` | Calendar metadata SDK call |
| `google.calendar.oauth.refresh` | Explicit credential refresh |

PUT/PATCH therefore has separate read and write spans. Local credential-file
loading and response translation remain outside these RPC spans. SDK discovery,
client construction, and refresh performed internally by an SDK execute call
are not separately instrumented; their time belongs to the enclosing span.
Normal direct adapter/authorization-script calls outside an HTTP request do not
create orphan provider traces.

Provider spans contain only fixed `rpc.system` and `rpc.method` attributes.
Exceptions mark them ERROR without an exception message, event, traceback,
status description, URL, resource ID, or payload. If a call returns malformed
data, its RPC span can finish without an exception while translation subsequently
marks the request as a provider failure. An RPC returning is not proof that its
result satisfies the contract.

Context follows the existing async middleware and synchronous worker threads.
Concurrent requests receive separate trace trees. The request log is written
while its SERVER span is current, so its identifiers match the exported span.
Provider exceptions still reach the existing error translation unchanged; no
provider call is retried by tracing.

The SDK bounds each span to 16 attributes of at most 128 characters, with no
events or links. Tracer startup, span start/update/end, and shutdown failures
are dropped rather than failing or repeating API work. A later exporter must
remain bounded and non-blocking as well.

Telemetry excludes credentials, authorization headers, raw URLs, bodies, event
IDs, titles, descriptions, provider error messages, and tracebacks. Recording
failures are dropped without changing the HTTP result or repeating an operation.
The middleware neither buffers request bodies nor stores individual measurements.

## Local verification and remaining integration

```sh
uv sync --frozen
uv run pytest tests/test_observability.py -v
uv run pytest tests/test_tracing.py -v
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -v
```

The new tests use the actual OpenTelemetry SDK with an `InMemoryMetricReader`
and isolated controlled service dependencies. They inspect aggregated counters
and histogram buckets, success/failure separation, sensitive-data exclusion,
authentication/validation failures, response-validation failures, bounded label
cardinality, and behavior when metric/log recording fails. They make no Google
calls and do not establish deployed behavior.

Tracing checks use the normal application lifespan, routes, and real Google
adapters, replacing only Google clients/credentials with controlled fixtures.
An isolated SDK provider and bounded in-memory span exporter verify parentage,
log/header correlation, RPC timing boundaries, parallel-request isolation,
unchanged error/retry behavior, and sanitized exports. They also check invalid
input, bearer rejection, malformed provider responses, unexpected exceptions,
credential refresh, and tracing failures. No Google access is required.

`tests/test_cloud_telemetry.py` serializes real SDK measurements/spans through
the official OTLP exporters into controlled HTTP sessions. It checks wire data,
log/trace correlation, parallel saturation, startup failure, shutdown, and a
blocked exporter while HTTP requests still complete. These checks do not
contact Google Cloud and must not be described as deployed evidence.

## Cloud setup

The runtime exports only when `CALENDAR_TELEMETRY_PROJECT` is a valid project
ID. Without it, startup does not discover ADC or open telemetry connections;
local spans have real IDs but are not retained/exported, and ordinary local
metric instruments remain no-op unless a test supplies a meter. Cloud startup
creates a separate metric provider and uses its instruments for each request;
it never installs global SDK providers. Startup/export failures preserve API
behavior but can cause missing observations, which must be investigated.

Exports use Google's runtime ADC and quota project, not Calendar OAuth or the
API bearer. Both SDK resources explicitly set `gcp.project_id` to identify the
destination; the credential's quota project alone does not select it.
The official OTLP/HTTP exporters send protobuf over TLS to
`https://telemetry.googleapis.com/v1/traces` and `/v1/metrics`. Separate sessions
avoid sharing mutable auth state between the two worker threads. Cloud Run
requires always-allocated CPU (`cpu_idle=false`) so export can continue after
the HTTP response. Minimum instances remain zero and maximum one; see the
billing implications in DESIGN.md.

Bounds: 512 queued spans, batches of at most 64 spans, 1-second trace scheduling,
30-second metric scheduling, 3-second export timeouts, and 256 KiB request size
limits. Metric requests split at 256 data points; the SDK bounds aggregation
cardinality (default 2,000 per instrument), including an overflow series.
Exporter internal metrics are disabled. SDK/exporter diagnostics retain only
the signal, HTTP status, and exception type, without response text or tracebacks. Telemetry transport
may retry within its short deadline; it never retries Calendar operations.
There is no disk spool, synchronous route export, or public telemetry endpoint.
Shutdown attempts to flush and then discards remaining observations.

An administrator provisions `infra/observability` separately from release CI:

```sh
terraform -chdir=infra/observability init \
  -backend-config=bucket=ospsd-team5-terraform-state \
  -backend-config=prefix=calendar/observability
terraform -chdir=infra/observability plan \
  -var=project_id=ospsd-team5 -out=/private/tmp/calendar-observability.tfplan
# Inspect the plan before applying the exact saved plan.
terraform -chdir=infra/observability apply /private/tmp/calendar-observability.tfplan
terraform -chdir=infra/observability output -raw dashboard_url
```

This state enables the Telemetry/Monitoring/Trace/Logging APIs, grants only
`roles/telemetry.writer` and `roles/serviceusage.serviceUsageConsumer` to the
existing demo/verify runtime identities, and creates the dashboard. It does not
deploy a service, read secrets, or grant project administration. The CI state
and deployment plan restrictions are unchanged. Normal service Terraform adds
`CALENDAR_ENV`, `CALENDAR_TELEMETRY_PROJECT`, and always-allocated CPU. Deploy a
reviewed commit through the existing pipeline once administrator setup is ready.

## Dashboard and investigation

The dashboard has four panels for each shared operation, plus investigation
instructions and shared Cloud Run memory utilization. Traffic/error rates use
60-second alignment; errors retain outcome labels. Latency converts cumulative
histograms to interval deltas and estimates the pooled p95 for each outcome
from their buckets. Saturation
shows the p99 request-entry concurrency ratio. Legends expose release and
environment, preventing demo/verify or different releases from being summed
together. No-data gaps remain gaps. A single counter sample may not establish
a rate; expand the time window and inspect the log and raw metric point too.

Direct OTLP metric names are `prometheus.googleapis.com/calendar.requests/counter`,
`calendar.request.errors/counter`, `calendar.request.duration/histogram`, and
`calendar.request.saturation/histogram` under that same prefix. This ingestion
path preserves dots and does not append `_total` or a unit to the name. Do not
reuse collector-exporter metric names without checking actual descriptors.

1. Select the time window, operation, release, and environment. A chart point is
   aggregated evidence, not an individual request identifier.
2. Open Cloud Logging from the dashboard. Filter
   `jsonPayload.service="calendar-team-5"`, then `jsonPayload.release`,
   `jsonPayload.contract_operation`, and `jsonPayload.outcome` for the panel.
3. Use `jsonPayload.request_id` or `trace="projects/PROJECT/traces/TRACE_ID"`
   to isolate the request. Set an explicit time window around the request;
   an API log scan can return empty intermediate pages with a continuation
   token, which must be followed. The response supplies `X-Request-ID` and `X-Trace-ID`.
4. Open the log's Trace link. Compare the SERVER duration with explicit Google
   CLIENT spans and inspect outcome/source/status and the serving release.
   A 422 should have no Google child; a provider auth failure should show
   `google.calendar.oauth.refresh` failing; successful CRUD has SDK call spans.
5. Inspect exported JSON and spans for secret/body/provider-content exclusion.
   Do not copy bearer values, event IDs/titles, descriptions or OAuth files into
   evidence, dashboards, screenshots, commits, or handoff messages.

## Deployed verification and Level 4 handoff

Keep an evidence record of the source/build fingerprint, immutable image,
environment, revision, UTC window, sanitized statuses, dashboard, log, and trace
links. An uncommitted candidate is not a published commit or verified release.
Use only the disposable verify environment for failure injection. A temporary
invalid refresh token can exercise a real Google authorization rejection
without revoking the team's valid grant; destroy that temporary secret version
and restore the original configuration after the check. No failure switch is
added to the application or demo environment.

Verify success, invalid input, and provider failure in the deployed candidate.
Complete the real POST/GET/PUT/GET/DELETE workflow with independent provider
read-back and cleanup, then inspect actual exported data in Monitoring,
Logging, and Trace. Restoring code does not undo Calendar writes.

A teammate who did not implement instrumentation must explain those three
requests using only the dashboard/log/trace links. Record their name, date, and
findings; agent inspection is not a substitute. Final reviewed deployment and
that independent walkthrough remain separate from this implementation batch.
Hand the common names, category/source labels, denominators, no-traffic behavior,
and queries to Ka Pui for Level 4. No availability/latency target or alert is
defined by Level 3; a wrong 2xx result still needs smoke/conformance detection.

See [the deployed verification record](OBSERVABILITY_VERIFICATION.md) for the
uncommitted candidate's actual cloud data and the remaining deployment checks.
The [independent walkthrough and Level 4 handoff](OBSERVABILITY_HANDOFF.md)
provides corrected request links, Ka Pui’s completed independent findings, metric
query details, and a separate reviewed-deployment checklist.

To tear down observability, first disable export in the service configuration,
then review/apply `terraform destroy` for this state. It removes the dashboard
and these writer grants; APIs stay enabled to protect other project resources.
Existing backend retention still applies to previously ingested observations.

References: [Google OTLP API and authentication](https://docs.cloud.google.com/stackdriver/docs/reference/telemetry/overview),
[metric mapping](https://docs.cloud.google.com/stackdriver/docs/reference/telemetry/v1.metrics),
and [OpenTelemetry exporters](https://opentelemetry.io/docs/languages/python/exporters/).
