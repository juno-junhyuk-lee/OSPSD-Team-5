# Team 5 Calendar implementation

`team5-calendar` supplies Team 5's Google Calendar implementation of the shared
`calendar-contract` interface. Import it as `team5_calendar` inside your own
Python API service. Python 3.14 or newer is required.

The four shared methods, models, and errors remain defined by
[`calendar-contract` v0.1.0](https://github.com/Airbus-A330/OSPSD-Calendar/tree/v0.1.0).
This package supplies the Google behavior; installing only the contract does
not install the implementation. The implementation runs with your own Google
test account and externally supplied OAuth token file.

## Install and configure

The stable-contract candidate is committed and pushed at
[`d19165f9b5e17ed5b63f1d21328513d61334da46`](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/commit/d19165f9b5e17ed5b63f1d21328513d61334da46)
and is under review in [PR #57](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/57).
Install that fixed candidate with:

```sh
pip install "team5-calendar @ git+https://github.com/juno-junhyuk-lee/OSPSD-Team-5.git@d19165f9b5e17ed5b63f1d21328513d61334da46#subdirectory=packages/team5-calendar"
```

No implementation release tag has been published. Earlier pinned-commit
installation and live Google evidence used `rc.1`; those records do not establish
a new stable-contract live run. See the [verification record](../../docs/CALENDAR_PACKAGE_VERIFICATION.md)
for each check's revision and scope.

To test local changes instead, build and install a wheel from the repository root:

```sh
uv build --wheel packages/team5-calendar --out-dir /tmp/team5-calendar-dist
pip install /tmp/team5-calendar-dist/team5_calendar-0.1.0-py3-none-any.whl
```

The implementation declares its tagged shared-contract dependency, so a clean
installer can resolve it without inheriting Team 5's uv configuration. If your
project also declares the contract, use the same stable source. For uv:

```toml
[tool.uv.sources]
calendar-contract = { git = "https://github.com/Airbus-A330/OSPSD-Calendar.git", rev = "v0.1.0" }
```

Using `rev` matches the direct Git reference in this package's metadata. No
dependency override is needed when both declarations resolve to that revision.

The intended immutable implementation tag is `team5-calendar-v0.1.0`. The command
below is for use **after** that tag is published; it is not available yet:

```sh
pip install "team5-calendar @ git+https://github.com/juno-junhyuk-lee/OSPSD-Team-5.git@team5-calendar-v0.1.0#subdirectory=packages/team5-calendar"
```

Enable Google Calendar API in your Google Cloud project, configure a Desktop
OAuth client, and authorize a dedicated test account. Keep the client JSON and
token outside source control. For an OAuth app in Testing, add that account to
the app's test-user list before authorization.

```sh
python -m team5_calendar.authorize \
  --client-secrets /absolute/private/credentials.json \
  --token-file /absolute/private/token.json
```

Only this explicit setup command opens a browser. Provider operations never
start interactive authorization. The service factory accepts the external token
path; runtime refresh stays in memory and does not write into the installed
package directory.

## Use the shared interface

```python
from calendar_contract import CalendarService, CreateEvent
from team5_calendar import create_calendar_service

calendar: CalendarService = create_calendar_service(
    token_file="/absolute/private/token.json"
)

created = calendar.create(
    CreateEvent(
        title="Disposable integration check",
        start="2030-01-07T15:00:00Z",
        end="2030-01-07T15:30:00Z",
    )
)
try:
    observed = calendar.get(created.id)
    assert observed.id == created.id
finally:
    calendar.delete(created.id)
```

This example changes your configured account's primary calendar. Calls return
shared `Event` objects or raise shared `CalendarError`; no Team 5 HTTP bearer
token or separately running Team 5 server is required. Creation is not
idempotent: never automatically repeat an uncertain create or replacement.
If creation fails before returning an ID, inspect Google for the uniquely named
test event before trying again.

See the [consumer and verification guide](../../docs/CALENDAR_PACKAGE.md) for
all four operations, error handling, local wheel testing, and release status.
