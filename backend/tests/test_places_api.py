"""OpenStreetMap place discovery tests. Every upstream response is mocked."""
from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.places import OverpassPlaceService

from test_transit_api import FakeTransitRepository

FIXED_NOW = datetime(2026, 11, 8, 1, 0, tzinfo=timezone.utc)
DURHAM_BODY = {
    "startingLocation": "Durham College, Oshawa, Ontario",
    "outingRequest": "Find somewhere to eat near an Oshawa Generals game",
}


def element(
    element_id: int,
    *,
    element_type: str = "node",
    latitude: float = 43.9005,
    longitude: float = -78.8995,
    tags: dict | None = None,
) -> dict:
    value = {
        "type": element_type,
        "id": element_id,
        "tags": tags or {"name": f"Place {element_id}", "amenity": "restaurant"},
    }
    if element_type == "node":
        value.update({"lat": latitude, "lon": longitude})
    else:
        value["center"] = {"lat": latitude, "lon": longitude}
    return value


def payload(*elements: dict) -> dict:
    return {
        "version": 0.6,
        "generator": "Overpass API",
        "osm3s": {"timestamp_osm_base": "2026-11-08T00:59:00Z"},
        "elements": list(elements),
    }


class Upstream:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_client(upstream: Upstream, **overrides) -> tuple[TestClient, OverpassPlaceService]:
    settings = Settings(_env_file=None, auth_required=False, **overrides)
    service = OverpassPlaceService(
        settings,
        transport=httpx.MockTransport(upstream),
        clock=lambda: FIXED_NOW,
    )
    app = create_app(
        settings,
        FakeTransitRepository([]),
        place_service=service,
    )
    return TestClient(app), service


def test_returns_verified_places_and_bounded_query() -> None:
    upstream = Upstream(httpx.Response(200, json=payload(
        element(1, tags={
            "name": "Grounded Kitchen",
            "amenity": "restaurant",
            "addr:housenumber": "10",
            "addr:street": "King Street",
            "addr:city": "Oshawa",
            "addr:postcode": "L1H 1A1",
        }),
        element(2, element_type="way", latitude=43.902, longitude=-78.898, tags={
            "name": "Source Park",
            "leisure": "park",
        }),
        element(3, tags={"name": "Local Museum", "tourism": "museum"}),
        element(4, tags={"name": "Family Cinema", "amenity": "cinema"}),
        element(5, tags={"amenity": "cafe"}),
        element(6, latitude=44.5, longitude=-79.5),
    )))
    client, service = make_client(upstream)

    with client:
        response = client.post("/api/places/search", json=DURHAM_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["areaId"] == "durham"
    assert body["anchor"]["kind"] == "area_center"
    assert body["radiusMeters"] == 3_500
    assert body["dataTimestamp"] == "2026-11-08T00:59:00Z"
    assert body["source"]["name"] == "OpenStreetMap contributors"
    assert {place["category"] for place in body["places"]} == {
        "food",
        "culture",
        "entertainment_family",
        "parks_outdoors",
    }
    restaurant = next(place for place in body["places"] if place["name"] == "Grounded Kitchen")
    assert restaurant["address"] == "10 King Street, Oshawa, L1H 1A1"
    assert restaurant["sourceUrl"] == "https://www.openstreetmap.org/node/1"
    assert all(place["distanceMeters"] >= 0 for place in body["places"])
    assert service.upstream_calls == 1
    assert len(upstream.requests) == 1

    request = upstream.requests[0]
    query = parse_qs(request.content.decode())["data"][0]
    assert request.method == "POST"
    assert request.headers["user-agent"].startswith("SmartMoveOntario/")
    assert "[out:json][timeout:12][maxsize:8000000]" in query
    assert "around:3500,43.900000,-78.900000" in query
    assert "cafe|restaurant" in query
    assert "museum|gallery" not in query
    assert query.count("nwr(") == 1
    assert "out center 60" in query


def test_verified_destination_controls_anchor_and_radius() -> None:
    upstream = Upstream(httpx.Response(200, json=payload()))
    client, _ = make_client(upstream)
    body = {
        **DURHAM_BODY,
        "destinationName": "Verified event venue",
        "destinationLatitude": 43.897,
        "destinationLongitude": -78.86,
    }

    with client:
        response = client.post("/api/places/search", json=body)

    assert response.status_code == 200
    assert response.json()["anchor"] == {
        "name": "Verified event venue",
        "latitude": 43.897,
        "longitude": -78.86,
        "kind": "verified_destination",
    }
    assert response.json()["radiusMeters"] == 2_000
    query = parse_qs(upstream.requests[0].content.decode())["data"][0]
    assert "around:2000,43.897000,-78.860000" in query


def test_results_are_cached_and_sorted_by_distance() -> None:
    upstream = Upstream(httpx.Response(200, json=payload(
        element(10, latitude=43.91, longitude=-78.9),
        element(11, latitude=43.9001, longitude=-78.9),
    )))
    client, service = make_client(upstream)

    with client:
        first = client.post("/api/places/search", json=DURHAM_BODY)
        second = client.post("/api/places/search", json=DURHAM_BODY)

    assert first.status_code == second.status_code == 200
    assert [place["id"] for place in first.json()["places"]] == [
        "osm-node-11",
        "osm-node-10",
    ]
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert service.upstream_calls == 1


def test_missing_address_remains_null_without_invented_fields() -> None:
    upstream = Upstream(httpx.Response(200, json=payload(element(20))))
    client, _ = make_client(upstream)

    with client:
        response = client.post("/api/places/search", json=DURHAM_BODY)

    place = response.json()["places"][0]
    assert place["address"] is None
    assert "rating" not in place
    assert "price" not in place
    assert "openingHours" not in place
    assert "travelTime" not in place


def test_unsupported_area_and_invalid_destination_do_not_call_overpass() -> None:
    upstream = Upstream(httpx.Response(200, json=payload()))
    client, service = make_client(upstream)

    with client:
        unsupported = client.post("/api/places/search", json={
            "startingLocation": "Sudbury",
            "outingRequest": "Find a park in Thunder Bay",
        })
        outside = client.post("/api/places/search", json={
            **DURHAM_BODY,
            "destinationLatitude": 45.42,
            "destinationLongitude": -75.69,
        })

    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "unsupported_event_area"
    assert outside.status_code == 422
    assert outside.json()["error"]["code"] == "invalid_place_destination"
    assert service.upstream_calls == 0


@pytest.mark.parametrize("upstream_response, status, code", [
    (httpx.Response(429), 429, "places_rate_limited"),
    (httpx.Response(504), 504, "places_upstream_timeout"),
    (httpx.Response(500), 502, "places_upstream_error"),
    (httpx.Response(200, text="not json"), 502, "places_upstream_error"),
    (httpx.ReadTimeout("timed out"), 504, "places_upstream_timeout"),
    (httpx.ConnectError("failed"), 502, "places_upstream_error"),
])
def test_upstream_failures_are_sanitized(upstream_response, status, code) -> None:
    client, _ = make_client(Upstream(upstream_response))

    with client:
        response = client.post("/api/places/search", json=DURHAM_BODY)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    if code == "places_upstream_timeout":
        assert "Events and transit are still available" in response.json()["error"]["message"]


def test_timeout_failures_are_cached_without_a_second_upstream_call() -> None:
    upstream = Upstream(httpx.ReadTimeout("timed out"))
    client, service = make_client(upstream)

    with client:
        first = client.post("/api/places/search", json=DURHAM_BODY)
        second = client.post("/api/places/search", json=DURHAM_BODY)

    assert first.status_code == second.status_code == 504
    assert first.json()["error"]["code"] == second.json()["error"]["code"] == "places_upstream_timeout"
    assert service.upstream_calls == 1
    assert len(upstream.requests) == 1


def test_kingston_area_uses_smaller_radius() -> None:
    upstream = Upstream(httpx.Response(200, json=payload()))
    client, _ = make_client(upstream)

    with client:
        response = client.post("/api/places/search", json={
            "startingLocation": "Kingston, Ontario",
            "outingRequest": "Find a museum in Kingston",
        })

    assert response.status_code == 200
    assert response.json()["areaId"] == "kingston"
    assert response.json()["radiusMeters"] == 3_500


def test_broad_prompt_combines_filters_without_duplicate_tag_scans() -> None:
    upstream = Upstream(httpx.Response(200, json=payload()))
    client, _ = make_client(upstream)

    with client:
        response = client.post("/api/places/search", json={
            "startingLocation": "Kingston, Ontario",
            "outingRequest": "Show me interesting places in Kingston",
        })

    assert response.status_code == 200
    query = parse_qs(upstream.requests[0].content.decode())["data"][0]
    assert query.count('["amenity"~') == 1
    assert query.count('["leisure"~') == 1
    assert query.count('["tourism"~') == 1
    assert query.count('["boundary"~') == 1
    assert query.count("nwr(") == 4


def test_different_intents_use_distinct_cache_entries() -> None:
    upstream = Upstream(httpx.Response(200, json=payload()))
    client, service = make_client(upstream)

    with client:
        food = client.post("/api/places/search", json=DURHAM_BODY)
        parks = client.post("/api/places/search", json={
            **DURHAM_BODY,
            "outingRequest": "Find a park in Oshawa",
        })

    assert food.status_code == parks.status_code == 200
    assert service.upstream_calls == 2
    food_query = parse_qs(upstream.requests[0].content.decode())["data"][0]
    park_query = parse_qs(upstream.requests[1].content.decode())["data"][0]
    assert '["amenity"~' in food_query
    assert '["leisure"~' in park_query
    assert food_query != park_query
