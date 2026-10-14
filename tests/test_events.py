from fastapi.testclient import TestClient


def test_get_known_event(client: TestClient) -> None:
    response = client.get("/events/test-event")

    assert response.status_code == 200
    assert response.json() == {
        "id": "test-event",
        "title": "Example Event",
        "start_time": "2026-10-05T18:00:00Z",
        "end_time": "2026-10-05T19:00:00Z",
    }


def test_get_unknown_event(client: TestClient) -> None:
    response = client.get("/events/missing-event")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}
