"""Offline checks for the hosted workflow run/inspect/cleanup helper."""

from datetime import UTC, datetime
from typing import Any

import pytest

from scripts.verify_workflow_hosted import (
    TITLE_PREFIX,
    clean_up,
    expectation_met,
    inspect,
    request_for,
    sha256,
    summarize_response,
    summary_path,
)

ROOT = "/ospsd-team5-hw3"
MARKER = "f" * 32


class FakeProviders:
    def __init__(self) -> None:
        self.cards: dict[str, dict[str, Any]] = {}
        self.events: dict[str, dict[str, Any]] = {}
        self.files: dict[str, str] = {}
        self.fail_event_delete = False
        self.deleted: list[str] = []

    def find_cards(self, title: str) -> list[dict[str, Any]]:
        return [card for card in self.cards.values() if card["name"] == title]

    def delete_card(self, card_id: str) -> None:
        self.deleted.append(f"issue:{card_id}")
        del self.cards[card_id]

    def find_events(self, marker: str, start: str, end: str) -> list[dict[str, Any]]:
        return [e for e in self.events.values() if marker in e["summary"]]

    def delete_event(self, event_id: str) -> None:
        if self.fail_event_delete:
            raise RuntimeError("private provider text")
        self.deleted.append(f"event:{event_id}")
        del self.events[event_id]

    def summary_sha256(self, path: str) -> str | None:
        return sha256(self.files[path]) if path in self.files else None

    def delete_summary(self, path: str) -> None:
        self.deleted.append(f"summary:{path}")
        del self.files[path]


def record_for(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "marker": MARKER,
        "request": request_for(MARKER, datetime(2026, 11, 18, tzinfo=UTC)),
        "response": response,
    }


def created_world() -> tuple[FakeProviders, dict[str, Any]]:
    providers = FakeProviders()
    record = record_for(
        summarize_response(
            201,
            {
                "issue": {"id": "card1", "title": "t"},
                "event": {"id": "evt1", "title": "t", "start": "s", "end": "e"},
                "summary": {"id": "id:abc", "markdown": "# t\n"},
            },
        )
    )
    title = record["request"]["title"]
    providers.cards["card1"] = {"id": "card1", "name": title, "closed": False}
    providers.cards["other"] = {"id": "other", "name": "someone else's card"}
    providers.events["evt1"] = {"id": "evt1", "summary": title}
    providers.files[summary_path(ROOT, "card1", "evt1")] = "# t\n"
    return providers, record


def test_request_is_marked_and_in_the_future() -> None:
    request = request_for(MARKER, datetime(2026, 11, 18, tzinfo=UTC))
    assert request == {
        "title": TITLE_PREFIX + MARKER,
        "start": "2027-01-17T15:00:00Z",
        "end": "2027-01-17T15:30:00Z",
    }


def test_success_record_keeps_ids_and_hash_not_markdown() -> None:
    response = summarize_response(
        201,
        {
            "issue": {"id": "card1"},
            "event": {"id": "evt1", "start": "s", "end": "e"},
            "summary": {"id": "id:abc", "markdown": "# secret-ish body\n"},
        },
    )
    assert "secret-ish" not in str(response)
    assert response["summary_sha256"] == sha256("# secret-ish body\n")
    assert expectation_met("created", response)
    assert not expectation_met("storage_failure", response)


def test_storage_failure_record_keeps_five_field_shape_only() -> None:
    body = {
        "error": {
            "code": "provider_error",
            "message": "Summary storage request failed.",
            "retryable": False,
            "step": "summary",
            "leftovers": [],
        }
    }
    response = summarize_response(502, body)
    assert response == {
        "status": 502,
        "error": {
            "code": "provider_error",
            "retryable": False,
            "step": "summary",
            "leftovers": [],
        },
    }
    assert expectation_met("storage_failure", response)
    assert not expectation_met("created", response)
    body["error"]["step"] = "event"
    assert not expectation_met("storage_failure", summarize_response(502, body))


def test_inspect_finds_only_this_runs_resources() -> None:
    providers, record = created_world()
    found = inspect(providers, record, ROOT)
    assert found["trello_cards"] == [{"id": "card1", "closed": False}]
    assert found["calendar_events"] == [{"id": "evt1"}]
    assert found["summaries"] == [
        {
            "path": summary_path(ROOT, "card1", "evt1"),
            "present": True,
            "matches_response": True,
        }
    ]
    assert providers.deleted == []


def test_cleanup_deletes_newest_first_and_confirms_absence() -> None:
    providers, record = created_world()
    result = clean_up(providers, record, ROOT)
    assert [entry.split(":")[0] for entry in providers.deleted] == [
        "summary",
        "event",
        "issue",
    ]
    assert result["all_absent"] is True
    assert "other" in providers.cards


def test_cleanup_reports_failures_without_provider_text() -> None:
    providers, record = created_world()
    providers.fail_event_delete = True
    result = clean_up(providers, record, ROOT)
    assert result["all_absent"] is False
    assert {
        "kind": "event",
        "id": "evt1",
        "deleted": False,
        "error": "RuntimeError",
    } in (result["actions"])
    assert "private provider text" not in str(result)


def test_compensated_storage_failure_inspects_as_absent() -> None:
    providers = FakeProviders()
    record = record_for(
        summarize_response(
            502,
            {"error": {"code": "provider_error", "step": "summary", "leftovers": []}},
        )
    )
    found = inspect(providers, record, ROOT)
    assert found["trello_cards"] == []
    assert found["calendar_events"] == []
    assert found["summaries"] == []


def test_uncertain_summary_leftover_path_is_inspected() -> None:
    providers = FakeProviders()
    path = ROOT + "/scheduled-issue-x.md"
    record = record_for(
        summarize_response(
            502,
            {
                "error": {
                    "step": "summary",
                    "leftovers": [
                        {
                            "kind": "summary",
                            "id": None,
                            "state": "uncertain",
                            "path": path,
                        }
                    ],
                }
            },
        )
    )
    assert inspect(providers, record, ROOT)["summaries"] == [
        {"path": path, "present": False, "matches_response": False}
    ]


@pytest.mark.parametrize("status", [None, 500])
def test_unknown_outcome_never_meets_an_expectation(status: int | None) -> None:
    response = {"status": status, "transport_error": "ReadTimeout"}
    assert not expectation_met("created", response)
    assert not expectation_met("storage_failure", response)
