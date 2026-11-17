"""Package probe checks with fake provider state; no Dropbox access."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.storage_package import PackageStorageSettings
from scripts.verify_storage_live import main, verify


@pytest.fixture(autouse=True)
def package_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in tuple(os.environ):
        if key.startswith(("DROPBOX_", "STORAGE_")):
            monkeypatch.delenv(key)
    for key, value in {
        "PYTHON_DOTENV_DISABLED": "1",
        "STORAGE_ROOT_PATH": "/team5-test",
        "DROPBOX_APP_KEY": "test-key",
        "DROPBOX_APP_SECRET": "test-secret",
        "DROPBOX_REFRESH_TOKEN": "test-refresh",
    }.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize(
    "mode",
    [
        "success",
        "existing",
        "conflict",
        "lost_response",
        "unknown_no_write",
        "read_mismatch",
        "cleanup_failure",
        "cleanup_untyped",
        "health_failure",
    ],
)
def test_probe_records_failures_and_only_cleans_its_own_file(mode: str) -> None:
    exists = mode == "existing"
    content = b""
    calls: list[tuple[str, str]] = []

    def info(path: str) -> SimpleNamespace:
        return SimpleNamespace(
            id="file-id",
            name=path.rsplit("/", 1)[1],
            path=path,
            size=len(content),
            modified=None,
            etag=None,
        )

    def upload(local_path: str, path: str, *, overwrite: bool) -> SimpleNamespace:
        nonlocal exists, content
        calls.append(("create", path))
        assert overwrite is False
        if exists or mode == "conflict":
            raise FileExistsError("SECRET")
        content = Path(local_path).read_bytes()
        if mode != "unknown_no_write":
            exists = True
        if mode in {"lost_response", "unknown_no_write"}:
            raise ConnectionError("SECRET")
        return info(path)

    def metadata(path: str) -> SimpleNamespace:
        calls.append(("metadata", path))
        if not exists:
            raise FileNotFoundError("SECRET")
        return info(path)

    def download(path: str, local_path: str) -> SimpleNamespace:
        calls.append(("download", path))
        Path(local_path).write_bytes(b"wrong" if mode == "read_mismatch" else content)
        return info(path)

    def delete(path: str) -> None:
        nonlocal exists
        calls.append(("delete", path))
        if mode == "cleanup_failure":
            raise ConnectionError("SECRET")
        if mode == "cleanup_untyped":
            raise RuntimeError("SECRET")
        if not exists:
            raise FileNotFoundError("SECRET")
        exists = False

    provider = Mock()
    provider.upload_file.side_effect = upload
    provider.download_file.side_effect = download
    provider.get_metadata.side_effect = metadata
    provider.delete.side_effect = delete
    if mode == "health_failure":
        provider.check_health.side_effect = ConnectionError("SECRET")
    with (
        patch("dropbox.Dropbox") as sdk,
        patch("dropbox_client_impl.DropboxClient", return_value=provider),
    ):
        result = verify(PackageStorageSettings.from_environment())
        sdk.return_value.close.assert_called_once_with()
    assert "SECRET" not in str(result)
    assert "test-refresh" not in str(result)
    assert result["integration"] == "Team3 package import"
    assert "base_url" not in result
    assert result["direct_provider_verification"] == "pending"
    assert result["deployed_composed_workflow"] == "not exercised"
    assert all(path == result["path"] for _, path in calls)
    operations = [operation for operation, _ in calls]
    if mode == "success":
        assert result["result"] == "passed"
        for key in (
            "create_and_download_compare",
            "create_conflict",
            "conflict_preserved_bytes",
        ):
            assert result[key] == "passed"
        assert result["cleanup"] == "confirmed absent" and not exists
    elif mode in {"existing", "conflict", "health_failure"}:
        assert result["result"] == "failed"
        assert "delete" not in operations
        if mode == "existing":
            assert "create" not in operations and exists
    elif mode in {"cleanup_failure", "cleanup_untyped"}:
        assert result["result"] == "failed" and result["cleanup"] == "failed"
        assert exists
    else:
        assert result["result"] == "failed"
        assert result["cleanup"] == "confirmed absent"
        assert not exists and operations.count("create") == 1


def test_probe_records_construction_failure() -> None:
    with patch("dropbox.Dropbox", side_effect=ValueError("SECRET")):
        result = verify(PackageStorageSettings.from_environment())
    assert result["result"] == "failed"
    assert result["cleanup"] == "not needed"
    assert "SECRET" not in str(result)


def test_cli_requires_explicit_execute_flag() -> None:
    with patch("sys.argv", ["probe", "--output", "unused.json"]):
        with patch("scripts.verify_storage_live.verify") as run:
            with pytest.raises(SystemExit) as caught:
                main()
    assert caught.value.code == 2
    run.assert_not_called()


def test_cli_refuses_existing_evidence(tmp_path: Path) -> None:
    output = tmp_path / "existing.json"
    output.write_text("original")
    with (
        patch("sys.argv", ["probe", "--execute", "--output", str(output)]),
        patch("scripts.verify_storage_live.verify") as run,
        pytest.raises(FileExistsError),
    ):
        main()
    assert output.read_text() == "original"
    run.assert_not_called()


def test_cli_invalid_configuration_does_not_create_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DROPBOX_APP_KEY")
    output = tmp_path / "evidence.json"
    with (
        patch("sys.argv", ["probe", "--execute", "--output", str(output)]),
        patch("scripts.verify_storage_live.verify") as run,
        pytest.raises(SystemExit),
    ):
        main()
    assert not output.exists()
    run.assert_not_called()


@pytest.mark.parametrize("outcome", ["passed", "failed"])
def test_cli_records_provenance_and_exit_status(tmp_path: Path, outcome: str) -> None:
    output = tmp_path / "evidence.json"
    with (
        patch("sys.argv", ["probe", "--execute", "--output", str(output)]),
        patch(
            "scripts.verify_storage_live.verify",
            return_value={
                "result": outcome,
                "cleanup": "confirmed absent",
            },
        ) as run,
    ):
        if outcome == "failed":
            with pytest.raises(SystemExit) as caught:
                main()
            assert caught.value.code == 1
        else:
            main()
        run.assert_called_once()
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["result"] == outcome
    assert "app/storage_package.py" in evidence["source_sha256"]
    assert "app/storage_paths.py" in evidence["source_sha256"]
    assert (
        evidence["packages"]["dropbox-client-impl"]["direct_url"]["vcs_info"][
            "commit_id"
        ]
        == "fde60d4fb648df6defb918ff815fe940c525adc7"
    )
    assert "test-secret" not in output.read_text(encoding="utf-8")
