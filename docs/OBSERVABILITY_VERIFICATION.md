# Level 3 cloud observability verification

Owner: Jim Lo. Recorded November 07, 2026 22:08 EST (2026-11-08 03:08 UTC).

This record checks a candidate deployed before its implementation was committed, in the disposable verify service. It is not a GitHub release, a deployment of the eventual reviewed commit, or independent teammate verification. The run did not use a Git push or workflow dispatch, and no external message was sent.

The implementation was subsequently committed as `ac1b7c2`. An offline comparison confirmed that all 29 committed Dockerfile/app/pyproject/lock build inputs match the source fingerprint below. The historical logs still carry the parent release; a deployment of the reviewed merge commit remains separate.

## Candidate and scope

- Base commit: `900c32858390d6f8c5b49b7ff9efc5bcf381f161`. This value was used for `CALENDAR_RELEASE`; it identifies the parent, not these uncommitted files.
- Source SHA-256 over the sorted Dockerfile/app/pyproject/lock inputs: `ef6c8d718947864e8d7ae9ef2d845cec8d7513aeb661fe3d57623130c3f41a59`.
- Immutable image: `us-central1-docker.pkg.dev/ospsd-team5/team5-calendar-verify/calendar@sha256:f58b6455b820bbe0bdaf22702f7745a87de399168c1f62a5c885f8029475a030`.
- The build context contained only Dockerfile, Python app source, pyproject.toml, and uv.lock. No OAuth, bearer, ADC, Terraform state, or repository history entered the image.
- Valid candidate revisions: `team5-calendar-verify-00008-mkj` and recovery revision `team5-calendar-verify-00010-kbk`; controlled failure revision: `team5-calendar-verify-00009-62d`.
- Demo application, revision and traffic were unchanged. The approved administrator setup enabled the observability APIs and granted telemetry/quota writer access to the existing demo/verify runtime identities in separate Terraform state.

## Local checks

- Python: 652 passed; 24 opt-in live-conformance cases skipped in the offline command. Those skips are not live evidence.
- Ruff lint and format, strict mypy for app/tests, mypy for the existing deployment/live scripts, actionlint, and git diff whitespace checks passed.
- Terraform formatting and validation passed for the service, CI, and observability roots. Four existing CI mock tests and one observability mock test passed.
- Six new cloud telemetry tests use real SDK/OTLP serialization with controlled transport. They check destination-project resource attributes, correlation, private-value exclusion, offline behavior, saturation, startup failure and a blocked exporter.

## Real deployed workflow

Final-image workflow markers `9dfa5fca057a`, `eeec101e6086`, and `08121481f906` passed. The later runs verify recovery and provide another counter sample for traffic-rate checks. Each run used the existing verification helpers against deployed HTTPS, not dependency overrides.

Health 200, readiness 204, POST 201, GET 200, PUT 200, and GET 200 passed. Independent Google SDK read-back confirmed the same ID, title, times and preserved description. DELETE returned 204; subsequent GET and repeated DELETE returned 404. Additional invalid POST and PUT requests returned 422 without a provider call.

A temporary **new** verify OAuth secret version 2 contained an invalid refresh token. Google rejected the real refresh request. POST returned 503 `provider_unavailable`, `retryable=false`; the request trace identifies the failing OAuth boundary. No Calendar insert was attempted. The valid grant was neither changed nor revoked. Version 2 was destroyed, version 1 restored, and the real normal workflow passed after recovery.

## Actual metrics, logs and traces

[Dashboard](https://console.cloud.google.com/monitoring/dashboards/custom/c25e66c8-e3e3-44bc-af2b-6707ca37a175?project=ospsd-team5). Select **November 7, 2026, 21:55–22:01 EST** (November 8, 02:55–03:01 UTC) for these request examples. The service has since been restored; current-time gaps are expected.

All 17 chart queries were read back from the created dashboard and executed against real Monitoring data. Every query succeeded and returned data: four signals for each shared operation, plus shared Cloud Run memory. The series expose the parent release and verify environment. Cumulative histogram panels use interval deltas before percentile reduction.

| Case | HTTP / source | Outcome log | Trace |
| --- | --- | --- | --- |
| success | 201 / none | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Fb49454506862e151bc19e7e7866ba2e6%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=b49454506862e151bc19e7e7866ba2e6?project=ospsd-team5) |
| invalid_input | 422 / caller | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Ff2a765aeb27c51c738b8a54847950029%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=f2a765aeb27c51c738b8a54847950029?project=ospsd-team5) |
| provider_failure | 503 / provider | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2Facbf0393a219d301c633b49216030b27%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=acbf0393a219d301c633b49216030b27?project=ospsd-team5) |
| replace_success | 200 / none | [log](https://console.cloud.google.com/logs/query;query=trace%3D%22projects%2Fospsd-team5%2Ftraces%2F5c9ee3144bf5020fd7fe522df481c931%22%20AND%20jsonPayload.service%3D%22calendar-team-5%22?project=ospsd-team5) | [trace](https://console.cloud.google.com/traces/explorer;traceId=5c9ee3144bf5020fd7fe522df481c931?project=ospsd-team5) |

Each exact trace lookup returned one application outcome log. Its request/trace IDs match the HTTP response, and its release matches the SERVER span. Google CLIENT spans have the SERVER span as parent. Invalid input has no Google child; successful PUT has separate get/patch children; authorization failure has an OAuth refresh child.

Actual exported logs and traces were inspected. The checks compared their contents with the real bearer, OAuth client secret and refresh token in memory, and searched for test titles/descriptions and the deliberately invalid token. None appeared. No recorded stack trace or exception event was present. Only sanitized evidence is recorded here.

## Findings resolved during verification

- The first candidate omitted the required `gcp.project_id` resource attribute. Google rejected the nonempty OTLP batches. The final candidate sets it on both SDK resources, and the wire tests now check it.
- The first dashboard applied a gauge-style percentile aligner directly to cumulative histograms. Real query execution rejected it; the final dashboard uses `ALIGN_DELTA` followed by percentile reduction.
- The dashboard API omits zero-valued layout coordinates. The Terraform source follows that shape so repeated plans do not attempt cosmetic updates.
- Cloud telemetry and log indexing are asynchronous. Use a bounded timestamp window and follow API continuation tokens; an empty intermediate log page is not proof of a missing log.

## Cleanup and restoration

- Verify restored to its original image, four environment variables, OAuth/bearer version 1, CPU throttling, concurrency and instance limits. The actual ready revision is `team5-calendar-verify-00011-qgx`; its revision-level image/configuration and traffic were checked, not only the service template.
- After restoration: health 200, readiness 204, and real Google calendar metadata GET 200.
- Independent Google searches for all 4 owned workflow markers found zero remaining events, including the early workflow used while diagnosing export.
- Temporary invalid secret version 2 is DESTROYED; the original version remains usable. Temporary OAuth files and Docker registry authentication files were removed.
- Demo remains `team5-calendar-demo-00003-gd4` with its original image, configuration and traffic.
- Observability APIs, writer grants and dashboard remain as approved. Candidate image artifacts remain in the verify registry for provenance; they are not release tags. Follow the deployment/observability teardown instructions when no longer needed.
- The original Level 2 verify Terraform configuration and final observability configuration both produced no-change plans (detailed exit code 0).

## Required follow-up

Jim plans to ask Ka Pui Cheung to explain the successful, invalid and provider-failure requests using only the dashboard/log/trace links. Ka Pui has not performed the walkthrough or accepted the handoff yet. The [walkthrough worksheet and Level 4 reference](OBSERVABILITY_HANDOFF.md) contain the entry links, questions and pending result fields.

Record the actual verifier, date, observations and any corrections. After review/merge, deploy the actual reviewed commit through the existing pipeline and record that release evidence. The candidate checks do not replace either step. The same handoff reference gives Ka Pui the operation names, metric types, labels, no-data behavior and queries; no SLO or alert is claimed here.
