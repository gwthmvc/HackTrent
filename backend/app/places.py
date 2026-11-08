"""Bounded OpenStreetMap place discovery through the public Overpass API.

The service sends one compact query for named places near a supported search
anchor. Results contain only source-backed OSM fields; ratings, prices, hours,
availability, routes, and travel times are intentionally outside this contract.
"""
from __future__ import annotations

import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from .config import Settings
from .errors import ApiError
from .events import EVENT_AREAS, EventArea, SlidingWindowLimiter, TTLCache, resolve_area
from .models import (
    DiscoveredPlace,
    PlaceCategory,
    PlaceSearchAnchor,
    PlaceSearchRequest,
    PlaceSearchResponse,
)

logger = logging.getLogger(__name__)

for _noisy_logger in ("httpx", "httpcore"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

AREA_RADIUS_METERS = {"durham": 3_500, "kingston": 3_500}
DESTINATION_RADIUS_METERS = 2_000
OVERPASS_ELEMENT_LIMIT = 60
OVERPASS_MAXSIZE_BYTES = 8_000_000

FOOD_AMENITIES = {"restaurant", "cafe"}
PARK_LEISURE = {"park", "garden", "nature_reserve"}
CULTURE_TOURISM = {"museum", "gallery", "artwork", "attraction", "viewpoint"}
CULTURE_AMENITIES = {"arts_centre"}
ENTERTAINMENT_AMENITIES = {"cinema", "theatre"}
ENTERTAINMENT_LEISURE = {
    "amusement_arcade",
    "bowling_alley",
    "escape_game",
    "playground",
    "sports_centre",
    "water_park",
}
ENTERTAINMENT_TOURISM = {"zoo", "aquarium", "theme_park"}

CATEGORY_KEYWORDS: dict[PlaceCategory, set[str]] = {
    "food": {
        "breakfast", "brunch", "cafe", "cafes", "coffee", "dining", "dinner",
        "eat", "eating", "food", "lunch", "meal", "restaurant", "restaurants", "snack",
    },
    "parks_outdoors": {
        "garden", "gardens", "hike", "hiking", "nature", "outdoor", "outdoors", "park",
        "parks", "picnic", "trail", "trails", "viewpoint",
    },
    "culture": {
        "art", "arts", "attraction", "attractions", "cultural", "culture", "gallery",
        "galleries", "heritage", "museum", "museums",
    },
    "entertainment_family": {
        "aquarium", "arcade", "bowling", "children", "cinema", "entertainment", "escape",
        "family", "kid", "kids", "movie", "movies", "playground", "sports", "theater",
        "theatre", "theme", "zoo",
    },
}
ALL_CATEGORIES: frozenset[PlaceCategory] = frozenset(CATEGORY_KEYWORDS)


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(value))


def _clean_text(value: object, limit: int = 240) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None


def _as_coordinate(value: object, minimum: float, maximum: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and minimum <= number <= maximum else None


def _category(tags: dict[str, Any]) -> tuple[PlaceCategory, str] | None:
    amenity = _clean_text(tags.get("amenity"), 60)
    leisure = _clean_text(tags.get("leisure"), 60)
    tourism = _clean_text(tags.get("tourism"), 60)
    boundary = _clean_text(tags.get("boundary"), 60)

    if amenity in FOOD_AMENITIES:
        return "food", amenity.replace("_", " ").title()
    if leisure in PARK_LEISURE or boundary == "protected_area":
        subtype = leisure or "protected area"
        return "parks_outdoors", subtype.replace("_", " ").title()
    if tourism in CULTURE_TOURISM or amenity in CULTURE_AMENITIES:
        subtype = tourism or amenity or "cultural attraction"
        return "culture", subtype.replace("_", " ").title()
    if (
        amenity in ENTERTAINMENT_AMENITIES
        or leisure in ENTERTAINMENT_LEISURE
        or tourism in ENTERTAINMENT_TOURISM
    ):
        subtype = amenity or leisure or tourism or "entertainment"
        return "entertainment_family", subtype.replace("_", " ").title()
    return None


def _address(tags: dict[str, Any]) -> str | None:
    if full := _clean_text(tags.get("addr:full")):
        return full
    street = _clean_text(tags.get("addr:street"), 120)
    number = _clean_text(tags.get("addr:housenumber"), 30)
    city = _clean_text(tags.get("addr:city"), 80)
    postcode = _clean_text(tags.get("addr:postcode"), 16)
    street_line = " ".join(part for part in (number, street) if part)
    parts = [part for part in (street_line or None, city, postcode) if part]
    return ", ".join(parts) if parts else None


def _coordinates(raw: dict[str, Any]) -> tuple[float, float] | None:
    coordinate_source = raw if raw.get("type") == "node" else raw.get("center")
    if not isinstance(coordinate_source, dict):
        return None
    latitude = _as_coordinate(coordinate_source.get("lat"), -90, 90)
    longitude = _as_coordinate(coordinate_source.get("lon"), -180, 180)
    if latitude is None or longitude is None or (latitude, longitude) == (0.0, 0.0):
        return None
    return latitude, longitude


def parse_place(
    raw: dict[str, Any],
    anchor: PlaceSearchAnchor,
    radius_meters: int,
) -> DiscoveredPlace | None:
    element_type = raw.get("type")
    element_id = raw.get("id")
    if element_type not in {"node", "way", "relation"} or not isinstance(element_id, int):
        return None
    tags = raw.get("tags") if isinstance(raw.get("tags"), dict) else {}
    name = _clean_text(tags.get("name"))
    classification = _category(tags)
    coordinates = _coordinates(raw)
    if not name or classification is None or coordinates is None:
        return None

    latitude, longitude = coordinates
    distance = _haversine_meters(
        anchor.latitude,
        anchor.longitude,
        latitude,
        longitude,
    )
    if distance > radius_meters * 1.25:
        return None

    category, subtype = classification
    return DiscoveredPlace(
        id=f"osm-{element_type}-{element_id}",
        name=name,
        category=category,
        subtype=subtype,
        address=_address(tags),
        latitude=latitude,
        longitude=longitude,
        distance_meters=max(0, round(distance)),
        source_url=f"https://www.openstreetmap.org/{element_type}/{element_id}",
    )


def _anchor_for(request: PlaceSearchRequest, area: EventArea) -> tuple[PlaceSearchAnchor, int]:
    if request.destination_latitude is not None and request.destination_longitude is not None:
        distance_from_area = _haversine_meters(
            area.latitude,
            area.longitude,
            request.destination_latitude,
            request.destination_longitude,
        )
        if distance_from_area > area.radius_km * 1_500:
            raise ApiError(
                422,
                "invalid_place_destination",
                "The verified destination is outside the supported search area.",
            )
        return (
            PlaceSearchAnchor(
                name=_clean_text(request.destination_name) or "Verified destination",
                latitude=request.destination_latitude,
                longitude=request.destination_longitude,
                kind="verified_destination",
            ),
            DESTINATION_RADIUS_METERS,
        )

    label = "Oshawa search area" if area.area_id == "durham" else "Kingston search area"
    return (
        PlaceSearchAnchor(
            name=label,
            latitude=area.latitude,
            longitude=area.longitude,
            kind="area_center",
        ),
        AREA_RADIUS_METERS[area.area_id],
    )


def infer_categories(outing_request: str) -> frozenset[PlaceCategory]:
    """Select explicit place intents; broad prompts retain every supported category."""
    tokens = set(re.findall(r"[a-z0-9]+", outing_request.casefold()))
    selected = frozenset(
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if tokens & keywords
    )
    return selected or ALL_CATEGORIES


def _query_filters(categories: frozenset[PlaceCategory]) -> dict[str, set[str]]:
    filters: dict[str, set[str]] = {}

    def include(key: str, values: set[str]) -> None:
        filters.setdefault(key, set()).update(values)

    if "food" in categories:
        include("amenity", FOOD_AMENITIES)
    if "parks_outdoors" in categories:
        include("leisure", PARK_LEISURE)
        include("boundary", {"protected_area"})
    if "culture" in categories:
        include("tourism", CULTURE_TOURISM)
        include("amenity", CULTURE_AMENITIES)
    if "entertainment_family" in categories:
        include("amenity", ENTERTAINMENT_AMENITIES)
        include("leisure", ENTERTAINMENT_LEISURE)
        include("tourism", ENTERTAINMENT_TOURISM)
    return filters


def build_query(
    anchor: PlaceSearchAnchor,
    radius_meters: int,
    timeout_seconds: int,
    categories: frozenset[PlaceCategory],
) -> str:
    around = f"around:{radius_meters},{anchor.latitude:.6f},{anchor.longitude:.6f}"
    selectors = []
    for key, values in sorted(_query_filters(categories).items()):
        regex = "|".join(sorted(values))
        selectors.append(f'  nwr({around})["name"]["{key}"~"^({regex})$"];')
    return "\n".join((
        f"[out:json][timeout:{timeout_seconds}][maxsize:{OVERPASS_MAXSIZE_BYTES}];",
        "(",
        *selectors,
        ");",
        f"out center {OVERPASS_ELEMENT_LIMIT};",
    ))


@dataclass(slots=True)
class _CachedPlaces:
    places: list[DiscoveredPlace]
    total_available: int
    data_timestamp: datetime | None


@dataclass
class OverpassPlaceService:
    settings: Settings
    transport: httpx.BaseTransport | None = None
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self._cache = TTLCache(self.settings.places_cache_ttl_seconds)
        self._minute_limiter = SlidingWindowLimiter(
            self.settings.overpass_max_requests_per_minute,
            60,
        )
        self._user_limiter = SlidingWindowLimiter(
            self.settings.places_max_searches_per_user_per_minute,
            60,
        )
        self._upstream_lock = threading.Lock()
        self.upstream_calls = 0

    @property
    def configured(self) -> bool:
        return bool(self.settings.overpass_base_url and self.settings.overpass_user_agent)

    def search(self, request: PlaceSearchRequest, subject: str) -> PlaceSearchResponse:
        area = resolve_area(request.starting_location, request.outing_request)
        anchor, radius_meters = _anchor_for(request, area)
        categories = infer_categories(request.outing_request)
        if not self.configured:
            raise ApiError(503, "places_not_configured", "OpenStreetMap place search is not configured.")
        if not self._user_limiter.try_acquire(subject):
            raise ApiError(429, "places_rate_limited", "Too many place searches. Please wait a minute.")

        cache_key = (
            area.area_id,
            round(anchor.latitude, 5),
            round(anchor.longitude, 5),
            radius_meters,
            tuple(sorted(categories)),
        )
        cached = self._cache.get(cache_key)
        from_cache = cached is not None
        if cached is None:
            with self._upstream_lock:
                cached = self._cache.get(cache_key)
                from_cache = cached is not None
                if cached is None:
                    query = build_query(
                        anchor,
                        radius_meters,
                        self.settings.overpass_query_timeout_seconds,
                        categories,
                    )
                    cached = self._fetch(query, anchor, radius_meters)
                    self._cache.set(cache_key, cached)

        return PlaceSearchResponse(
            area_id=area.area_id,
            area_name=area.name,
            anchor=anchor,
            radius_meters=radius_meters,
            retrieved_at=self.clock(),
            data_timestamp=cached.data_timestamp,
            cached=from_cache,
            total_available=cached.total_available,
            places=cached.places[: self.settings.places_max_results],
        )

    def _fetch(
        self,
        query: str,
        anchor: PlaceSearchAnchor,
        radius_meters: int,
    ) -> _CachedPlaces:
        if not self._minute_limiter.try_acquire():
            raise ApiError(429, "places_rate_limited", "OpenStreetMap place search is temporarily rate limited.")

        self.upstream_calls += 1
        started_at = time.perf_counter()
        try:
            with httpx.Client(
                timeout=self.settings.overpass_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
                headers={
                    "Accept": "application/json",
                    "User-Agent": self.settings.overpass_user_agent,
                },
            ) as client:
                response = client.post(
                    self.settings.overpass_base_url,
                    data={"data": query},
                )
        except httpx.TimeoutException:
            elapsed = time.perf_counter() - started_at
            logger.warning("Overpass request timed out after %.1f seconds", elapsed)
            raise ApiError(
                504,
                "places_upstream_timeout",
                "Place discovery is temporarily unavailable because OpenStreetMap did not respond in time. Events and transit are still available.",
            ) from None
        except httpx.HTTPError as error:
            logger.warning("Overpass request failed (%s)", type(error).__name__)
            raise ApiError(502, "places_upstream_error", "OpenStreetMap place search is unavailable.") from None

        if response.status_code in {429, 504}:
            logger.warning("Overpass load limit reached (status %s)", response.status_code)
            status = 429 if response.status_code == 429 else 504
            code = "places_rate_limited" if status == 429 else "places_upstream_timeout"
            raise ApiError(
                status,
                code,
                "Place discovery is temporarily unavailable. Events and transit are still available.",
            )
        if response.status_code != 200:
            logger.warning("Overpass returned status %s", response.status_code)
            raise ApiError(502, "places_upstream_error", "OpenStreetMap returned an unexpected response.")
        if len(response.content) > self.settings.overpass_max_response_bytes:
            raise ApiError(502, "places_upstream_error", "OpenStreetMap returned too much data.")

        try:
            body = response.json()
        except ValueError:
            raise ApiError(502, "places_upstream_error", "OpenStreetMap returned unreadable data.") from None
        if not isinstance(body, dict):
            raise ApiError(502, "places_upstream_error", "OpenStreetMap returned an unexpected response.")

        timestamp: datetime | None = None
        osm3s = body.get("osm3s") if isinstance(body.get("osm3s"), dict) else {}
        raw_timestamp = osm3s.get("timestamp_osm_base")
        if isinstance(raw_timestamp, str):
            try:
                timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            except ValueError:
                timestamp = None

        places: list[DiscoveredPlace] = []
        seen: set[str] = set()
        elements = body.get("elements") if isinstance(body.get("elements"), list) else []
        for raw in elements:
            if not isinstance(raw, dict):
                continue
            place = parse_place(raw, anchor, radius_meters)
            if place and place.id not in seen:
                seen.add(place.id)
                places.append(place)
        places.sort(key=lambda place: (place.distance_meters, place.name.casefold()))
        return _CachedPlaces(
            places=places,
            total_available=len(places),
            data_timestamp=timestamp,
        )
