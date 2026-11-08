from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.events import TicketmasterEventService
from app.main import create_app
from app.outings import OutingOrchestrator
from app.places import OverpassPlaceService
from app.repository import PositionRecord
from app.service import TransitService

FAKE_KEY = "fake-ticketmaster-key-123"
FIXED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)


def tm_event(event_id: str, **overrides) -> dict:
    event = {
        "id": event_id,
        "name": f"Event {event_id}",
        "url": f"https://ticketmaster.example/{event_id}",
        "dates": {"start": {"localDate": "2026-11-14", "localTime": "19:30:00", "dateTime": "2026-11-15T00:30:00Z"}},
        "priceRanges": [{"currency": "CAD", "min": 25, "max": 60}],
        "_embedded": {"venues": [{
            "name": "Durham Venue",
            "address": {"line1": "1 Main Street"},
            "city": {"name": "Oshawa"},
            "state": {"stateCode": "ON"},
            "location": {"latitude": "43.9", "longitude": "-78.9"},
        }]},
    }
    event.update(overrides)
    return event


def tm_payload(*events: dict) -> dict:
    return {"_embedded": {"events": list(events)}, "page": {"size": 50, "totalElements": len(events), "totalPages": 1, "number": 0}}


class Upstream:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeTransitRepository:
    def __init__(self, records: list[PositionRecord]) -> None:
        self.records = records

    def latest_positions(self, agency_value: str) -> list[PositionRecord]:
        return self.records


def ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


def place_payload() -> dict:
    return {
        "elements": [{
            "type": "node", "id": 1, "lat": 43.9005, "lon": -78.8995,
            "tags": {"name": "Local Cafe", "amenity": "cafe"},
        }],
        "osm3s": {"timestamp_osm_base": "2026-11-11T14:59:00Z"},
    }


def make_client(event_upstream: Upstream, place_upstream: Upstream, records=None, **overrides):
    settings = Settings(_env_file=None, auth_required=False, ticketmaster_api_key=FAKE_KEY, **overrides)
    event_service = TicketmasterEventService(settings, transport=httpx.MockTransport(event_upstream), clock=lambda: FIXED_NOW)
    place_service = OverpassPlaceService(settings, transport=httpx.MockTransport(place_upstream), clock=lambda: FIXED_NOW)
    transit_service = TransitService(FakeTransitRepository(records or []), settings)
    orchestrator = OutingOrchestrator(event_service, place_service, transit_service)
    return TestClient(create_app(settings, FakeTransitRepository(records or []), event_service=event_service, place_service=place_service, outing_orchestrator=orchestrator)), event_service


BODY = {"startingLocation": "Oshawa, Ontario", "outingRequest": "Things to do in Oshawa"}


def test_all_sources_succeed():
    client, _ = make_client(Upstream(ok(tm_payload(tm_event("event-1")))), Upstream(ok(place_payload())), [
        PositionRecord("bus-1", "durham", "900", 43.9, -78.9, FIXED_NOW),
    ])
    with client:
        response = client.post("/api/outings/generate", json=BODY)
    body = response.json()
    assert response.status_code == 200
    assert {item["id"] for item in body["recommendations"]} == {"event-1", "osm-node-1"}
    assert body["itinerary"][0]["id"] == "event-1"
    assert body["transit"]["items"][0]["id"] == "bus-1"


def test_missing_classification_is_null_and_price_uses_price_range():
    event = tm_event("priced", classifications=[])
    client, _ = make_client(
        Upstream(ok(tm_payload(event))),
        Upstream(ok({"elements": []})),
    )
    with client:
        body = client.post("/api/outings/generate", json=BODY).json()
    recommendation = body["recommendations"][0]
    assert recommendation["category"] is None
    assert recommendation["description"] is None
    assert recommendation["priceRange"] == {"min": 25.0, "max": 60.0, "currency": "CAD"}
    assert "price" not in recommendation


def test_verified_venue_is_passed_to_places():
    places = Upstream(ok({"elements": []}))
    client, _ = make_client(Upstream(ok(tm_payload(tm_event("event-1")))), places)
    with client:
        client.post("/api/outings/generate", json=BODY)
    query = parse_qs(places.requests[0].content.decode())["data"][0]
    assert "around:2000,43.900000,-78.900000" in query


def test_no_verified_venue_uses_area_anchor():
    places = Upstream(ok({"elements": []}))
    event = tm_event("missing", _embedded={"venues": [{"name": "Unknown"}]})
    client, _ = make_client(Upstream(ok(tm_payload(event))), places)
    with client:
        client.post("/api/outings/generate", json=BODY)
    query = parse_qs(places.requests[0].content.decode())["data"][0]
    assert "around:3500,43.900000,-78.900000" in query


def test_invalid_destination_retries_without_destination():
    class RetryPlaces(OverpassPlaceService):
        def __init__(self, settings):
            super().__init__(settings, transport=httpx.MockTransport(Upstream(ok({"elements": []}))))
            self.requests = []
        def search(self, request, subject):
            self.requests.append(request)
            if len(self.requests) == 1:
                from app.errors import ApiError
                raise ApiError(422, "invalid_place_destination", "outside")
            return super().search(request, subject)

    settings = Settings(_env_file=None, auth_required=False, ticketmaster_api_key=FAKE_KEY)
    events = TicketmasterEventService(settings, transport=httpx.MockTransport(Upstream(ok(tm_payload(tm_event("e"))))), clock=lambda: FIXED_NOW)
    places = RetryPlaces(settings)
    transit = TransitService(FakeTransitRepository([]), settings)
    app = create_app(settings, FakeTransitRepository([]), event_service=events, place_service=places, outing_orchestrator=OutingOrchestrator(events, places, transit))
    with TestClient(app) as client:
        response = client.post("/api/outings/generate", json=BODY)
    assert response.status_code == 200
    assert places.requests[1].destination_latitude is None


def test_events_upstream_failure_is_partial_success():
    client, _ = make_client(Upstream(httpx.Response(502)), Upstream(ok({"elements": []})))
    with client:
        response = client.post("/api/outings/generate", json=BODY)
    assert response.status_code == 200
    assert response.json()["sourceStatus"]["events"]["status"] == "unavailable"
    assert not response.json()["recommendations"]


def test_places_upstream_failure_summary_does_not_report_zero_places():
    client, _ = make_client(
        Upstream(ok(tm_payload())),
        Upstream(httpx.Response(504)),
    )
    with client:
        response = client.post("/api/outings/generate", json=BODY)
    description = response.json()["summary"]["description"]
    assert response.status_code == 200
    assert "0 places" not in description
    assert "Places could not be searched" in description
    assert "places_upstream_timeout" in description


def test_transit_unsupported_is_partial_success():
    client, _ = make_client(Upstream(ok(tm_payload())), Upstream(ok({"elements": []})))
    with client:
        response = client.post("/api/outings/generate", json={"startingLocation": "Courtice, Ontario", "outingRequest": "Things to do"})
    assert response.status_code == 200
    assert response.json()["sourceStatus"]["transit"]["code"] == "unsupported_area"


def test_events_unsupported_is_rejected():
    client, _ = make_client(Upstream(ok(tm_payload())), Upstream(ok({"elements": []})))
    with client:
        response = client.post("/api/outings/generate", json={"startingLocation": "Sudbury", "outingRequest": "Find a park in Thunder Bay"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_event_area"


def test_missing_transit_records_are_partial_success():
    client, _ = make_client(Upstream(ok(tm_payload())), Upstream(ok({"elements": []})))
    with client:
        response = client.post("/api/outings/generate", json=BODY)
    assert response.json()["sourceStatus"]["transit"]["code"] == "no_transit_records"
    assert response.json()["transit"]["status"] == "unavailable"


def test_itinerary_has_only_timed_events():
    untimed = tm_event("untimed")
    untimed["dates"]["start"].pop("localTime")
    client, _ = make_client(Upstream(ok(tm_payload(tm_event("timed"), untimed))), Upstream(ok({"elements": []})))
    with client:
        body = client.post("/api/outings/generate", json=BODY).json()
    assert [item["id"] for item in body["itinerary"]] == ["timed"]
    assert all(not item["id"].startswith("osm-") for item in body["itinerary"])


def test_police_incidents_are_always_unavailable():
    client, _ = make_client(Upstream(ok(tm_payload())), Upstream(ok({"elements": []})))
    with client:
        body = client.post("/api/outings/generate", json=BODY).json()
    assert body["policeIncidents"] == {"status": "unavailable", "reason": "No public-safety data source is implemented."}


def test_requires_authentication():
    settings = Settings(_env_file=None, auth_required=True)
    app = create_app(settings, FakeTransitRepository([]))
    with TestClient(app) as client:
        response = client.post("/api/outings/generate", json=BODY)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_access_token"
