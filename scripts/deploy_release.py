"""Prepare release references and reject unsafe Terraform deployment plans."""

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TRUSTED_BRANCHES = {"hw2/milestone-3-level-2", "hw2/milestone-3", "main"}


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


def check_service(
    service: dict[str, Any], release: Release, project: str, environment: str
) -> str:
    """Check Cloud Run v1 describe output before trusting a smoke result."""
    if environment not in {"demo", "verify"}:
        raise ValueError("Unsupported deployment environment")
    name = f"team5-calendar-{environment}"
    status = service["status"]
    revision = status["latestReadyRevisionName"]
    if (
        service["metadata"]["name"] != name
        or not isinstance(revision, str)
        or not revision.startswith(f"{name}-")
        or status["latestCreatedRevisionName"] != revision
    ):
        raise ValueError("The selected service's latest revision must be ready")
    containers = service["spec"]["template"]["spec"]["containers"]
    expected = f"us-central1-docker.pkg.dev/{project}/{name}/calendar@{release.digest}"
    if len(containers) != 1 or containers[0]["image"] != expected:
        raise ValueError("The running template must use the selected image digest")
    settings = {entry["name"]: entry.get("value") for entry in containers[0]["env"]}
    if settings.get("CALENDAR_RELEASE") != release.commit:
        raise ValueError("The running release must match the selected commit")
    traffic = status["traffic"]
    if sum(route.get("percent", 0) for route in traffic) != 100 or any(
        route.get("percent", 0) > 0 and route.get("revisionName") != revision
        for route in traffic
    ):
        raise ValueError("All service traffic must reach the selected ready revision")
    return revision


def select_rollback_artifact(
    run: dict[str, Any], artifacts: dict[str, Any], repository: str, environment: str
) -> dict[str, Any]:
    """Accept evidence only from a successful trusted deployment workflow."""
    if (
        environment not in {"demo", "verify"}
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("event") not in {"push", "workflow_dispatch"}
        or run.get("head_branch") not in TRUSTED_BRANCHES
        or str(run.get("path", "")).split("@", 1)[0] != ".github/workflows/deploy.yml"
        or run.get("repository", {}).get("full_name") != repository
        or run.get("head_repository", {}).get("full_name") != repository
    ):
        raise ValueError("Rollback requires a successful trusted deployment run")
    for field in ("id", "run_attempt"):
        if type(run.get(field)) is not int or run[field] < 1:
            raise ValueError("Invalid source run identity")
    if not re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]):
        raise ValueError("Invalid source workflow commit")
    entries = artifacts["artifacts"]
    if artifacts["total_count"] != len(entries):
        raise ValueError("A complete source artifact listing is required")
    name = f"verified-release-{environment}-{run['head_sha']}-{run['run_attempt']}"
    matches = [artifact for artifact in entries if artifact.get("name") == name]
    if len(matches) != 1:
        raise ValueError("Exactly one verified release artifact must match the run")
    artifact = matches[0]
    if (
        artifact.get("expired") is not False
        or type(artifact.get("id")) is not int
        or artifact["id"] < 1
        or not 0 < artifact.get("size_in_bytes", 0) <= 65536
    ):
        raise ValueError("The source artifact must be available and bounded in size")
    return {
        "artifact_name": name,
        "artifact_id": artifact["id"],
        "run_id": run["id"],
        "run_attempt": run["run_attempt"],
        "workflow_commit": run["head_sha"],
    }


def prepare_rollback(
    document: dict[str, Any], selection: dict[str, Any], project: str, environment: str
) -> tuple[Release, str]:
    """Restore release inputs and configuration source without trusting artifact code."""
    release = Release(**document["release"])
    name = f"team5-calendar-{environment}"
    if (
        environment not in {"demo", "verify"}
        or document.get("verified") is not True
        or document.get("project") != project
        or document.get("environment") != environment
        or document.get("image")
        != f"us-central1-docker.pkg.dev/{project}/{name}/calendar@{release.digest}"
        or not str(document.get("revision", "")).startswith(f"{name}-")
        or any(
            document.get(field) != selection[field]
            for field in ("run_id", "run_attempt", "workflow_commit")
        )
    ):
        raise ValueError("The verified artifact must match its source run and target")
    configuration_commit = document["configuration_commit"]
    if not isinstance(configuration_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", configuration_commit
    ):
        raise ValueError("A pinned configuration commit is required")
    operation = document.get("operation")
    if operation == "deploy":
        if (
            release.commit != selection["workflow_commit"]
            or configuration_commit != selection["workflow_commit"]
        ):
            raise ValueError("A deployment artifact must match its checked commit")
    elif operation == "rollback":
        if (
            type(document.get("rollback_source_run_id")) is not int
            or document["rollback_source_run_id"] < 1
        ):
            raise ValueError("A rollback artifact must record its source run")
    else:
        raise ValueError("Unknown source release operation")
    return release, configuration_commit


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
    running = commands.add_parser("check-service")
    running.add_argument("--service", type=Path, required=True)
    running.add_argument("--release", type=Path, required=True)
    running.add_argument("--project", required=True)
    running.add_argument("--environment", choices=["demo", "verify"], required=True)
    select = commands.add_parser("select-rollback")
    select.add_argument("--run", type=Path, required=True)
    select.add_argument("--artifacts", type=Path, required=True)
    select.add_argument("--repository", required=True)
    select.add_argument("--environment", choices=["demo", "verify"], required=True)
    select.add_argument("--output", type=Path, required=True)
    rollback = commands.add_parser("prepare-rollback")
    rollback.add_argument("--artifact", type=Path, required=True)
    rollback.add_argument("--selection", type=Path, required=True)
    rollback.add_argument("--project", required=True)
    rollback.add_argument("--environment", choices=["demo", "verify"], required=True)
    rollback.add_argument("--output", type=Path, required=True)
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
        elif args.command == "check-plan":
            check_plan(
                json.loads(args.plan.read_text(encoding="utf-8")),
                read_release(args.release),
                args.project,
                args.environment,
            )
        elif args.command == "check-service":
            print(
                check_service(
                    json.loads(args.service.read_text(encoding="utf-8")),
                    read_release(args.release),
                    args.project,
                    args.environment,
                )
            )
        elif args.command == "select-rollback":
            selection = select_rollback_artifact(
                json.loads(args.run.read_text(encoding="utf-8")),
                json.loads(args.artifacts.read_text(encoding="utf-8")),
                args.repository,
                args.environment,
            )
            args.output.write_text(json.dumps(selection) + "\n", encoding="utf-8")
        else:
            release, configuration_commit = prepare_rollback(
                json.loads(args.artifact.read_text(encoding="utf-8")),
                json.loads(args.selection.read_text(encoding="utf-8")),
                args.project,
                args.environment,
            )
            args.output.write_text(
                json.dumps({"release": asdict(release)}, indent=2) + "\n",
                encoding="utf-8",
            )
            print(configuration_commit)
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        OSError,
    ) as error:
        # Do not echo malformed plan values, state, or provider responses.
        parser.exit(1, f"Release deployment rejected ({type(error).__name__}).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
