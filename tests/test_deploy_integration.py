"""Release checks for the HW3 workflow settings and pinned credential versions."""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from scripts.deploy_release import (
    INTEGRATION_SECRETS,
    Integration,
    Release,
    check_plan,
    check_service,
    main,
    prepare_rollback,
    read_integration,
)

COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
RELEASE = Release(COMMIT, DIGEST, 2, 3)
NAME = "team5-calendar-verify"
VERSIONS = {secret: index + 4 for index, secret in enumerate(INTEGRATION_SECRETS)}
INTEGRATION = Integration("team3_dropbox", "/ospsd-team5-hw3", "0" * 24, VERSIONS)
IMAGE = f"us-central1-docker.pkg.dev/ospsd-team5/{NAME}/calendar@{DIGEST}"


def settings_env(integration: Integration) -> list[dict[str, Any]]:
    return [
        {"name": key, "value": value} for key, value in integration.settings().items()
    ]


def plan_env(integration: Integration) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = [{"name": "CALENDAR_RELEASE", "value": COMMIT}]
    entries += settings_env(integration)
    for secret, variable in INTEGRATION_SECRETS.items():
        entries.append(
            {
                "name": variable,
                "value": None,
                "value_source": [
                    {
                        "secret_key_ref": [
                            {
                                "secret": f"{NAME}-{secret.replace('_', '-')}",
                                "version": str(integration.secret_versions[secret]),
                            }
                        ]
                    }
                ],
            }
        )
    return entries


def service_env(integration: Integration) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = [{"name": "CALENDAR_RELEASE", "value": COMMIT}]
    entries += settings_env(integration)
    for secret, variable in INTEGRATION_SECRETS.items():
        entries.append(
            {
                "name": variable,
                "valueFrom": {
                    "secretKeyRef": {
                        "name": f"{NAME}-{secret.replace('_', '-')}",
                        "key": str(integration.secret_versions[secret]),
                    }
                },
            }
        )
    return entries


def plan_for(env: list[dict[str, Any]]) -> dict[str, Any]:
    volumes = [
        {
            "name": name,
            "secret": [{"secret": f"{NAME}-{name}", "items": [{"version": version}]}],
        }
        for name, version in (("oauth", "2"), ("bearer", "3"))
    ]
    service = {
        "name": NAME,
        "project": "ospsd-team5",
        "location": "us-central1",
        "template": [
            {"containers": [{"image": IMAGE, "env": env}], "volumes": volumes}
        ],
    }
    return {
        "complete": True,
        "errored": False,
        "resource_changes": [
            {
                "address": "google_cloud_run_v2_service.calendar[0]",
                "change": {"actions": ["update"], "after": service},
            }
        ],
    }


def service_for(env: list[dict[str, Any]]) -> dict[str, Any]:
    revision = f"{NAME}-00003-abc"
    return {
        "metadata": {"name": NAME},
        "spec": {"template": {"spec": {"containers": [{"image": IMAGE, "env": env}]}}},
        "status": {
            "latestCreatedRevisionName": revision,
            "latestReadyRevisionName": revision,
            "traffic": [{"revisionName": revision, "percent": 100}],
        },
    }


@pytest.mark.parametrize("implementation", ["team3_dropbox", "team1_dropbox"])
def test_accepts_matching_workflow_settings(implementation: str) -> None:
    integration = replace(INTEGRATION, storage_implementation=implementation)
    check_plan(
        plan_for(plan_env(integration)), RELEASE, "ospsd-team5", "verify", integration
    )
    assert (
        check_service(
            service_for(service_env(integration)),
            RELEASE,
            "ospsd-team5",
            "verify",
            integration,
        )
        == f"{NAME}-00003-abc"
    )


def test_storage_swap_changes_only_the_selector() -> None:
    team1 = replace(INTEGRATION, storage_implementation="team1_dropbox")
    before = {entry["name"]: entry for entry in service_env(INTEGRATION)}
    after = {entry["name"]: entry for entry in service_env(team1)}
    assert {key for key in before if before[key] != after[key]} == {
        "STORAGE_IMPLEMENTATION"
    }
    # A Team 3 manifest must not accept a Team 1 service, and vice versa.
    with pytest.raises(ValueError, match="workflow settings"):
        check_service(
            service_for(service_env(team1)),
            RELEASE,
            "ospsd-team5",
            "verify",
            INTEGRATION,
        )


@pytest.mark.parametrize(
    "defect", ["missing", "plain-value", "wrong-version", "latest", "other-secret"]
)
def test_rejects_unpinned_or_mismatched_credentials(defect: str) -> None:
    env = plan_env(INTEGRATION)
    entry = next(item for item in env if item["name"] == "DROPBOX_REFRESH_TOKEN")
    ref = entry["value_source"][0]["secret_key_ref"][0]
    if defect == "missing":
        env.remove(entry)
    elif defect == "plain-value":
        entry["value"] = "not-a-real-token"
    elif defect == "wrong-version":
        ref["version"] = "99"
    elif defect == "latest":
        ref["version"] = "latest"
    else:
        ref["secret"] = "team5-calendar-demo-dropbox-refresh-token"
    with pytest.raises(ValueError, match="secret references"):
        check_plan(plan_for(env), RELEASE, "ospsd-team5", "verify", INTEGRATION)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("STORAGE_IMPLEMENTATION", "team1_dropbox"),
        ("STORAGE_ROOT_PATH", "/other"),
        ("TRELLO_LIST_ID", "1" * 24),
        ("PYTHON_DOTENV_DISABLED", "0"),
        ("ISSUE_TRACKER_IMPLEMENTATION", "other"),
    ],
)
def test_rejects_mismatched_settings(name: str, value: str) -> None:
    env = plan_env(INTEGRATION)
    next(item for item in env if item["name"] == name)["value"] = value
    with pytest.raises(ValueError, match="workflow settings"):
        check_plan(plan_for(env), RELEASE, "ospsd-team5", "verify", INTEGRATION)


def test_release_without_integration_rejects_workflow_settings() -> None:
    plan = plan_for(plan_env(INTEGRATION))
    with pytest.raises(ValueError, match="Unexpected workflow settings"):
        check_plan(plan, RELEASE, "ospsd-team5", "verify")
    check_plan(
        plan_for([{"name": "CALENDAR_RELEASE", "value": COMMIT}]),
        RELEASE,
        "ospsd-team5",
        "verify",
    )


@pytest.mark.parametrize(
    "change",
    [
        {"storage_implementation": "team3_dropbox "},
        {"storage_implementation": "s3"},
        {"storage_root_path": "relative"},
        {"storage_root_path": "/"},
        {"storage_root_path": "/a/../b"},
        {"trello_list_id": "short"},
        {"secret_versions": {**VERSIONS, "trello_token": 0}},
        {"secret_versions": {**VERSIONS, "trello_token": True}},
        {"secret_versions": {k: v for k, v in VERSIONS.items() if k != "trello_token"}},
    ],
)
def test_rejects_invalid_integration(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        replace(INTEGRATION, **change)


def test_prepare_cli_records_integration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    integration_path = tmp_path / "integration.json"
    integration_path.write_text(
        json.dumps(
            {
                "storage_implementation": "team1_dropbox",
                "storage_root_path": "/ospsd-team5-hw3",
                "trello_list_id": "0" * 24,
                "secret_versions": VERSIONS,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "release.tfvars.json"
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
            "--integration",
            str(integration_path),
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    document = json.loads(output.read_text(encoding="utf-8"))
    assert set(document) == {"release", "integration"}
    assert read_integration(output) == replace(
        INTEGRATION, storage_implementation="team1_dropbox"
    )


def test_prepare_cli_without_integration_keeps_hw2_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "release.tfvars.json"
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
            str(output),
        ],
    )
    assert main() == 0
    assert set(json.loads(output.read_text(encoding="utf-8"))) == {"release"}
    assert read_integration(output) is None


def test_rollback_restores_recorded_integration() -> None:
    document: dict[str, Any] = {
        "release": {
            "commit": COMMIT,
            "digest": DIGEST,
            "oauth_version": 2,
            "bearer_version": 3,
        },
        "integration": {
            "storage_implementation": "team3_dropbox",
            "storage_root_path": "/ospsd-team5-hw3",
            "trello_list_id": "0" * 24,
            "secret_versions": VERSIONS,
        },
        "verified": True,
        "project": "ospsd-team5",
        "environment": "verify",
        "image": IMAGE,
        "revision": f"{NAME}-00003-abc",
        "run_id": 42,
        "run_attempt": 1,
        "workflow_commit": COMMIT,
        "configuration_commit": COMMIT,
        "operation": "deploy",
    }
    selection = {"run_id": 42, "run_attempt": 1, "workflow_commit": COMMIT}
    release, integration, _ = prepare_rollback(
        deepcopy(document), selection, "ospsd-team5", "verify"
    )
    assert release == RELEASE
    assert integration == INTEGRATION
    document["integration"]["storage_implementation"] = "unknown"
    with pytest.raises(ValueError):
        prepare_rollback(document, selection, "ospsd-team5", "verify")
