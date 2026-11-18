"""Run the deployed scheduled-issue workflow once, then inspect or clean up.

Two phases keep provider inspection possible between them:

    run      POST one marked request to the hosted service, then search Trello,
             Google Calendar and Dropbox for that marker. Nothing is deleted.
    cleanup  Read a run record, delete only that run's resources (newest first)
             and confirm each is absent afterward.

Hosted target: CALENDAR_VERIFY_URL (HTTPS origin) and CALENDAR_VERIFY_BEARER_FILE.
Provider inspection uses the operator's own credentials: TRELLO_API_KEY,
TRELLO_TOKEN, TRELLO_LIST_ID, the local Google token.json and the Dropbox
package settings (see docs/HW3_STORAGE_AUTH.md). Records hold IDs, statuses and
hashes only; no credentials, Markdown bodies or raw provider messages.
This command changes provider state. Never repeat an uncertain run blindly.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

EXPECTATIONS = {"created", "storage_failure"}
STORAGE_IMPLEMENTATIONS = {"team3_dropbox", "team1_dropbox"}
TITLE_PREFIX = "team5-hw3-hosted-"


class Providers(Protocol):
    """Independent provider access used to inspect and clean up one run."""

    def find_cards(self, title: str) -> list[dict[str, Any]]: ...
    def delete_card(self, card_id: str) -> None: ...
    def find_events(
        self, marker: str, start: str, end: str
    ) -> list[dict[str, Any]]: ...
    def delete_event(self, event_id: str) -> None: ...
    def summary_sha256(self, path: str) -> str | None: ...
    def delete_summary(self, path: str) -> None: ...


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def git_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        return None


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_for(marker: str, today: datetime) -> dict[str, str]:
    """A unique title and a future 30-minute slot that cannot hit real plans."""
    start = (today + timedelta(days=60)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    return {
        "title": f"{TITLE_PREFIX}{marker}",
        "start": start.isoformat().replace("+00:00", "Z"),
        "end": (start + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
    }


def summarize_response(status: int, body: object) -> dict[str, Any]:
    """Keep only identifiers and the five workflow error fields."""
    record: dict[str, Any] = {"status": status}
    if not isinstance(body, dict):
        record["body"] = "not-json-object"
        return record
    if status == 201:
        issue, event, summary = (
            body.get(k) or {} for k in ("issue", "event", "summary")
        )
        markdown = summary.get("markdown")
        record.update(
            issue_id=issue.get("id"),
            event_id=event.get("id"),
            event_start=event.get("start"),
            event_end=event.get("end"),
            summary_id=summary.get("id"),
            summary_sha256=sha256(markdown) if isinstance(markdown, str) else None,
        )
        return record
    error = body.get("error") or {}
    record["error"] = {
        key: error.get(key) for key in ("code", "retryable", "step", "leftovers")
    }
    return record


def expectation_met(expect: str, response: dict[str, Any]) -> bool:
    if expect == "created":
        return response["status"] == 201 and all(
            response.get(key) for key in ("issue_id", "event_id", "summary_id")
        )
    error = response.get("error") or {}
    return response["status"] in {502, 503} and error.get("step") == "summary"


def summary_path(root: str, issue_id: str, event_id: str) -> str:
    """The path the workflow stores under; summary_name reads only the IDs."""
    from app.storage_paths import storage_path
    from app.workflow import summary_name

    issue: Any = SimpleNamespace(id=issue_id)
    event: Any = SimpleNamespace(id=event_id)
    return storage_path(root) + "/" + summary_name(issue, event)


def inspect(
    providers: Providers,
    record: dict[str, Any],
    storage_root: str,
) -> dict[str, Any]:
    """Search each provider for this run's marker; never modify anything."""
    request = record["request"]
    marker = record["marker"]
    response = record["response"]
    cards = providers.find_cards(request["title"])
    events = providers.find_events(marker, request["start"], request["end"])
    summaries: list[dict[str, Any]] = []
    paths: list[str] = []
    if response.get("issue_id") and response.get("event_id"):
        paths.append(
            summary_path(storage_root, response["issue_id"], response["event_id"])
        )
    for leftover in (response.get("error") or {}).get("leftovers") or []:
        if leftover.get("kind") == "summary" and leftover.get("path"):
            paths.append(leftover["path"])
    for path in dict.fromkeys(paths):
        digest = providers.summary_sha256(path)
        summaries.append(
            {
                "path": path,
                "present": digest is not None,
                "matches_response": digest is not None
                and digest == response.get("summary_sha256"),
            }
        )
    return {
        "at": now(),
        "trello_cards": [{"id": c["id"], "closed": c.get("closed")} for c in cards],
        "calendar_events": [{"id": e["id"]} for e in events],
        "summaries": summaries,
    }


def clean_up(
    providers: Providers, record: dict[str, Any], storage_root: str
) -> dict[str, Any]:
    """Delete summary -> event -> card for this marker only, then re-inspect."""
    before = inspect(providers, record, storage_root)
    actions: list[dict[str, Any]] = []

    def attempt(kind: str, resource: str, delete: Any) -> None:
        try:
            delete(resource)
            actions.append({"kind": kind, "id": resource, "deleted": True})
        except Exception as error:
            actions.append(
                {
                    "kind": kind,
                    "id": resource,
                    "deleted": False,
                    "error": type(error).__name__,
                }
            )

    for summary in before["summaries"]:
        if summary["present"]:
            attempt("summary", summary["path"], providers.delete_summary)
    for event in before["calendar_events"]:
        attempt("event", event["id"], providers.delete_event)
    for card in before["trello_cards"]:
        attempt("issue", card["id"], providers.delete_card)
    after = inspect(providers, record, storage_root)
    absent = (
        not after["trello_cards"]
        and not after["calendar_events"]
        and not any(summary["present"] for summary in after["summaries"])
    )
    return {"before": before, "actions": actions, "after": after, "all_absent": absent}


def hosted_client() -> httpx.Client:
    url = os.environ["CALENDAR_VERIFY_URL"]
    target = urlsplit(url)
    if (
        target.scheme != "https"
        or not target.hostname
        or target.username is not None
        or target.path not in {"", "/"}
        or target.query
        or target.fragment
    ):
        raise ValueError("CALENDAR_VERIFY_URL must be an HTTPS service origin.")
    bearer = Path(os.environ["CALENDAR_VERIFY_BEARER_FILE"]).read_text().strip()
    if not bearer:
        raise ValueError("Provide the demo bearer token file.")
    return httpx.Client(
        base_url=url,
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=100,
        trust_env=False,
        follow_redirects=False,
    )


@dataclass
class LiveProviders:
    """Operator-credentialed provider access, independent of the hosted app."""

    trello: httpx.Client
    google: Any
    storage: Any
    list_id: str

    def find_cards(self, title: str) -> list[dict[str, Any]]:
        response = self.trello.get(
            f"lists/{self.list_id}/cards/all", params={"fields": "id,name,closed"}
        )
        response.raise_for_status()
        return [card for card in response.json() if card.get("name") == title]

    def delete_card(self, card_id: str) -> None:
        self.trello.delete(f"cards/{card_id}").raise_for_status()

    def find_events(self, marker: str, start: str, end: str) -> list[dict[str, Any]]:
        result = (
            self.google.events()
            .list(
                calendarId="primary",
                q=marker,
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                showDeleted=False,
            )
            .execute()
        )
        return [
            event
            for event in result.get("items", [])
            if marker in str(event.get("summary", ""))
        ]

    def delete_event(self, event_id: str) -> None:
        self.google.events().delete(calendarId="primary", eventId=event_id).execute()

    def summary_sha256(self, path: str) -> str | None:
        from cloud_storage_api import NotFoundError

        try:
            content: bytes = self.storage.download(path)
        except NotFoundError:
            return None
        return hashlib.sha256(content).hexdigest()

    def delete_summary(self, path: str) -> None:
        self.storage.delete(path)


@contextmanager
def live_providers() -> Iterator[tuple[LiveProviders, str]]:
    from googleapiclient.discovery import build  # type: ignore[import-untyped]

    from app.google_create_events import load_credentials
    from app.storage_package import PackageStorageSettings, package_document_storage

    key, token = os.environ["TRELLO_API_KEY"], os.environ["TRELLO_TOKEN"]
    settings = PackageStorageSettings.from_environment()
    with ExitStack() as stack:
        trello = stack.enter_context(
            httpx.Client(
                base_url="https://api.trello.com/1/",
                headers={
                    "Authorization": f'OAuth oauth_consumer_key="{key}", oauth_token="{token}"'
                },
                timeout=15,
                follow_redirects=False,
                trust_env=False,
            )
        )
        google = stack.enter_context(
            build("calendar", "v3", credentials=load_credentials())
        )
        storage = stack.enter_context(package_document_storage(settings))
        yield (
            LiveProviders(trello, google, storage, os.environ["TRELLO_LIST_ID"]),
            settings.root_path,
        )


def write_new(path: Path, document: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(document, output, indent=2)
        output.write("\n")


def run(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite an existing record.")
    marker = uuid4().hex
    request = request_for(marker, datetime.now(UTC))
    record: dict[str, Any] = {
        "kind": "hw3_hosted_workflow_run",
        "operator_checkout_commit": git_head(),
        "deploy_run_id": args.deploy_run_id,
        "deployed_storage_implementation": args.storage,
        "expect": args.expect,
        "service_host": urlsplit(os.environ["CALENDAR_VERIFY_URL"]).hostname,
        "marker": marker,
        "request": request,
        "started_at": now(),
    }
    with hosted_client() as client:
        record["health_status"] = client.get("/health").status_code
        try:
            response = client.post("/workflows/scheduled-issues", json=request)
        except httpx.HTTPError as error:
            # The outcome is unknown: keep the marker so inspection can find it.
            record["response"] = {
                "status": None,
                "transport_error": type(error).__name__,
            }
        else:
            try:
                body = response.json()
            except ValueError:
                body = None
            record["response"] = summarize_response(response.status_code, body)
    record["finished_at"] = now()
    with live_providers() as (providers, root):
        record["inspection_before_cleanup"] = inspect(providers, record, root)
    record["expectation_met"] = expectation_met(args.expect, record["response"])
    record["cleanup"] = "not performed; run the cleanup command after inspection"
    write_new(args.output, record)
    print(
        json.dumps(
            {"output": str(args.output), "expectation_met": record["expectation_met"]}
        )
    )
    return 0 if record["expectation_met"] else 1


def cleanup(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite an existing record.")
    record = json.loads(args.record.read_text(encoding="utf-8"))
    if record.get("kind") != "hw3_hosted_workflow_run" or not str(
        record.get("request", {}).get("title", "")
    ).startswith(TITLE_PREFIX):
        raise ValueError("Not a hosted workflow run record.")
    with live_providers() as (providers, root):
        result = clean_up(providers, record, root)
    write_new(
        args.output,
        {
            "kind": "hw3_hosted_workflow_cleanup",
            "run_record": args.record.name,
            "marker": record["marker"],
            "operator_checkout_commit": git_head(),
            "started_at": result["before"]["at"],
            **result,
        },
    )
    print(json.dumps({"output": str(args.output), "all_absent": result["all_absent"]}))
    return 0 if result["all_absent"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("run")
    start.add_argument(
        "--storage", choices=sorted(STORAGE_IMPLEMENTATIONS), required=True
    )
    start.add_argument("--expect", choices=sorted(EXPECTATIONS), required=True)
    start.add_argument("--deploy-run-id", type=int, required=True)
    start.add_argument("--output", type=Path, required=True)
    finish = commands.add_parser("cleanup")
    finish.add_argument("--record", type=Path, required=True)
    finish.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(args) if args.command == "run" else cleanup(args)
    except Exception as error:
        # Do not echo provider responses or credential-bearing configuration.
        print(json.dumps({"step": args.command, "error": type(error).__name__}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
