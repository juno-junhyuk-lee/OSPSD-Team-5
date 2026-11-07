"""Guard release identity and prevent destructive or unrelated deployments."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts.deploy_release import (
    Release,
    check_plan,
    check_service,
    main,
    read_release,
)

COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
RELEASE = Release(COMMIT, DIGEST, 2, 3)


@pytest.fixture
def plan() -> dict[str, Any]:
    return {
        "complete": True,
        "errored": False,
        "resource_changes": [
            {
                "address": "google_artifact_registry_repository.images",
                "change": {"actions": ["no-op"]},
            },
            {
                "address": "google_cloud_run_v2_service.calendar[0]",
                "change": {
                    "actions": ["update"],
                    "after": {
                        "name": "team5-calendar-verify",
                        "project": "ospsd-team5",
                        "location": "us-central1",
                        "template": [
                            {
                                "containers": [
                                    {
                                        "image": "us-central1-docker.pkg.dev/ospsd-team5/"
                                        f"team5-calendar-verify/calendar@{DIGEST}",
                                        "env": [
                                            {
                                                "name": "CALENDAR_RELEASE",
                                                "value": COMMIT,
                                            }
                                        ],
                                    }
                                ],
                                "volumes": [
                                    {
                                        "name": name,
                                        "secret": [
                                            {
                                                "secret": f"team5-calendar-verify-{name}",
                                                "items": [{"version": version}],
                                            }
                                        ],
                                    }
                                    for name, version in (
                                        ("oauth", "2"),
                                        ("bearer", "3"),
                                    )
                                ],
                            }
                        ],
                    },
                },
            },
        ],
    }


@pytest.mark.parametrize("actions", [["update"], ["no-op"]])
def test_accepts_existing_service_release(
    plan: dict[str, Any], actions: list[str]
) -> None:
    plan["resource_changes"][1]["change"]["actions"] = actions
    check_plan(plan, RELEASE, "ospsd-team5", "verify")


@pytest.mark.parametrize(
    "actions", [["create"], ["delete"], ["delete", "create"], ["create", "delete"]]
)
def test_rejects_service_creation_deletion_or_replacement(
    plan: dict[str, Any], actions: list[str]
) -> None:
    plan["resource_changes"][1]["change"]["actions"] = actions
    with pytest.raises(ValueError, match="existing service"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")


@pytest.mark.parametrize("actions", [["update"], ["create"], ["delete"]])
def test_rejects_foundation_changes(plan: dict[str, Any], actions: list[str]) -> None:
    plan["resource_changes"][0]["change"]["actions"] = actions
    with pytest.raises(ValueError, match="Foundation changes"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("name", "team5-calendar-demo"),
        ("project", "another-project"),
        ("location", "europe-west1"),
    ],
)
def test_rejects_wrong_target(plan: dict[str, Any], key: str, value: str) -> None:
    plan["resource_changes"][1]["change"]["after"][key] = value
    with pytest.raises(ValueError, match="deployment target"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")


def test_rejects_mutable_image_tag(plan: dict[str, Any]) -> None:
    container = plan["resource_changes"][1]["change"]["after"]["template"][0][
        "containers"
    ][0]
    container["image"] = "us-central1-docker.pkg.dev/ospsd-team5/repo/calendar:latest"
    with pytest.raises(ValueError, match="exact built image digest"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")


def test_rejects_wrong_commit(plan: dict[str, Any]) -> None:
    template = plan["resource_changes"][1]["change"]["after"]["template"][0]
    template["containers"][0]["env"][0]["value"] = "c" * 40
    with pytest.raises(ValueError, match="selected commit"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")


@pytest.mark.parametrize("wrong_secret", [True, False])
def test_rejects_wrong_secret_reference(
    plan: dict[str, Any], wrong_secret: bool
) -> None:
    secret = plan["resource_changes"][1]["change"]["after"]["template"][0]["volumes"][
        0
    ]["secret"][0]
    if wrong_secret:
        secret["secret"] = "team5-calendar-demo-oauth"
    else:
        secret["items"][0]["version"] = "latest"
    with pytest.raises(ValueError, match="secret references"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")


@pytest.mark.parametrize("field", ["errored", "complete"])
def test_rejects_incomplete_or_errored_plan(plan: dict[str, Any], field: str) -> None:
    plan[field] = field == "errored"
    with pytest.raises(ValueError, match="complete and error-free"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")


def test_rejects_absent_or_duplicate_service(plan: dict[str, Any]) -> None:
    duplicate = deepcopy(plan["resource_changes"][1])
    plan["resource_changes"].append(duplicate)
    with pytest.raises(ValueError):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")
    plan["resource_changes"] = []
    with pytest.raises(ValueError, match="must be present"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")


@pytest.mark.parametrize(
    ("commit", "digest", "oauth", "bearer"),
    [
        ("main", DIGEST, 1, 1),
        (COMMIT, "latest", 1, 1),
        (COMMIT, DIGEST, 0, 1),
        (COMMIT, DIGEST, 1, -1),
        (COMMIT, DIGEST, True, 1),
    ],
)
def test_rejects_invalid_release(
    commit: str, digest: str, oauth: int, bearer: int
) -> None:
    with pytest.raises(ValueError):
        Release(commit, digest, oauth, bearer)


def test_prepare_manifest_and_check_plan_cli(
    plan: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_path = tmp_path / "release.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "deploy_release",
            "prepare",
            "--commit",
            COMMIT,
            "--digest",
            DIGEST,
            "--oauth-version",
            "2",
            "--bearer-version",
            "3",
            "--output",
            str(release_path),
        ],
    )
    assert main() == 0
    assert read_release(release_path) == RELEASE
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "deploy_release",
            "check-plan",
            "--plan",
            str(plan_path),
            "--release",
            str(release_path),
            "--project",
            "ospsd-team5",
            "--environment",
            "verify",
        ],
    )
    assert main() == 0


def test_cli_rejects_malformed_plan_without_echoing_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    release_path = tmp_path / "release.json"
    release_path.write_text(
        json.dumps(
            {
                "release": {
                    "commit": COMMIT,
                    "digest": DIGEST,
                    "oauth_version": 2,
                    "bearer_version": 3,
                }
            }
        ),
        encoding="utf-8",
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("private-provider-response", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "deploy_release",
            "check-plan",
            "--plan",
            str(plan_path),
            "--release",
            str(release_path),
            "--project",
            "ospsd-team5",
            "--environment",
            "verify",
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "private-provider-response" not in capsys.readouterr().err


@pytest.fixture
def running_service() -> dict[str, Any]:
    revision = "team5-calendar-verify-00002-abc"
    return {
        "metadata": {"name": "team5-calendar-verify"},
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "image": "us-central1-docker.pkg.dev/ospsd-team5/"
                            f"team5-calendar-verify/calendar@{DIGEST}",
                            "env": [{"name": "CALENDAR_RELEASE", "value": COMMIT}],
                        }
                    ]
                }
            }
        },
        "status": {
            "latestCreatedRevisionName": revision,
            "latestReadyRevisionName": revision,
            "traffic": [{"revisionName": revision, "percent": 100}],
        },
    }


def test_accepts_matching_running_release(running_service: dict[str, Any]) -> None:
    assert check_service(running_service, RELEASE, "ospsd-team5", "verify") == (
        "team5-calendar-verify-00002-abc"
    )


@pytest.mark.parametrize(
    "defect", ["target", "image", "commit", "not-ready", "traffic"]
)
def test_rejects_stale_or_misdirected_smoke_target(
    running_service: dict[str, Any], defect: str
) -> None:
    if defect == "target":
        running_service["metadata"]["name"] = "team5-calendar-demo"
    elif defect == "image":
        running_service["spec"]["template"]["spec"]["containers"][0]["image"] = "other"
    elif defect == "commit":
        running_service["spec"]["template"]["spec"]["containers"][0]["env"][0][
            "value"
        ] = "c" * 40
    elif defect == "not-ready":
        running_service["status"]["latestCreatedRevisionName"] = (
            "new-not-ready-revision"
        )
    else:
        running_service["status"]["traffic"] = [
            {
                "revisionName": "team5-calendar-verify-00001-old",
                "percent": 100,
            }
        ]
    with pytest.raises(ValueError):
        check_service(running_service, RELEASE, "ospsd-team5", "verify")


@pytest.mark.parametrize("percent", [0, 50])
def test_rejects_incomplete_traffic_allocation(
    running_service: dict[str, Any], percent: int
) -> None:
    running_service["status"]["traffic"][0]["percent"] = percent
    with pytest.raises(ValueError, match="All service traffic"):
        check_service(running_service, RELEASE, "ospsd-team5", "verify")


def test_running_service_cli(
    running_service: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    release_path = tmp_path / "release.json"
    release_path.write_text(
        json.dumps(
            {
                "release": {
                    "commit": COMMIT,
                    "digest": DIGEST,
                    "oauth_version": 2,
                    "bearer_version": 3,
                }
            }
        ),
        encoding="utf-8",
    )
    service_path = tmp_path / "service.json"
    service_path.write_text(json.dumps(running_service), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "deploy_release",
            "check-service",
            "--service",
            str(service_path),
            "--release",
            str(release_path),
            "--project",
            "ospsd-team5",
            "--environment",
            "verify",
        ],
    )
    assert main() == 0
    assert capsys.readouterr().out.strip() == "team5-calendar-verify-00002-abc"
