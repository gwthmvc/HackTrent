"""Ticketmaster Discovery API v2 event search.

The Ticketmaster API key is read from server settings only. It is sent solely as
a query parameter to Ticketmaster and is never logged, cached, or returned.
"""
from __future__ import annotations

import logging
import math
import re
import threading
import time as monotonic_time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from .config import Settings
from .errors import ApiError
from .models import (
    EventPriceRange,
    EventSearchRequest,
    EventSearchResponse,
    EventSearchWindow,
    EventVenue,
    TicketmasterEvent,
)

logger = logging.getLogger(__name__)

# httpx logs full request URLs (including the apikey query parameter) at INFO.
for _noisy_logger in ("httpx", "httpcore"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

LOCAL_TZ = ZoneInfo("America/Toronto")
MAX_DAYS_AHEAD = 365
DEFAULT_WINDOW_DAYS = 14
UPSTREAM_PAGE_SIZE = 50


# --- Areas -------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EventArea:
    area_id: str
    name: str
    latitude: float
    longitude: float
    radius_km: int
    terms: tuple[str, ...]
    transit_coverage: bool


EVENT_AREAS: dict[str, EventArea] = {
    "durham": EventArea(
        area_id="durham",
        name="Durham Region",
        latitude=43.9000,
        longitude=-78.9000,
        radius_km=35,
        terms=(
            "durham", "oshawa", "whitby", "ajax", "pickering", "clarington",
            "bowmanville", "uxbridge", "scugog", "port perry", "courtice", "brooklin",
        ),
        transit_coverage=True,
    ),
    "kingston": EventArea(
        area_id="kingston",
        name="Kingston",
        latitude=44.2312,
        longitude=-76.4860,
        radius_km=25,
        terms=("kingston",),
        transit_coverage=True,
    ),
}


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)


def _first_position(value: str, area: EventArea) -> int | None:
    positions = [match.start() for term in area.terms if (match := _term_pattern(term).search(value))]
    return min(positions) if positions else None


def resolve_area(starting_location: str, outing_request: str) -> EventArea:
    """Prefer an area named in the request that differs from the start, then any
    area in the request, then the starting location."""

    def matches(value: str) -> dict[str, int]:
        found: dict[str, int] = {}
        for area_id, area in EVENT_AREAS.items():
            position = _first_position(value, area)
            if position is not None:
                found[area_id] = position
        return found

    start_matches = matches(starting_location)
    request_matches = matches(outing_request)
    destination = {k: v for k, v in request_matches.items() if k not in start_matches}
    for candidates in (destination, request_matches, start_matches):
        if candidates:
            return EVENT_AREAS[min(candidates, key=candidates.__getitem__)]

    supported = ", ".join(area.name for area in EVENT_AREAS.values())
    raise ApiError(
        status_code=422,
        code="unsupported_event_area",
        message=f"No supported event area was found in the request. Initial coverage: {supported}.",
    )


# --- Interests ---------------------------------------------------------------

INTEREST_CLASSIFICATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Hockey", ("hockey", "ohl", "frontenacs", "generals")),
    ("Comedy", ("comedy", "comedian", "stand-up", "standup")),
    ("Theatre", ("theatre", "theater", "musical", "play", "broadway")),
    ("Classical", ("symphony", "orchestra", "classical", "opera")),
    ("Jazz", ("jazz",)),
    ("Country", ("country music",)),
    ("Rock", ("rock",)),
    ("Music", ("concert", "music", "band", "gig", "live show")),
    ("Sports", ("sports", "game", "basketball", "soccer", "baseball", "football", "lacrosse")),
    ("Arts & Theatre", ("arts", "art", "dance", "ballet", "magic")),
    ("Family", ("family", "kids", "kid", "children", "child", "daughter", "son")),
    ("Film", ("movie", "film", "cinema")),
)
MAX_CLASSIFICATIONS = 4


def resolve_classifications(outing_request: str, interests: list[str]) -> list[str]:
    text = " ".join([outing_request, *interests]).casefold()
    selected = [
        name for name, terms in INTEREST_CLASSIFICATIONS
        if any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)
    ]
    return selected[:MAX_CLASSIFICATIONS]


# --- Dates and times ---------------------------------------------------------

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
TIME_OF_DAY = {
    "morning": (time(6, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "evening": (time(17, 0), time(23, 59)),
    "night": (time(17, 0), time(23, 59)),
    "tonight": (time(17, 0), time(23, 59)),
}
_ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_MONTH_DAY = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)
_WEEKDAY = re.compile(r"\b(?:(this|next)\s+)?(" + "|".join(WEEKDAYS) + r")s?\b", re.IGNORECASE)
_CLOCK = re.compile(r"\b(at|after|around|by|from)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SearchWindow:
    start: datetime  # aware, local
    end: datetime  # aware, local
    time_range: tuple[time, time] | None
    description: str


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, time(0, 0), LOCAL_TZ),
        datetime.combine(day, time(23, 59, 59), LOCAL_TZ),
    )


def _shift(value: time, minutes: int) -> time:
    total = max(0, min(23 * 60 + 59, value.hour * 60 + value.minute + minutes))
    return time(total // 60, total % 60)


def _parse_time_range(text: str, time_override: str | None) -> tuple[tuple[time, time] | None, str | None]:
    if time_override:
        hour, minute = (int(part) for part in time_override.split(":"))
        chosen = time(hour, minute)
        return (_shift(chosen, -60), _shift(chosen, 180)), f"around {chosen.strftime('%H:%M')}"

    clock = _CLOCK.search(text)
    if clock:
        hour = int(clock.group(2)) % 12 + (12 if clock.group(4).lower() == "pm" else 0)
        minute = int(clock.group(3) or 0)
        if hour <= 23 and minute <= 59:
            chosen = time(hour, minute)
            if clock.group(1).lower() in ("after", "from"):
                return (chosen, time(23, 59)), f"after {chosen.strftime('%H:%M')}"
            if clock.group(1).lower() == "by":
                return (time(0, 0), chosen), f"by {chosen.strftime('%H:%M')}"
            return (_shift(chosen, -60), _shift(chosen, 180)), f"around {chosen.strftime('%H:%M')}"

    for word, bounds in TIME_OF_DAY.items():
        if re.search(rf"\b{word}\b", text):
            return bounds, word
    return None, None


def resolve_window(
    outing_request: str,
    date_override: date | None,
    time_override: str | None,
    now: datetime,
) -> SearchWindow:
    now_local = now.astimezone(LOCAL_TZ)
    today = now_local.date()
    text = outing_request.casefold()
    start_day: date
    end_day: date
    label: str

    if date_override is not None:
        start_day = end_day = date_override
        label = date_override.isoformat()
    elif iso := _ISO_DATE.search(text):
        try:
            start_day = end_day = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError as error:
            raise ApiError(422, "invalid_event_date", "The requested event date is not a valid date.") from error
        label = start_day.isoformat()
    elif month_day := _MONTH_DAY.search(text):
        month = MONTHS[month_day.group(1).lower()[:4] if month_day.group(1).lower().startswith("sept") else month_day.group(1).lower()[:3]]
        try:
            candidate = date(today.year, month, int(month_day.group(2)))
            if candidate < today:
                candidate = date(today.year + 1, month, int(month_day.group(2)))
        except ValueError as error:
            raise ApiError(422, "invalid_event_date", "The requested event date is not a valid date.") from error
        start_day = end_day = candidate
        label = candidate.isoformat()
    elif re.search(r"\b(today|tonight)\b", text):
        start_day = end_day = today
        label = "today"
    elif re.search(r"\btomorrow\b", text):
        start_day = end_day = today + timedelta(days=1)
        label = "tomorrow"
    elif re.search(r"\bweekend\b", text):
        days_to_saturday = (5 - today.weekday()) % 7
        if today.weekday() == 6:
            start_day = end_day = today
        else:
            start_day = today + timedelta(days=days_to_saturday)
            end_day = start_day + timedelta(days=1)
        label = "this weekend"
    elif weekday := _WEEKDAY.search(text):
        target = WEEKDAYS.index(weekday.group(2).lower())
        days_ahead = (target - today.weekday()) % 7
        if weekday.group(1) and weekday.group(1).lower() == "next" and days_ahead == 0:
            days_ahead = 7
        start_day = end_day = today + timedelta(days=days_ahead)
        label = weekday.group(2).capitalize()
    else:
        start_day = today
        end_day = today + timedelta(days=DEFAULT_WINDOW_DAYS)
        label = f"next {DEFAULT_WINDOW_DAYS} days"

    if end_day < today:
        raise ApiError(422, "invalid_event_date", "The requested event date is in the past.")
    if start_day > today + timedelta(days=MAX_DAYS_AHEAD):
        raise ApiError(422, "invalid_event_date", "Event searches are limited to the next 12 months.")

    start, _ = _day_bounds(max(start_day, today))
    _, end = _day_bounds(end_day)
    if start.date() == today:
        # Floor to the hour so repeated searches share a cache entry.
        start = max(start, now_local.replace(minute=0, second=0, microsecond=0))

    time_range, time_label = _parse_time_range(text, time_override)
    description = label if not time_label else f"{label}, {time_label}"
    return SearchWindow(start=start, end=end, time_range=time_range, description=description)


# --- Caching and rate limiting -----------------------------------------------

class TTLCache:
    def __init__(self, ttl_seconds: int, max_entries: int = 128, clock: Callable[[], float] = monotonic_time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._items: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple) -> Any | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= self._clock():
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: tuple, value: Any) -> None:
        with self._lock:
            self._items[key] = (self._clock() + self._ttl, value)
            self._items.move_to_end(key)
            while len(self._items) > self._max:
                self._items.popitem(last=False)


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = monotonic_time.monotonic) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def try_acquire(self, key: str = "global") -> bool:
        with self._lock:
            now = self._clock()
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True


# --- Ticketmaster client -----------------------------------------------------

ALLOWED_LINK_HOSTS = ("ticketmaster.ca", "ticketmaster.com", "livenation.com", "universe.com")
ALLOWED_IMAGE_HOSTS = ("ticketm.net", "ticketmaster.com", "ticketmaster.ca")


def _host_allowed(url: object, allowed: tuple[str, ...]) -> str | None:
    if not isinstance(url, str):
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not any(host == h or host.endswith("." + h) for h in allowed):
        return None
    return url


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _as_float(value: object) -> float | None:
    try:
        number = float(value)  # Ticketmaster sends coordinates as strings.
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _text(value: object, limit: int = 240) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None


def parse_event(raw: dict[str, Any], area: EventArea) -> TicketmasterEvent | None:
    event_id = _text(raw.get("id"), 64)
    name = _text(raw.get("name"))
    dates = raw.get("dates") if isinstance(raw.get("dates"), dict) else {}
    start = dates.get("start") if isinstance(dates.get("start"), dict) else {}
    local_date = _text(start.get("localDate"), 10)
    if not event_id or not name or not local_date:
        return None
    try:
        date.fromisoformat(local_date)
    except ValueError:
        return None

    status = _text((dates.get("status") or {}).get("code") if isinstance(dates.get("status"), dict) else None, 32)
    if status == "cancelled":
        return None

    local_time = _text(start.get("localTime"), 8)
    if local_time and not re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", local_time):
        local_time = None
    start_utc: datetime | None = None
    if isinstance(start.get("dateTime"), str):
        try:
            start_utc = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
        except ValueError:
            start_utc = None

    price: EventPriceRange | None = None
    for candidate in raw.get("priceRanges") or []:
        if not isinstance(candidate, dict):
            continue
        low, high = _as_float(candidate.get("min")), _as_float(candidate.get("max"))
        if low is None and high is None:
            continue
        price = EventPriceRange(min=low, max=high, currency=_text(candidate.get("currency"), 3) or "CAD")
        break

    venues = (raw.get("_embedded") or {}).get("venues") if isinstance(raw.get("_embedded"), dict) else None
    venue_raw = venues[0] if isinstance(venues, list) and venues and isinstance(venues[0], dict) else {}
    location = venue_raw.get("location") if isinstance(venue_raw.get("location"), dict) else {}
    latitude, longitude = _as_float(location.get("latitude")), _as_float(location.get("longitude"))
    coordinate_status = "verified"
    if latitude is None or longitude is None or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        latitude = longitude = None
        coordinate_status = "missing"
    elif (latitude, longitude) == (0.0, 0.0) or _haversine_km(
        area.latitude, area.longitude, latitude, longitude,
    ) > area.radius_km * 1.5:
        latitude = longitude = None
        coordinate_status = "outside_search_area"

    address = venue_raw.get("address") if isinstance(venue_raw.get("address"), dict) else {}
    venue = EventVenue(
        name=_text(venue_raw.get("name")) or "Venue not listed",
        address=_text(address.get("line1")),
        city=_text((venue_raw.get("city") or {}).get("name") if isinstance(venue_raw.get("city"), dict) else None, 80),
        province=_text((venue_raw.get("state") or {}).get("stateCode") if isinstance(venue_raw.get("state"), dict) else None, 8),
        postal_code=_text(venue_raw.get("postalCode"), 12),
        latitude=latitude,
        longitude=longitude,
        coordinate_status=coordinate_status,
    )

    image_url = None
    images = [img for img in raw.get("images") or [] if isinstance(img, dict)]
    images.sort(key=lambda img: (img.get("ratio") != "16_9", -min(int(img.get("width") or 0), 1024)))
    for image in images:
        if (url := _host_allowed(image.get("url"), ALLOWED_IMAGE_HOSTS)):
            image_url = url
            break

    classification = None
    classifications = raw.get("classifications")
    if isinstance(classifications, list) and classifications and isinstance(classifications[0], dict):
        first = classifications[0]
        parts = [
            _text((first.get(level) or {}).get("name"), 40) if isinstance(first.get(level), dict) else None
            for level in ("segment", "genre")
        ]
        names = [p for p in parts if p and p.lower() != "undefined"]
        classification = " · ".join(dict.fromkeys(names)) or None

    return TicketmasterEvent(
        id=event_id,
        name=name,
        url=_host_allowed(raw.get("url"), ALLOWED_LINK_HOSTS),
        start_local_date=local_date,
        start_local_time=local_time[:5] if local_time else None,
        start_date_time=start_utc,
        status=status,
        price_range=price,
        venue=venue,
        image_url=image_url,
        classification=classification,
    )


def _within_time_range(event: TicketmasterEvent, time_range: tuple[time, time] | None) -> bool:
    if time_range is None or event.start_local_time is None:
        return True  # Unknown start times are kept and labelled "time to be announced".
    hour, minute = (int(part) for part in event.start_local_time.split(":"))
    return time_range[0] <= time(hour, minute) <= time_range[1]


@dataclass(slots=True)
class _CachedSearch:
    events: list[TicketmasterEvent]
    total_available: int


@dataclass
class TicketmasterEventService:
    settings: Settings
    transport: httpx.BaseTransport | None = None
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self._cache = TTLCache(self.settings.events_cache_ttl_seconds)
        self._minute_limiter = SlidingWindowLimiter(self.settings.ticketmaster_max_requests_per_minute, 60)
        self._day_limiter = SlidingWindowLimiter(self.settings.ticketmaster_max_requests_per_day, 86_400)
        self._user_limiter = SlidingWindowLimiter(self.settings.events_max_searches_per_user_per_minute, 60)
        self.upstream_calls = 0

    @property
    def configured(self) -> bool:
        key = self.settings.ticketmaster_api_key
        return bool(key and key.get_secret_value().strip())

    def search(self, request: EventSearchRequest, subject: str) -> EventSearchResponse:
        area = resolve_area(request.starting_location, request.outing_request)
        now = self.clock()
        window = resolve_window(request.outing_request, request.date, request.time, now)
        classifications = resolve_classifications(request.outing_request, request.interests)

        if not self.configured:
            raise ApiError(503, "events_not_configured", "Ticketmaster event search is not configured on the server.")
        if not self._user_limiter.try_acquire(subject):
            raise ApiError(429, "events_rate_limited", "Too many event searches. Please wait a minute and try again.")

        params = {
            "latlong": f"{area.latitude},{area.longitude}",
            "radius": str(area.radius_km),
            "unit": "km",
            "countryCode": "CA",
            "locale": "*",
            "sort": "date,asc",
            "size": str(UPSTREAM_PAGE_SIZE),
            "startDateTime": window.start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": window.end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if classifications:
            params["classificationName"] = ",".join(classifications)

        cache_key = tuple(sorted(params.items()))
        cached = self._cache.get(cache_key)
        if cached is None:
            cached = self._fetch(params, area)
            self._cache.set(cache_key, cached)
            from_cache = False
        else:
            from_cache = True

        events = [event for event in cached.events if _within_time_range(event, window.time_range)]
        events = events[: self.settings.events_max_results]
        return EventSearchResponse(
            area_id=area.area_id,
            area_name=area.name,
            transit_coverage=area.transit_coverage,
            retrieved_at=now,
            cached=from_cache,
            window=EventSearchWindow(
                start=window.start,
                end=window.end,
                description=window.description,
                time_from=window.time_range[0].strftime("%H:%M") if window.time_range else None,
                time_to=window.time_range[1].strftime("%H:%M") if window.time_range else None,
            ),
            classifications=classifications,
            total_available=cached.total_available,
            events=events,
        )

    def _fetch(self, params: dict[str, str], area: EventArea) -> _CachedSearch:
        if not self._minute_limiter.try_acquire() or not self._day_limiter.try_acquire():
            raise ApiError(429, "events_rate_limited", "Event search is temporarily rate limited. Please try again shortly.")

        api_key = self.settings.ticketmaster_api_key.get_secret_value().strip()  # type: ignore[union-attr]
        self.upstream_calls += 1
        try:
            with httpx.Client(
                base_url=self.settings.ticketmaster_base_url,
                timeout=self.settings.ticketmaster_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = client.get("/events.json", params={**params, "apikey": api_key})
        except httpx.TimeoutException:
            logger.warning("Ticketmaster request timed out")
            raise ApiError(504, "events_upstream_timeout", "Ticketmaster took too long to respond.") from None
        except httpx.HTTPError as error:
            logger.warning("Ticketmaster request failed (%s)", type(error).__name__)
            raise ApiError(502, "events_upstream_error", "Ticketmaster is currently unavailable.") from None

        if response.status_code == 429:
            logger.warning("Ticketmaster quota or rate limit reached")
            raise ApiError(429, "events_rate_limited", "Ticketmaster's request limit was reached. Please try again later.")
        if response.status_code in (401, 403):
            logger.error("Ticketmaster rejected the server API key (status %s)", response.status_code)
            raise ApiError(502, "events_upstream_auth", "Ticketmaster rejected the server's API credentials.")
        if response.status_code != 200:
            logger.warning("Ticketmaster returned status %s", response.status_code)
            raise ApiError(502, "events_upstream_error", "Ticketmaster returned an unexpected response.")

        try:
            body = response.json()
        except ValueError:
            raise ApiError(502, "events_upstream_error", "Ticketmaster returned an unreadable response.") from None
        if not isinstance(body, dict):
            raise ApiError(502, "events_upstream_error", "Ticketmaster returned an unexpected response.")

        raw_events = (body.get("_embedded") or {}).get("events") if isinstance(body.get("_embedded"), dict) else []
        page = body.get("page") if isinstance(body.get("page"), dict) else {}
        total = page.get("totalElements") if isinstance(page.get("totalElements"), int) else 0

        events: list[TicketmasterEvent] = []
        seen: set[str] = set()
        for raw in raw_events if isinstance(raw_events, list) else []:
            if not isinstance(raw, dict):
                continue
            event = parse_event(raw, area)
            if event and event.id not in seen:
                seen.add(event.id)
                events.append(event)
        return _CachedSearch(events=events, total_available=max(total, len(events)))
