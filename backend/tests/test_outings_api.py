import io
import zipfile
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import ApiError
from app.events import TicketmasterEventService
from app.gtfs import GtfsImporter, GtfsJourneyService
from app.main import create_app
from app.models import EventSearchResponse, EventSearchWindow, EventVenue, TicketmasterEvent
from app.outings import OutingOrchestrator
from app.places import OverpassPlaceService
from app.repository import PositionRecord
from app.service import TransitService

FAKE_KEY = "fake-ticketmaster-key-123"
FIXED_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)


def journey_gtfs_archive() -> bytes:
    files = {
        "agency.txt": (
            "agency_id,agency_name,agency_url,agency_timezone\n"
            "DRT,Durham Region Transit,https://www.durhamregiontransit.com,America/Toronto\n"
        ),
        "routes.txt": (
            "route_id,route_short_name,route_long_name,route_type\n"
            "R1,901,Campus Express,3\n"
        ),
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,Ontario Tech / Durham College,43.9450,-78.8960\n"
            "B,Simcoe Street Terminal,43.9000,-78.8600\n"
            "C,Arena Station,43.8970,-78.8600\n"
            "D,No Service Venue,43.8970,-78.8500\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "SVC,1,1,1,1,1,1,1,20261101,20261130\n"
        ),
        "calendar_dates.txt": "service_id,date,exception_type\n",
        "trips.txt": (
            "route_id,service_id,trip_id,trip_headsign,direction_id,shape_id\n"
            "R1,SVC,T1,Arena,0,SH1\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type,shape_dist_traveled\n"
            "T1,08:00:00,08:00:00,A,1,0,0,0\n"
            "T1,08:25:00,08:25:00,C,2,0,0,7500\n"
        ),
        "shapes.txt": (
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\n"
            "SH1,43.945,-78.896,1,0\nSH1,43.897,-78.860,2,7500\n"
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class JourneyEventService:
    configured = True

    def __init__(self, venue_latitude: float | None = 43.8970, venue_longitude: float | None = -78.8600) -> None:
        verified = venue_latitude is not None and venue_longitude is not None
        self.event = TicketmasterEvent(
            id="journey-event",
            name="Journey Event",
            url="https://ticketmaster.example/journey-event",
            start_local_date="2026-11-14",
            start_local_time="19:30:00",
            start_date_time=datetime(2026, 11, 15, 0, 30, tzinfo=timezone.utc),
            status=None,
            price_range=None,
            venue=EventVenue(
                name="Journey Venue",
                address="1 Main Street",
                city="Oshawa",
                province="ON",
                postal_code=None,
                latitude=venue_latitude,
                longitude=venue_longitude,
                coordinate_status="verified" if verified else "missing",
            ),
            image_url=None,
            classification=None,
        )

    def search(self, request, subject) -> EventSearchResponse:
        return EventSearchResponse(
            area_id="durham",
            area_name="Durham Region",
            transit_coverage=True,
            retrieved_at=FIXED_NOW,
            cached=True,
            window=EventSearchWindow(
                start=FIXED_NOW,
                end=FIXED_NOW + timedelta(days=1),
                description="test",
                time_from=None,
                time_to=None,
            ),
            classifications=[],
            total_available=1,
            events=[self.event],
        )


class ErrorJourneyService:
    def search(self, request):
        raise ApiError(503, "journey_fixture_error", "Journey fixture failed.")


def journey_client(tmp_path, *, starting_location="Durham College, Oshawa", venue_latitude=43.8970, venue_longitude=-78.8600, journey_service=None):
    settings = Settings(
        _env_file=None,
        auth_required=False,
        ticketmaster_api_key=FAKE_KEY,
        gtfs_cache_dir=tmp_path,
    )
    GtfsImporter(settings).import_archive(journey_gtfs_archive(), {})
    event_service = JourneyEventService(venue_latitude, venue_longitude)
    place_service = OverpassPlaceService(
        settings,
        transport=httpx.MockTransport(Upstream(ok({"elements": []}))),
        clock=lambda: FIXED_NOW,
    )
    transit_service = TransitService(FakeTransitRepository([]), settings)
    orchestrator = OutingOrchestrator(
        event_service,
        place_service,
        transit_service,
        journey_service or GtfsJourneyService(settings),
    )
    app = create_app(
        settings,
        FakeTransitRepository([]),
        event_service=event_service,
        place_service=place_service,
        journey_service=journey_service or GtfsJourneyService(settings),
        outing_orchestrator=orchestrator,
    )
    return TestClient(app), starting_location


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


def place_payload(*elements: dict) -> dict:
    places = list(elements) or [{
        "type": "node", "id": 1, "lat": 43.9005, "lon": -78.8995,
        "tags": {"name": "Local Cafe", "amenity": "cafe"},
    }]
    return {
        "elements": places,
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


def test_outing_places_match_place_search():
    place_elements = [
        {
            "type": "node", "id": 11, "lat": 43.9005, "lon": -78.8995,
            "tags": {"name": "Cafe One", "amenity": "cafe"},
        },
        {
            "type": "node", "id": 12, "lat": 43.901, "lon": -78.898,
            "tags": {"name": "Cafe Two", "amenity": "restaurant"},
        },
    ]
    client, _ = make_client(
        Upstream(ok(tm_payload())),
        Upstream(ok(place_payload(*place_elements))),
    )
    with client:
        body = client.post("/api/outings/generate", json=BODY).json()

    places = body["places"]
    assert places["areaId"] == "durham"
    assert places["anchor"] == {
        "name": "Oshawa search area",
        "latitude": 43.9,
        "longitude": -78.9,
        "kind": "area_center",
    }
    assert places["radiusMeters"] == 3_500
    assert places["totalAvailable"] == 2
    assert [place["id"] for place in places["places"]] == ["osm-node-11", "osm-node-12"]
    assert [place["distanceMeters"] for place in places["places"]] == [69, 195]


def test_outing_places_null_when_unavailable():
    client, _ = make_client(
        Upstream(ok(tm_payload())),
        Upstream(httpx.Response(504)),
    )
    with client:
        body = client.post("/api/outings/generate", json=BODY).json()

    assert body["places"] is None
    assert body["sourceStatus"]["places"]["status"] == "unavailable"


def test_outing_places_empty_when_none_found():
    client, _ = make_client(
        Upstream(ok(tm_payload())),
        Upstream(ok({"elements": []})),
    )
    with client:
        body = client.post("/api/outings/generate", json=BODY).json()

    assert body["places"]["places"] == []
    assert body["places"]["totalAvailable"] == 0
    assert body["sourceStatus"]["places"]["status"] == "available"


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


def test_journey_available_with_durham_college_origin(tmp_path):
    client, _ = journey_client(tmp_path)
    with client:
        response = client.post(
            "/api/outings/generate",
            json={
                "startingLocation": "Durham College, Oshawa",
                "outingRequest": "Things to do",
                "date": "2026-11-09",
                "time": "07:30",
            },
        )
    journeys = response.json()["journeys"]
    assert response.status_code == 200
    assert journeys["status"] == "available"
    assert journeys["items"]


def test_journey_requires_departure_time(tmp_path):
    client, _ = journey_client(tmp_path)
    with client:
        body = client.post(
            "/api/outings/generate",
            json={
                "startingLocation": "Durham College, Oshawa",
                "outingRequest": "Things to do",
                "date": "2026-11-09",
            },
        ).json()
    assert body["journeys"]["status"] == "unavailable"
    assert body["journeys"]["code"] == "departure_time_required"


def test_journey_rejects_origin_not_durham_college(tmp_path):
    client, _ = journey_client(tmp_path, starting_location="Oshawa, Ontario")
    with client:
        body = client.post(
            "/api/outings/generate",
            json={
                "startingLocation": "Oshawa, Ontario",
                "outingRequest": "Things to do",
                "date": "2026-11-09",
                "time": "07:30",
            },
        ).json()
    assert body["journeys"]["status"] == "unavailable"
    assert body["journeys"]["code"] == "origin_not_supported"


def test_journey_requires_verified_destination(tmp_path):
    client, _ = journey_client(
        tmp_path,
        venue_latitude=None,
        venue_longitude=None,
    )
    with client:
        body = client.post(
            "/api/outings/generate",
            json={
                "startingLocation": "Durham College, Oshawa",
                "outingRequest": "Things to do",
                "date": "2026-11-09",
                "time": "07:30",
            },
        ).json()
    assert body["journeys"]["status"] == "unavailable"
    assert body["journeys"]["code"] == "no_verified_destination"


def test_journey_service_error_is_unavailable(tmp_path):
    client, _ = journey_client(tmp_path, journey_service=ErrorJourneyService())
    with client:
        body = client.post(
            "/api/outings/generate",
            json={
                "startingLocation": "Durham College, Oshawa",
                "outingRequest": "Things to do",
                "date": "2026-11-09",
                "time": "07:30",
            },
        ).json()
    assert body["journeys"]["status"] == "unavailable"
    assert body["journeys"]["code"] == "journey_fixture_error"
    assert body["journeys"]["items"] == []


def test_journey_no_direct_trip_is_empty_success(tmp_path):
    client, _ = journey_client(
        tmp_path,
        venue_latitude=43.8970,
        venue_longitude=-78.8500,
    )
    with client:
        body = client.post(
            "/api/outings/generate",
            json={
                "startingLocation": "Durham College, Oshawa",
                "outingRequest": "Things to do",
                "date": "2026-11-09",
                "time": "07:30",
            },
        ).json()
    assert body["journeys"]["status"] == "available"
    assert body["journeys"]["items"] == []
    assert "No direct scheduled trip found." in body["journeys"]["limitations"]
