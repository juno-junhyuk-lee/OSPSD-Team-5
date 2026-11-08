# Level 4 SLIs, SLOs, error budget and alerts

Owner: Ka Pui Cheung. Built on the [Level 3 metric reference](OBSERVABILITY_HANDOFF.md#level-4-metric-reference). Terraform: `infra/observability/slo.tf`.

## Scope

- Operations: the four shared-contract operations `create`, `get`, `replace`, `delete`. PATCH, calendar metadata, `health`, `ready` and `http_other` are excluded.
- Environment: `demo` by default (`slo_environment`). `verify` is disposable and never shares an objective with `demo`.
- Releases are aggregated within the environment; a deploy does not reset the budget.

## SLIs and objectives (28-day rolling window)

| SLO | SLI (request-based) | Objective | Budget |
| --- | --- | --- | --- |
| Availability | Eligible = all shared-operation requests (`calendar.requests`). Bad = errors with `failure_source` `service` or `provider` (`calendar.request.errors`). | 99% | 1% of requests |
| Latency | Eligible = successful shared-operation requests (`calendar.request.duration`, `outcome="success"`). Good = finished within 1 s. | 95% | 5% of successful requests |

Why these choices:

- Caller outcomes (`invalid_input`, `not_found`, `access_denied`) are correct rejections, so they count as eligible but never as bad. A 404 is not an outage.
- Provider failures count as bad: users see a failed request whatever the cause, and Google outages are the main availability risk.
- Latency uses success only, so fast rejections cannot hide slow successes. The Level 3 sample shows create at 538 ms (Google insert 516 ms) and rejections at about 4 ms; 1 s leaves room for Google calls but flags cold starts and slow provider calls.
- Histogram buckets bound the threshold; 1 s must stay a bucket boundary.

## Alerts

One policy per SLO, each with two burn-rate conditions (Google SRE multiwindow pattern):

| Condition | Window | Burn rate | Meaning |
| --- | --- | --- | --- |
| Fast | 1 h | > 14.4 | About 2% of the 28-day budget in one hour; act now |
| Slow | 6 h, held 5 min | > 6 | About 5% of the budget in six hours; act the same day |

`alert_email` adds an email channel; it is empty by default so applying the module emails no one by surprise.

## No data, resets and retries

- No data is not zero errors. A missing series can mean no traffic, too few samples or broken telemetry. Burn-rate conditions evaluate to no data in that case; check the dashboard's traffic panel before trusting a quiet alert.
- Counters are cumulative per process; Cloud Monitoring's SLO computation handles resets per time series, so do not pre-sum counters across instances.
- Uncertain POST/PUT results keep `retryable=false`. An alert never authorizes retrying them.
- A wrong 2xx response is still "good" to these SLIs. Conformance tests and provider read-back remain the correctness checks.

## Error-budget policy

| Budget left (28 d) | Action |
| --- | --- |
| > 50% | Normal work; deploy through the existing pipeline. |
| 25–50% | Each deploy needs a passing Google smoke run before traffic moves; review the failing outcome/source on the dashboard. |
| < 25% | Freeze feature merges to `hw2/milestone-3`; only reliability fixes and rollbacks until the budget is above 25%. |
| Exhausted | Roll back to the last verified release; write a short incident note in the PR that caused it. |

Provider-caused burn still counts. If Google is the cause, the response is retry/backoff or capacity work on our side, not excluding the data.

## Verification

| Check | Status |
| --- | --- |
| `terraform test` (mock provider): goals, bad-filter scope, success-only latency, two burn conditions per SLO, no default channel | Added in `tests/slo.tftest.hcl` |
| Apply in `ospsd-team5` and confirm both SLOs report compliance on the demo service | **Pending** |
| Alert test: inject provider failures in `verify` with `slo_environment=verify`, confirm the fast-burn condition opens and then closes | **Pending** |

The pending rows need cloud access and a controlled failure window; record the run, times and incident links here when done.
