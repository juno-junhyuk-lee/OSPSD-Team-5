"""Reject untrusted rollback evidence and preserve verified release inputs."""

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.deploy_release import (
    Release,
    main,
    prepare_rollback,
    read_release,
    select_rollback_artifact,
)

REPOSITORY = "juno-junhyuk-lee/OSPSD-Team-5"
COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
ARTIFACT_NAME = f"verified-release-verify-{COMMIT}-1"


@pytest.fixture
def source_run() -> dict[str, Any]:
    return {
        "id": 42,
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "head_branch": "hw2/milestone-3-level-2",
        "head_sha": COMMIT,
        "path": ".github/workflows/deploy.yml",
        "repository": {"full_name": REPOSITORY},
        "head_repository": {"full_name": REPOSITORY},
    }


@pytest.fixture
def source_artifacts() -> dict[str, Any]:
    return {
        "total_count": 1,
        "artifacts": [
            {
                "id": 99,
                "name": ARTIFACT_NAME,
                "expired": False,
                "size_in_bytes": 500,
            }
        ],
    }


@pytest.fixture
def selection() -> dict[str, Any]:
    return {
        "artifact_name": ARTIFACT_NAME,
        "artifact_id": 99,
        "run_id": 42,
        "run_attempt": 1,
        "workflow_commit": COMMIT,
    }


@pytest.fixture
def verified_release() -> dict[str, Any]:
    return {
        "release": {
            "commit": COMMIT,
            "digest": DIGEST,
            "oauth_version": 2,
            "bearer_version": 3,
        },
        "project": "ospsd-team5",
        "environment": "verify",
        "image": f"us-central1-docker.pkg.dev/ospsd-team5/team5-calendar-verify/calendar@{DIGEST}",
        "revision": "team5-calendar-verify-00002-abc",
        "verified": True,
        "operation": "deploy",
        "configuration_commit": COMMIT,
        "workflow_commit": COMMIT,
        "run_id": 42,
        "run_attempt": 1,
        "rollback_source_run_id": None,
    }


def test_selects_exact_verified_artifact(
    source_run: dict[str, Any],
    source_artifacts: dict[str, Any],
    selection: dict[str, Any],
) -> None:
    assert (
        select_rollback_artifact(source_run, source_artifacts, REPOSITORY, "verify")
        == selection
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "in_progress"),
        ("conclusion", "failure"),
        ("event", "pull_request"),
        ("event", "workflow_run"),
        ("head_branch", "unreviewed-feature"),
        ("path", ".github/workflows/checks.yml"),
        ("repository", {"full_name": "outsider/OSPSD-Team-5"}),
        ("head_repository", {"full_name": "outsider/OSPSD-Team-5"}),
        ("id", 0),
        ("run_attempt", 0),
        ("head_sha", "main"),
    ],
)
def test_rejects_untrusted_or_invalid_source_run(
    source_run: dict[str, Any],
    source_artifacts: dict[str, Any],
    field: str,
    value: object,
) -> None:
    source_run[field] = value
    with pytest.raises(ValueError):
        select_rollback_artifact(source_run, source_artifacts, REPOSITORY, "verify")


@pytest.mark.parametrize(
    "defect",
    [
        "expired",
        "oversized",
        "missing",
        "duplicate",
        "incomplete-list",
        "wrong-attempt",
    ],
)
def test_rejects_unavailable_or_ambiguous_artifact(
    source_run: dict[str, Any],
    source_artifacts: dict[str, Any],
    defect: str,
) -> None:
    artifact = source_artifacts["artifacts"][0]
    if defect == "expired":
        artifact["expired"] = True
    elif defect == "oversized":
        artifact["size_in_bytes"] = 65537
    elif defect == "missing":
        source_artifacts.update(total_count=0, artifacts=[])
    elif defect == "duplicate":
        source_artifacts["artifacts"].append(dict(artifact))
        source_artifacts["total_count"] = 2
    elif defect == "incomplete-list":
        source_artifacts["total_count"] = 101
    else:
        artifact["name"] = f"verified-release-verify-{COMMIT}-2"
    with pytest.raises(ValueError):
        select_rollback_artifact(source_run, source_artifacts, REPOSITORY, "verify")


def test_restores_original_digest_secret_versions_and_configuration(
    verified_release: dict[str, Any],
    selection: dict[str, Any],
) -> None:
    release, configuration = prepare_rollback(
        verified_release, selection, "ospsd-team5", "verify"
    )
    assert release == Release(COMMIT, DIGEST, 2, 3)
    assert configuration == COMMIT


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("verified", False),
        ("verified", "true"),
        ("project", "another-project"),
        ("environment", "demo"),
        ("image", "calendar:latest"),
        ("revision", "team5-calendar-demo-00001-abc"),
        ("run_id", 43),
        ("run_attempt", 2),
        ("workflow_commit", "c" * 40),
        ("configuration_commit", "main"),
        ("configuration_commit", "d" * 40),
        ("operation", "unknown"),
    ],
)
def test_rejects_forged_unverified_or_mismatched_release(
    verified_release: dict[str, Any],
    selection: dict[str, Any],
    field: str,
    value: object,
) -> None:
    verified_release[field] = value
    with pytest.raises(ValueError):
        prepare_rollback(verified_release, selection, "ospsd-team5", "verify")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commit", "c" * 40),
        ("digest", "latest"),
        ("oauth_version", 0),
        ("bearer_version", True),
    ],
)
def test_rejects_invalid_or_unrelated_release_inputs(
    verified_release: dict[str, Any],
    selection: dict[str, Any],
    field: str,
    value: object,
) -> None:
    verified_release["release"][field] = value
    with pytest.raises(ValueError):
        prepare_rollback(verified_release, selection, "ospsd-team5", "verify")


def test_can_restore_a_release_verified_by_an_earlier_rollback(
    verified_release: dict[str, Any],
    selection: dict[str, Any],
) -> None:
    verified_release.update(
        operation="rollback", rollback_source_run_id=41, configuration_commit="c" * 40
    )
    verified_release["release"]["commit"] = "d" * 40
    release, configuration = prepare_rollback(
        verified_release, selection, "ospsd-team5", "verify"
    )
    assert release.commit == "d" * 40
    assert release.digest == DIGEST
    assert configuration == "c" * 40
    verified_release["rollback_source_run_id"] = None
    with pytest.raises(ValueError):
        prepare_rollback(verified_release, selection, "ospsd-team5", "verify")


def test_rollback_cli_writes_only_pinned_release_inputs(
    source_run: dict[str, Any],
    source_artifacts: dict[str, Any],
    verified_release: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name, value in (
        ("run", source_run),
        ("artifacts", source_artifacts),
        ("release", verified_release),
    ):
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    selection_path = tmp_path / "selection.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "deploy_release",
            "select-rollback",
            "--run",
            str(tmp_path / "run.json"),
            "--artifacts",
            str(tmp_path / "artifacts.json"),
            "--repository",
            REPOSITORY,
            "--environment",
            "verify",
            "--output",
            str(selection_path),
        ],
    )
    assert main() == 0
    output_path = tmp_path / "release.tfvars.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "deploy_release",
            "prepare-rollback",
            "--artifact",
            str(tmp_path / "release.json"),
            "--selection",
            str(selection_path),
            "--project",
            "ospsd-team5",
            "--environment",
            "verify",
            "--output",
            str(output_path),
        ],
    )
    assert main() == 0
    assert capsys.readouterr().out.strip() == COMMIT
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "release": verified_release["release"]
    }
    assert read_release(output_path) == Release(COMMIT, DIGEST, 2, 3)
