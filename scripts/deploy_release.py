"""Prepare release references and reject unsafe Terraform deployment plans."""

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Release:
    commit: str
    digest: str
    oauth_version: int
    bearer_version: int

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            raise ValueError("A full lowercase commit SHA is required")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.digest):
            raise ValueError("An immutable sha256 image digest is required")
        if any(
            type(version) is not int or version < 1
            for version in (self.oauth_version, self.bearer_version)
        ):
            raise ValueError("Secret versions must be positive integers")


def read_release(path: Path) -> Release:
    document = json.loads(path.read_text(encoding="utf-8"))
    return Release(**document["release"])


def check_plan(
    plan: dict[str, Any], release: Release, project: str, environment: str
) -> None:
    if environment not in {"demo", "verify"}:
        raise ValueError("Unsupported deployment environment")
    if plan.get("errored") or plan.get("complete") is not True:
        raise ValueError("The deployment plan must be complete and error-free")
    name = f"team5-calendar-{environment}"
    image = f"us-central1-docker.pkg.dev/{project}/{name}/calendar@{release.digest}"
    changes = plan.get("resource_changes")
    if not isinstance(changes, list):
        raise ValueError("The deployment plan must contain resource changes")
    service = None
    for resource in changes:
        change = resource["change"]
        if resource["address"] == "google_cloud_run_v2_service.calendar[0]":
            if service is not None or change["actions"] not in (["update"], ["no-op"]):
                raise ValueError("Only updates to an existing service are permitted")
            service = change["after"]
        elif change["actions"] != ["no-op"]:
            raise ValueError("Foundation changes require a separate administrator plan")
    if not isinstance(service, dict):
        raise ValueError("The existing Calendar service must be present in the plan")
    if (
        service.get("name") != name
        or service.get("project") != project
        or service.get("location") != "us-central1"
    ):
        raise ValueError("The service does not match the selected deployment target")
    template = service["template"][0]
    containers = template["containers"]
    if len(containers) != 1 or containers[0]["image"] != image:
        raise ValueError("The service must use the exact built image digest")
    settings = {entry["name"]: entry.get("value") for entry in containers[0]["env"]}
    if settings.get("CALENDAR_RELEASE") != release.commit:
        raise ValueError("The service release does not match the selected commit")
    volumes = {volume["name"]: volume["secret"][0] for volume in template["volumes"]}
    for secret, version in (
        ("oauth", release.oauth_version),
        ("bearer", release.bearer_version),
    ):
        value = volumes[secret]
        if value["secret"] != f"{name}-{secret}" or value["items"][0]["version"] != str(
            version
        ):
            raise ValueError("The service secret references do not match the release")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--commit", required=True)
    prepare.add_argument("--digest", required=True)
    prepare.add_argument("--oauth-version", type=int, required=True)
    prepare.add_argument("--bearer-version", type=int, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("check-plan")
    check.add_argument("--plan", type=Path, required=True)
    check.add_argument("--release", type=Path, required=True)
    check.add_argument("--project", required=True)
    check.add_argument("--environment", choices=["demo", "verify"], required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            release = Release(
                args.commit, args.digest, args.oauth_version, args.bearer_version
            )
            args.output.write_text(
                json.dumps({"release": asdict(release)}, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            check_plan(
                json.loads(args.plan.read_text(encoding="utf-8")),
                read_release(args.release),
                args.project,
                args.environment,
            )
    except (ValueError, TypeError, KeyError, IndexError, OSError) as error:
        # Do not echo malformed plan values, state, or provider responses.
        parser.exit(1, f"Release deployment rejected ({type(error).__name__}).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
