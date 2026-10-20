# HW1 final release evidence

This page covers the final-release items not tied to one operation's Level 5 record. Other evidence:

- Justified decision (one shared error format): [DELETE Level 5 verification](DELETE_LEVEL5_VERIFICATION.md#design-decision-one-shared-error-format).
- A test that catches a defect, and a bug investigation (event GET returned deleted events): [#30](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/30) and [event GET Level 5 verification](EVENT_GET_LEVEL5_VERIFICATION.md#cancelled-event-review-follow-up).

## Operation cost: event GET

`GET /events/{event_id}` returns four fields, but its work grows with the size of the Google event it reads.

**Input size.** Let *n* be the size of Google's event resource in bytes. Google returns every field of the event: description, attendees, attachments, reminders, conference data and more. The ID is capped at 1024 characters, so its check is O(1) for our purposes.

**Data structures.** The SDK reads the HTTP body into a `bytes` buffer and decodes it with `json.loads` into nested Python `dict`s and `list`s. `translate_event` reads four keys from that dict and builds one `Event` Pydantic model.

| Step | Time | Memory |
| --- | --- | --- |
| ID format check | O(1) (ID ≤ 1024 chars) | O(1) |
| Receive and decode the response | O(n) | O(n) for the body and the parsed dict |
| `status == "cancelled"` check and `translate_event` | O(1) dict lookups, plus O(title length) to copy the title | O(title length) |
| Serialize the four-field response | O(title length) | O(title length) |

So the request costs O(n) time and O(n) peak memory, even though the response it returns is bounded by the title length.

**Provider calls.** One `events.get` call per request. An expired token adds one refresh first, and a Google 401 makes the auth library refresh and replay the request up to `DEFAULT_MAX_REFRESH_ATTEMPTS = 2` times, so the worst case is three HTTP requests. The count does not depend on *n*.

**Measurement.** On 2026-10-19, against the shared account, we created timed events with descriptions of 0, 1000 and 8000 characters, read each one, and deleted it. "Parse" is `json.loads` plus `translate_event` on the returned dict, averaged over 1000 runs.

| Description | Full response | With `fields=id,summary,start,end,status` | Parse time | Peak parse memory |
| --- | --- | --- | --- | --- |
| 0 chars | 754 B | 256 B | 70 µs | 5.2 KB |
| 1000 chars | 1773 B | 256 B | 65 µs | 6.6 KB |
| 8000 chars | 8773 B | 256 B | 83 µs | 20.6 KB |

The full response grows linearly with the description; network time dominates the parse time at these sizes.

**Assumptions.** One event per request; Google's lookup by ID is treated as constant from our side, since we cannot see its implementation; the description is the only large field (attendees and attachments grow *n* the same way).

**Possible improvement.** Passing `fields="id,summary,start,end,status"` to `events.get` would make the response size independent of the description and attendees, so local time and memory would become O(title length). We have not changed this because events in the test calendar are small, and the field list would have to stay in sync with `translate_event`.

## Teammate extension: calendar GET scope check

Ka Pui Cheung extended Juno Lee's calendar GET in commit "fix(calendar): require the calendar scope before calling Google".

**Expected behavior.** The README's calendar GET table and the other operations treat a token without the needed scope as 503 `provider_unavailable`, telling the caller to run `scripts/google_calendar_auth.py`.

**Observed.** A token without `calendar.calendars.readonly` reached Google and came back as 403 `access_denied` ("resolve access"). This happened during the #34 verification run, before the shared token was reauthorized.

**Boundary.** Only `GoogleCalendarReader` changed: it checks the scope after loading the token and raises the existing `CalendarMetadataAuthenticationError`, which the route already maps to 503. The route, the `CalendarReader` interface and the response contract did not change.

**Tests.** `test_token_without_calendar_scope_needs_authorization` checks that no client is built and the error is local (`provider=false`). With the check removed, it fails with `DID NOT RAISE CalendarMetadataAuthenticationError`. On the shared account, a token with both scopes still returns 200, and a copy with only `calendar.events` returns 503 with one log line marked `"provider": false`.

## Process observation

**Observation.** The Level 5 reviewer column in `docs/WORK_PLAN.md` said "to be agreed" until the end, so reviews went to whoever was free, and three Level 5 PRs (#30, #32, #33) were approved and merged by the same teammate. Both real defects in this release (deleted events returned by GET, and the stale-scope 403 on calendar GET) were found only by running against the shared Google account; offline tests passed in both cases, and in the first one they asserted the wrong behavior.

**Adjustment.** Name the reviewer when a PR opens, spread reviews across teammates, and have the reviewer run the live workflow on the shared account before approving, recording expected versus actual results in the review.
