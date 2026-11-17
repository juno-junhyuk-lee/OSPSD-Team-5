"""Install a Calendar wheel in an isolated consumer and check its boundary."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

CONTRACT_SOURCE = (
    "calendar-contract @ git+https://github.com/Airbus-A330/OSPSD-Calendar.git@v0.1.0"
)

CONSUMER_CHECK = '''"""Check the installed distribution without Team 5's source tree."""
import json
import sys
from importlib.metadata import distribution
from pathlib import Path

import app
import calendar_contract
import team5_calendar
from calendar_contract import CalendarError, CreateEvent, ErrorCode, ReplaceEvent
from team5_calendar import create_calendar_service

assert app.SENTINEL == "consumer-owned-app"
repository = Path(__TEAM5_REPOSITORY__).resolve()
assert all(
    not Path(entry or ".").resolve().is_relative_to(repository)
    for entry in sys.path
)
for module in (team5_calendar, calendar_contract):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert not any(
    name == "fastapi" or name.startswith("fastapi.")
    or name == "opentelemetry.sdk" or name.startswith("opentelemetry.sdk.")
    or name == "app.main"
    for name in sys.modules
)
assert distribution("team5-calendar").version == "0.1.0"
contract = distribution("calendar-contract")
assert contract.version == "0.1.0"
source = json.loads(contract.read_text("direct_url.json") or "{}")
assert source["vcs_info"]["commit_id"] == "db73e6261a93b0c3cc6aa0a48c4687f742aacc9b"

def deny_provider_network(event, args):
    if event == "socket.connect":
        raise AssertionError("Missing authorization attempted provider network access")

sys.addaudithook(deny_provider_network)
request = CreateEvent(
    title="Isolated consumer check",
    start="2030-01-07T15:00:00Z",
    end="2030-01-07T15:30:00Z",
)
malformed = Path("malformed-token.json").resolve()
malformed.write_text("{}", encoding="utf-8")
checked = 0
for token_file in (Path("absent-token.json").resolve(), malformed):
    service = create_calendar_service(token_file=token_file)
    operations = (
        lambda: service.create(request),
        lambda: service.get("unknown-event"),
        lambda: service.replace("unknown-event", ReplaceEvent(**request.model_dump())),
        lambda: service.delete("unknown-event"),
    )
    for operation in operations:
        try:
            operation()
        except CalendarError as error:
            assert error.code == ErrorCode.PROVIDER_UNAVAILABLE
            assert error.retryable is False
            checked += 1
        else:
            raise AssertionError("Missing authorization was accepted")
assert checked == 8
assert not Path("absent-token.json").exists()
print(json.dumps({
    "step": "isolated_consumer",
    "passed": True,
    "own_app_preserved": True,
    "installed_modules": True,
    "framework_independent": True,
    "authorization_checks": checked,
    "contract_commit": source["vcs_info"]["commit_id"],
}))
'''


def inspect_wheel(wheel: Path) -> None:
    """Reject accidental application, infrastructure, or credential inclusion."""
    with ZipFile(wheel) as archive:
        names = archive.namelist()
    roots = {name.split("/", 1)[0] for name in names}
    metadata_roots = {root for root in roots if root.endswith(".dist-info")}
    if len(metadata_roots) != 1 or roots != {"team5_calendar", *metadata_roots}:
        raise ValueError("Wheel must contain only team5_calendar and its metadata.")
    if "team5_calendar/py.typed" not in names:
        raise ValueError("Wheel is missing its py.typed marker.")
    for name in names:
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or path.name.lower() in {"token.json", "credentials.json", ".env"}
            or path.suffix.lower() in {".pem", ".key"}
        ):
            raise ValueError("Wheel contains an unsafe path or credential file.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--uv", default="uv", help="Path to the uv executable")
    parser.add_argument("--installer", choices=("uv", "pip"), default="uv")
    args = parser.parse_args()
    wheel: Path = args.wheel.resolve()
    inspect_wheel(wheel)
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        environment.pop(name, None)
    repository = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="team5-calendar-consumer-") as temporary:
        consumer = Path(temporary)
        python = consumer / ".venv" / "bin" / "python"
        create_environment = [
            args.uv,
            "venv",
            str(consumer / ".venv"),
            "--python",
            sys.executable,
        ]
        if args.installer == "pip":
            create_environment.append("--seed")
        subprocess.run(
            create_environment,
            cwd=consumer,
            env=environment,
            check=True,
        )
        if args.installer == "uv":
            # Resolve a consumer that explicitly depends on both distributions.
            dependencies = ["team5-calendar @ " + wheel.as_uri(), CONTRACT_SOURCE]
            (consumer / "pyproject.toml").write_text(
                '[project]\nname = "calendar-consumer-check"\nversion = "0.0.0"\n'
                'requires-python = ">=3.14"\ndependencies = '
                + json.dumps(dependencies)
                + "\n",
                encoding="utf-8",
            )
            commands = [
                [args.uv, "lock", "--python", sys.executable],
                [args.uv, "sync", "--frozen", "--python", sys.executable],
            ]
        else:
            commands = [
                [str(python), "-m", "pip", "install", str(wheel), CONTRACT_SOURCE]
            ]
        for command in commands:
            subprocess.run(command, cwd=consumer, env=environment, check=True)
        (consumer / "app").mkdir()
        (consumer / "app" / "__init__.py").write_text(
            'SENTINEL = "consumer-owned-app"\n', encoding="utf-8"
        )
        (consumer / "check.py").write_text(
            CONSUMER_CHECK.replace("__TEAM5_REPOSITORY__", repr(str(repository))),
            encoding="utf-8",
        )
        subprocess.run(
            [str(python), "check.py"],
            cwd=consumer,
            env=environment,
            check=True,
        )
    print(
        json.dumps(
            {
                "step": "wheel_boundary",
                "passed": True,
                "wheel": wheel.name,
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "installer": args.installer,
                "explicit_contract_dependency": True,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
