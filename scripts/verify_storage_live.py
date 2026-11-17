"""Opt-in summary upload, readback, conflict and cleanup verification.

Set package credentials and STORAGE_ROOT_PATH as in docs/HW3_STORAGE_AUTH.md.
Run with python -m scripts.verify_storage_live
--execute --output <evidence.json>. Creates/deletes one UUID-named file, leaving
the configured folder intact. Direct provider inspection is a separate check.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import distribution
from pathlib import Path
from uuid import uuid4

from cloud_storage_api import ConflictError, NotFoundError

from app.storage_package import PackageStorageSettings, package_document_storage
from app.summary_storage import DocumentSummaryStore, SummaryStorageError


def verify(settings: PackageStorageSettings) -> dict[str, object]:
    root = settings.root_path
    name = f"team5-hw3-{uuid4().hex}.md"
    path = root + "/" + name
    markdown = f"# Team 5 storage verification\n\nFile: {name}\nUTF-8: 일정 확인\n"
    content = markdown.encode()
    result: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "integration": "Team3 package import",
        "python_version": sys.version.split()[0],
        "path": path,
        "sha256": hashlib.sha256(content).hexdigest(),
        "direct_provider_verification": "pending",
        "deployed_composed_workflow": "not exercised",
        "cleanup": "not needed",
    }
    with ExitStack() as stack:
        try:
            storage = stack.enter_context(package_document_storage(settings))
        except Exception as error:
            result.update(result="failed", failure_type=type(error).__name__)
            result["finished_at"] = datetime.now(UTC).isoformat()
            return result
        may_exist = False
        try:
            storage.check_health()
            result["provider_health"] = "passed"
            try:
                storage.get_metadata(path)
            except NotFoundError:
                pass
            else:
                raise ConflictError("Scratch path is occupied")
            may_exist = True
            try:
                saved = DocumentSummaryStore(storage, root).save_summary(name, markdown)
            except SummaryStorageError as error:
                may_exist = error.may_have_applied
                raise
            result["create_and_download_compare"] = "passed"
            result["reference"] = saved.id
            result["metadata"] = asdict(storage.get_metadata(path))
            try:
                storage.create(path, b"must not overwrite")
            except ConflictError:
                result["create_conflict"] = "passed"
            else:
                raise AssertionError("Create did not report conflict")
            if storage.download(path) != content:
                raise AssertionError("Conflict changed stored bytes")
            result["conflict_preserved_bytes"] = "passed"
            result["result"] = "passed"
        except Exception as error:
            result["result"] = "failed"
            result["failure_type"] = type(error).__name__
        finally:
            if may_exist:
                try:
                    try:
                        storage.delete(path)
                    except NotFoundError:
                        pass
                    try:
                        storage.get_metadata(path)
                    except NotFoundError:
                        result["cleanup"] = "confirmed absent"
                    else:
                        raise AssertionError("File remains after cleanup")
                except Exception as error:
                    result["cleanup"] = "failed"
                    result["cleanup_failure_type"] = type(error).__name__
                    result["result"] = "failed"
    result["finished_at"] = datetime.now(UTC).isoformat()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        parser.error("--execute is required because this changes provider state")
    try:
        settings = PackageStorageSettings.from_environment()
    except SummaryStorageError:
        parser.error(
            "Package storage configuration is invalid; see docs/HW3_STORAGE_AUTH.md"
        )
    # Check the evidence destination before creating any remote state.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Do not overwrite historical evidence, token files or another run's output.
    with args.output.open("x", encoding="utf-8"):
        pass
    repo = Path(__file__).resolve().parents[1]
    provenance = {
        "application_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "source_sha256": {
            name: hashlib.sha256((repo / name).read_bytes()).hexdigest()
            for name in (
                "app/storage_paths.py",
                "app/storage_package.py",
                "app/summary_storage.py",
                "scripts/verify_storage_live.py",
                "uv.lock",
                "pyproject.toml",
            )
        },
    }
    result = {
        **provenance,
        "packages": {
            name: {
                "version": distribution(name).version,
                "direct_url": json.loads(
                    distribution(name).read_text("direct_url.json") or "null"
                ),
            }
            for name in (
                "cloud-storage-api",
                "cloud-storage-client-api",
                "dropbox-client-impl",
                "dropbox",
            )
        },
        **verify(settings),
    }
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": result["result"], "cleanup": result["cleanup"]}))
    if result["result"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
