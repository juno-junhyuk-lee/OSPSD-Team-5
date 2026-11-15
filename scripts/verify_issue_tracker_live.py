"""Opt-in creation/read/cleanup check with independent Trello read-back."""

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from importlib.metadata import distribution
from uuid import uuid4

import httpx
from issue_tracker_contract import IssueProvider, ServiceError

from app.issue_tracker_dependencies import get_issue_provider


def emit(step: str, passed: bool, **details: object) -> None:
    print(json.dumps({"step": step, "passed": passed, **details}), flush=True)


def verify(issues: IssueProvider, direct: httpx.Client, marker: str) -> bool:
    """Delete only the confirmed card from this run; never repeat a create."""
    title = f"team5-hw3-{marker}"
    card_id: str | None = None
    create_attempted = False
    success = True
    try:
        target = direct.get(
            f"lists/{os.environ['TRELLO_LIST_ID']}", params={"fields": "id,closed"}
        )
        target.raise_for_status()
        if (
            target.json().get("id") != os.environ["TRELLO_LIST_ID"]
            or target.json().get("closed") is not False
        ):
            raise ValueError
        emit("independent_list_preflight", True)
        create_attempted = True
        created = issues.create_issue(title)
        card_id = created.id
        if created.title != title:
            raise ValueError
        emit("create", True)
        fetched = issues.get_issue(card_id, fresh=True)
        if fetched != created:
            raise ValueError
        emit("fresh_read", True)
        response = direct.get(f"cards/{card_id}", params={"fields": "id,name,idList"})
        response.raise_for_status()
        actual = response.json()
        if (
            actual.get("id") != card_id
            or actual.get("name") != title
            or actual.get("idList") != os.environ["TRELLO_LIST_ID"]
        ):
            raise ValueError
        emit("independent_trello_read", True)
    except ServiceError, httpx.HTTPError, ValueError, KeyError, TypeError:
        emit(
            "workflow",
            False,
            inspection_required=create_attempted and card_id is None,
            marker=title,
        )
        success = False
    finally:
        if card_id is not None:
            try:
                issues.delete_issue(card_id)
                emit("delete", True)
            except ServiceError:
                emit("delete", False, inspection_required=True, marker=title)
                success = False
            try:
                absent = direct.get(f"cards/{card_id}").status_code == 404
                emit("independent_cleanup", absent, marker=title)
                success = success and absent
            except httpx.HTTPError:
                emit(
                    "independent_cleanup", False, inspection_required=True, marker=title
                )
                success = False
        elif create_attempted:
            emit("cleanup", False, inspection_required=True, marker=title)
    return success


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-writes", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_writes:
        parser.error("Pass --allow-writes to create and delete a test card.")
    emit(
        "provenance",
        True,
        started_utc=datetime.now(UTC).isoformat(),
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        dirty=bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        ),
        contract=distribution("issue-tracker-contract").version,
        implementation=distribution("team-4-issue-tracker-trello").version,
        implementation_commit=json.loads(
            distribution("team-4-issue-tracker-trello").read_text("direct_url.json")
            or "{}"
        )
        .get("vcs_info", {})
        .get("commit_id"),
    )
    dependency = get_issue_provider()
    try:
        issues = next(dependency)
        key, token = os.environ["TRELLO_API_KEY"], os.environ["TRELLO_TOKEN"]
        with httpx.Client(
            base_url="https://api.trello.com/1/",
            headers={
                "Authorization": f'OAuth oauth_consumer_key="{key}", oauth_token="{token}"'
            },
            timeout=15,
            follow_redirects=False,
            trust_env=False,
        ) as direct:
            success = verify(issues, direct, uuid4().hex)
    except ServiceError:
        emit("configuration", False)
        return 1
    finally:
        dependency.close()
    emit("finished", success)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
