"""Opt-in summary upload, readback, conflict and cleanup verification.

Set STORAGE_BASE_URL and STORAGE_ROOT_PATH (optional connection settings as in
app/storage_settings.py). Run with python -m scripts.verify_storage_live
--execute --output <evidence.json>. Creates/deletes one UUID-named file, leaving
the configured folder intact. Direct provider inspection is a separate check.
"""

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cloud_storage_api import ConflictError, NotFoundError, StorageError

from app.storage_client import HttpDocumentStorage, storage_path
from app.storage_settings import StorageSettings, storage_http_client
from app.summary_storage import DocumentSummaryStore, SummaryStorageError


def verify(settings: StorageSettings, root_path: str) -> dict[str, object]:
    root = storage_path(root_path)
    name = f"team5-hw3-{uuid4().hex}.md"
    path = root + "/" + name
    markdown = f"# Team 5 storage verification\n\nFile: {name}\nUTF-8: 일정 확인\n"
    content = markdown.encode()
    result: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": settings.base_url,
        "path": path,
        "sha256": hashlib.sha256(content).hexdigest(),
        "direct_provider_verification": "pending",
        "deployed_composed_workflow": "not exercised",
        "cleanup": "not needed",
    }
    with storage_http_client(settings) as client:
        storage = HttpDocumentStorage(client)
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
                except (StorageError, AssertionError) as error:
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
    # Check the evidence destination before creating any remote state.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8"):
        pass
    repo = Path(__file__).resolve().parents[1]
    provenance = {
        "application_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "source_sha256": {
            name: hashlib.sha256((repo / name).read_bytes()).hexdigest()
            for name in (
                "app/storage_http.py",
                "app/storage_client.py",
                "app/storage_settings.py",
                "app/summary_storage.py",
                "scripts/verify_storage_live.py",
                "uv.lock",
            )
        },
    }
    result = {
        **provenance,
        **verify(StorageSettings.from_environment(), os.environ["STORAGE_ROOT_PATH"]),
    }
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": result["result"], "cleanup": result["cleanup"]}))
    if result["result"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
