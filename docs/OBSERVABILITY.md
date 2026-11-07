# Level 3 request observability

Owner: Jim Lo. Request metrics and outcome logging are implemented. Provider
spans, cloud export, saturation, the dashboard, and deployed/teammate verification
remain follow-up work. This document does not claim Level 3 is complete.

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
Provider-call timing will be added separately.

## Metrics

| Instrument | Type / unit | Meaning |
| --- | --- | --- |
| `calendar.requests` | Counter / requests | Completed HTTP requests, including rejected and failed requests |
| `calendar.request.errors` | Counter / requests | Requests whose outcome is not `success` |
| `calendar.request.duration` | Histogram / seconds | Duration distribution, separated by outcome |

All instruments use the same finite labels: `operation`, `outcome`,
`failure_source`, and `http.response.status_code`. They contain no resource IDs,
raw paths, query strings, request IDs, titles, or caller-provided labels.

| HTTP operation | Metric `operation` / log `contract_operation` | Existing log `operation` |
| --- | --- | --- |
| POST `/events` | `create` | `create_event` |
| GET `/events/{event_id}` | `get` | `get_event` |
| PUT `/events/{event_id}` | `replace` | `replace_event` |
| DELETE `/events/{event_id}` | `delete` | `delete_event` |
| PATCH extension | `patch` | `update_event` |
| Calendar metadata extension | `get_calendar` | `get_calendar` |

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
`duration_ms`, and `request_id`. Successes are INFO, caller failures are WARN,
and service/5xx failures are ERROR. `provider` is the inherited error-context
flag, not a count of provider calls; it is null when no shared error was handled.

The release is the full lowercase commit SHA from `CALENDAR_RELEASE`, or `local`
when it is absent/invalid. Each request gets a new server-generated UUID and the
same `X-Request-ID` response header on responses that reach the middleware.
Caller-supplied IDs are not trusted or logged. A framework-generated 500 outside
this middleware may lack that header; its outcome log still has a request ID.
Trace correlation will be added with tracing, not fabricated from this UUID.

Telemetry excludes credentials, authorization headers, raw URLs, bodies, event
IDs, titles, descriptions, provider error messages, and tracebacks. Recording
failures are dropped without changing the HTTP result or repeating an operation.
The middleware neither buffers request bodies nor stores individual measurements.

## Local verification and remaining integration

```sh
uv sync --frozen
uv run pytest tests/test_observability.py -v
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

Production instrumentation currently obtains instruments from the OpenTelemetry
API's global meter provider. Until SDK/exporter initialization is wired in the
next integration batches, ordinary runs emit outcome logs but do not retain or
export metric measurements. The test reader is not installed globally and is
not an application endpoint. No exporter thread or network call is introduced.

Follow-up work must configure bounded, non-blocking cloud export, resource
release metadata, provider spans, a saturation measure, and a dashboard. Then
verify successful, invalid, and provider-failure requests in the deployed service,
inspect sanitized exports, and have another teammate explain them using only
dashboard/log/trace links. Hand those queries and labels to Ka Pui for Level 4.
