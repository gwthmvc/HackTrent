"""Ticketmaster integration tests. All upstream calls use httpx.MockTransport."""
import logging
from datetime import date, datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import ApiError
from app.events import (
    EVENT_AREAS,
    TicketmasterEventService,
    resolve_area,
    resolve_classifications,
    resolve_window,
)
from app.main import create_app

from test_transit_api import FakeTransitRepository

FAKE_KEY = "fake-ticketmaster-key-123"
# Wednesday 2026-11-11 10:00 America/Toronto
FIXED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
KINGSTON_BODY = {
    "startingLocation": "Durham College, Oshawa, Ontario",
    "outingRequest": "A family day out in Kingston this Saturday evening",
}


def tm_event(event_id: str, **overrides) -> dict:
    event = {
        "id": event_id,
        "name": f"Event {event_id}",
        "url": f"https://www.ticketmaster.ca/event/{event_id}",
        "dates": {
            "start": {"localDate": "2026-11-14", "localTime": "19:30:00", "dateTime": "2026-11-15T00:30:00Z"},
            "status": {"code": "onsale"},
        },
        "priceRanges": [{"type": "standard", "currency": "CAD", "min": 25.0, "max": 60.0}],
        "images": [
            {"ratio": "4_3", "url": "https://s1.ticketm.net/a.jpg", "width": 305},
            {"ratio": "16_9", "url": "https://s1.ticketm.net/b.jpg", "width": 640},
        ],
        "classifications": [{"segment": {"name": "Music"}, "genre": {"name": "Rock"}}],
        "_embedded": {"venues": [{
            "name": "Slush Puppie Place",
            "address": {"line1": "1 The Tragically Hip Way"},
            "city": {"name": "Kingston"},
            "state": {"stateCode": "ON"},
            "postalCode": "K7L 0E3",
            "location": {"latitude": "44.2297", "longitude": "-76.4812"},
        }]},
    }
    event.update(overrides)
    return event


def tm_payload(*events: dict) -> dict:
    if not events:
        return {"page": {"size": 50, "totalElements": 0, "totalPages": 0, "number": 0}}
    return {
        "_embedded": {"events": list(events)},
        "page": {"size": 50, "totalElements": len(events), "totalPages": 1, "number": 0},
    }


class Upstream:
    """Records requests and replies with a canned response."""

    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_client(upstream: Upstream, **settings_overrides) -> tuple[TestClient, TicketmasterEventService]:
    values = {"auth_required": False, "ticketmaster_api_key": FAKE_KEY, **settings_overrides}
    settings = Settings(_env_file=None, **values)
    service = TicketmasterEventService(settings, transport=httpx.MockTransport(upstream), clock=lambda: FIXED_NOW)
    app = create_app(settings, FakeTransitRepository([]), event_service=service)
    return TestClient(app), service


def ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


# --- Successful searches ------------------------------------------------------

def test_returns_verified_events_and_sends_expected_query(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    upstream = Upstream(ok(tm_payload(
        tm_event("full"),
        tm_event("no-coords", _embedded={"venues": [{"name": "Grand Theatre", "location": {}}]}),
        tm_event("far-away", _embedded={"venues": [{"name": "Far", "location": {"latitude": "43.65", "longitude": "-79.38"}}]}),
        tm_event("cancelled", dates={"start": {"localDate": "2026-11-14"}, "status": {"code": "cancelled"}}),
        tm_event("bad-link", url="https://phishing.example/event"),
        {"id": "broken"},
    )))
    client, service = make_client(upstream)

    with client:
        response = client.post("/api/events/search", json=KINGSTON_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["areaId"] == "kingston"
    assert body["source"]["name"] == "Ticketmaster Discovery API"
    events = {event["id"]: event for event in body["events"]}
    assert set(events) == {"full", "no-coords", "far-away", "bad-link"}

    full = events["full"]
    assert full["name"] == "Event full"
    assert full["url"] == "https://www.ticketmaster.ca/event/full"
    assert full["startLocalDate"] == "2026-11-14"
    assert full["startLocalTime"] == "19:30"
    assert full["priceRange"] == {"min": 25.0, "max": 60.0, "currency": "CAD"}
    assert full["imageUrl"] == "https://s1.ticketm.net/b.jpg"
    assert full["classification"] == "Music · Rock"
    assert full["venue"]["address"] == "1 The Tragically Hip Way"
    assert full["venue"]["latitude"] == pytest.approx(44.2297)
    assert full["venue"]["coordinateStatus"] == "verified"

    assert events["no-coords"]["venue"]["latitude"] is None
    assert events["no-coords"]["venue"]["coordinateStatus"] == "missing"
    assert events["far-away"]["venue"]["latitude"] is None
    assert events["far-away"]["venue"]["coordinateStatus"] == "outside_search_area"
    assert events["bad-link"]["url"] is None
    assert events["no-coords"]["priceRange"] == {"min": 25.0, "max": 60.0, "currency": "CAD"}

    assert service.upstream_calls == 1
    params = upstream.requests[0].url.params
    assert upstream.requests[0].url.path.endswith("/discovery/v2/events.json")
    assert params["apikey"] == FAKE_KEY
    assert params["latlong"] == "44.2312,-76.486"
    assert params["radius"] == "25" and params["unit"] == "km"
    assert params["startDateTime"] == "2026-11-14T05:00:00Z"  # Saturday 00:00 EST
    assert params["endDateTime"] == "2026-11-15T04:59:59Z"
    assert params["classificationName"] == "Family"

    # The key must never reach the client or the logs.
    assert FAKE_KEY not in response.text
    assert FAKE_KEY not in caplog.text


def test_no_events_returns_empty_list() -> None:
    client, _ = make_client(Upstream(ok(tm_payload())))
    with client:
        response = client.post("/api/events/search", json=KINGSTON_BODY)
    assert response.status_code == 200
    assert response.json()["events"] == []
    assert response.json()["totalAvailable"] == 0


def test_price_missing_is_null_not_invented() -> None:
    event = tm_event("free")
    del event["priceRanges"]
    client, _ = make_client(Upstream(ok(tm_payload(event))))
    with client:
        response = client.post("/api/events/search", json=KINGSTON_BODY)
    assert response.json()["events"][0]["priceRange"] is None


def test_time_of_day_filter_keeps_matching_and_unknown_times() -> None:
    afternoon = tm_event("afternoon")
    afternoon["dates"]["start"]["localTime"] = "14:00:00"
    tba = tm_event("tba")
    del tba["dates"]["start"]["localTime"]
    client, _ = make_client(Upstream(ok(tm_payload(tm_event("evening"), afternoon, tba))))
    with client:
        response = client.post("/api/events/search", json=KINGSTON_BODY)
    assert [e["id"] for e in response.json()["events"]] == ["evening", "tba"]
    assert response.json()["window"]["timeFrom"] == "17:00"


def test_results_are_cached_between_identical_searches() -> None:
    upstream = Upstream(ok(tm_payload(tm_event("one"))))
    client, service = make_client(upstream)
    with client:
        first = client.post("/api/events/search", json=KINGSTON_BODY)
        second = client.post("/api/events/search", json=KINGSTON_BODY)
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert second.json()["events"] == first.json()["events"]
    assert service.upstream_calls == 1


def test_durham_search_uses_durham_area() -> None:
    upstream = Upstream(ok(tm_payload()))
    client, _ = make_client(upstream)
    with client:
        response = client.post("/api/events/search", json={
            "startingLocation": "Trent University Durham, Oshawa",
            "outingRequest": "Hockey game in Oshawa tomorrow",
        })
    assert response.json()["areaId"] == "durham"
    params = upstream.requests[0].url.params
    assert params["latlong"] == "43.9,-78.9"
    assert params["classificationName"] == "Hockey,Sports"


# --- Failure handling ---------------------------------------------------------

@pytest.mark.parametrize("upstream_response, status, code", [
    (httpx.Response(500, text="boom"), 502, "events_upstream_error"),
    (httpx.Response(401, json={"fault": {"faultstring": "Invalid ApiKey"}}), 502, "events_upstream_auth"),
    (httpx.Response(429, json={"fault": {}}), 429, "events_rate_limited"),
    (httpx.Response(200, text="<html>not json</html>"), 502, "events_upstream_error"),
    (httpx.ReadTimeout("timed out"), 504, "events_upstream_timeout"),
    (httpx.ConnectError(f"failed for https://app.ticketmaster.com/?apikey={FAKE_KEY}"), 502, "events_upstream_error"),
])
def test_upstream_failures_return_structured_errors(caplog, upstream_response, status, code) -> None:
    caplog.set_level(logging.DEBUG)
    client, _ = make_client(Upstream(upstream_response))
    with client:
        response = client.post("/api/events/search", json=KINGSTON_BODY)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert FAKE_KEY not in response.text
    assert FAKE_KEY not in caplog.text


def test_failed_searches_are_not_cached() -> None:
    upstream = Upstream(httpx.Response(500))
    client, service = make_client(upstream)
    with client:
        client.post("/api/events/search", json=KINGSTON_BODY)
        upstream.response = ok(tm_payload(tm_event("recovered")))
        response = client.post("/api/events/search", json=KINGSTON_BODY)
    assert response.status_code == 200
    assert service.upstream_calls == 2


def test_missing_api_key_returns_503_without_calling_upstream() -> None:
    upstream = Upstream(ok(tm_payload()))
    client, service = make_client(upstream, ticketmaster_api_key=None)
    with client:
        response = client.post("/api/events/search", json=KINGSTON_BODY)
        health = client.get("/health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "events_not_configured"
    assert service.upstream_calls == 0
    assert health.json()["eventsConfigured"] is False


def test_unsupported_area_returns_422_without_calling_upstream() -> None:
    upstream = Upstream(ok(tm_payload()))
    client, service = make_client(upstream)
    with client:
        response = client.post("/api/events/search", json={
            "startingLocation": "Sudbury", "outingRequest": "Concert in Thunder Bay",
        })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_event_area"
    assert service.upstream_calls == 0


def test_global_upstream_rate_limit() -> None:
    upstream = Upstream(ok(tm_payload()))
    client, service = make_client(upstream, ticketmaster_max_requests_per_minute=1)
    with client:
        first = client.post("/api/events/search", json=KINGSTON_BODY)
        second = client.post("/api/events/search", json={**KINGSTON_BODY, "outingRequest": "Kingston concert tomorrow"})
        cached = client.post("/api/events/search", json=KINGSTON_BODY)
    assert first.status_code == 200
    assert second.status_code == 429
    assert cached.status_code == 200  # Cache hits do not consume upstream quota.
    assert service.upstream_calls == 1


def test_per_user_search_limit() -> None:
    client, _ = make_client(Upstream(ok(tm_payload())), events_max_searches_per_user_per_minute=2)
    with client:
        codes = [client.post("/api/events/search", json=KINGSTON_BODY).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_events_endpoint_requires_auth0_token() -> None:
    settings = Settings(
        _env_file=None,
        ticketmaster_api_key=FAKE_KEY,
        auth0_domain="tenant.example.auth0.com",
        auth0_audience="https://api.smartmove.test",
    )
    upstream = Upstream(ok(tm_payload()))
    service = TicketmasterEventService(settings, transport=httpx.MockTransport(upstream))
    with TestClient(create_app(settings, FakeTransitRepository([]), event_service=service)) as client:
        response = client.post("/api/events/search", json=KINGSTON_BODY)
    assert response.status_code == 401
    assert service.upstream_calls == 0


def test_health_does_not_expose_key() -> None:
    client, _ = make_client(Upstream(ok(tm_payload())))
    with client:
        health = client.get("/health")
    assert health.json()["eventsConfigured"] is True
    assert FAKE_KEY not in health.text


# --- Request interpretation ---------------------------------------------------

def test_area_prefers_destination_over_start() -> None:
    assert resolve_area("Oshawa", "Take the bus to Kingston").area_id == "kingston"
    assert resolve_area("Kingston", "Something fun nearby").area_id == "kingston"
    assert resolve_area("Whitby", "Things to do").area_id == "durham"
    assert set(EVENT_AREAS) == {"durham", "kingston"}


def test_interest_classifications() -> None:
    assert resolve_classifications("Comedy night with my daughter", []) == ["Comedy", "Family"]
    assert resolve_classifications("Something fun", ["jazz"]) == ["Jazz"]
    assert resolve_classifications("Something fun", []) == []


@pytest.mark.parametrize("text, start, end", [
    ("this saturday", "2026-11-14T00:00:00-05:00", "2026-11-14T23:59:59-05:00"),
    ("this weekend", "2026-11-14T00:00:00-05:00", "2026-11-15T23:59:59-05:00"),
    ("tonight", "2026-11-11T10:00:00-05:00", "2026-11-11T23:59:59-05:00"),
    ("tomorrow", "2026-11-12T00:00:00-05:00", "2026-11-12T23:59:59-05:00"),
    ("on 2026-12-05", "2026-12-05T00:00:00-05:00", "2026-12-05T23:59:59-05:00"),
    ("on December 5th", "2026-12-05T00:00:00-05:00", "2026-12-05T23:59:59-05:00"),
    ("next wednesday", "2026-11-18T00:00:00-05:00", "2026-11-18T23:59:59-05:00"),
    ("sometime soon", "2026-11-11T10:00:00-05:00", "2026-11-25T23:59:59-05:00"),
])
def test_resolve_window(text, start, end) -> None:
    window = resolve_window(text, None, None, FIXED_NOW)
    assert window.start.isoformat() == start
    assert window.end.isoformat() == end


def test_explicit_date_and_time_override_prompt() -> None:
    window = resolve_window("this saturday evening", date(2026, 11, 20), "13:00", FIXED_NOW)
    assert window.start.date() == date(2026, 11, 20)
    assert window.time_range is not None
    assert window.time_range[0].strftime("%H:%M") == "12:00"


def test_clock_time_in_prompt() -> None:
    window = resolve_window("Kingston after 7pm tomorrow", None, None, FIXED_NOW)
    assert window.time_range is not None
    assert window.time_range[0].strftime("%H:%M") == "19:00"


def test_past_date_is_rejected() -> None:
    with pytest.raises(ApiError) as error:
        resolve_window("on 2026-01-02", None, None, FIXED_NOW)
    assert error.value.code == "invalid_event_date"


def test_invalid_request_fields_are_rejected() -> None:
    client, service = make_client(Upstream(ok(tm_payload())))
    with client:
        bad_time = client.post("/api/events/search", json={**KINGSTON_BODY, "time": "25:99"})
        too_many = client.post("/api/events/search", json={**KINGSTON_BODY, "interests": ["a"] * 6})
    assert bad_time.status_code == 422
    assert too_many.status_code == 422
    assert service.upstream_calls == 0


def test_settings_env_file_is_anchored_to_backend_directory(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from app.config import BACKEND_ENV_FILE

    backend_dir = Path(__file__).resolve().parent.parent
    assert Settings.model_config["env_file"] == BACKEND_ENV_FILE
    assert BACKEND_ENV_FILE == backend_dir / ".env"

    env_file = tmp_path / ".env"
    env_file.write_text("TICKETMASTER_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)  # a different working directory
    monkeypatch.delenv("TICKETMASTER_API_KEY", raising=False)
    settings = Settings(_env_file=env_file)
    assert settings.ticketmaster_api_key.get_secret_value() == "from-file"
