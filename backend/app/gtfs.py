"""Validated GTFS static-schedule cache and direct-trip journey search.

GTFS schedules are stored in a local SQLite cache that is deliberately separate
from TigerData vehicle observations. Runtime searches are read-only and never
interpret a vehicle position as an arrival prediction.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from .config import Settings
from .errors import ApiError
from .models import (
    GtfsFeedMetadata,
    JourneyPointInput,
    ScheduledStop,
    ScheduledTransitJourney,
    TransitJourneySearchRequest,
    TransitJourneySearchResponse,
)

DURHAM_AGENCY_ID = "durham"
REQUIRED_FILES = {
    "agency.txt",
    "routes.txt",
    "stops.txt",
    "trips.txt",
    "stop_times.txt",
}
CALENDAR_FILES = {"calendar.txt", "calendar_dates.txt"}
REQUIRED_COLUMNS = {
    "agency.txt": {"agency_name", "agency_timezone"},
    "routes.txt": {"route_id", "route_short_name", "route_long_name", "route_type"},
    "stops.txt": {"stop_id", "stop_name", "stop_lat", "stop_lon"},
    "trips.txt": {"route_id", "service_id", "trip_id", "shape_id"},
    "stop_times.txt": {
        "trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence",
    },
    "calendar.txt": {
        "service_id", "monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday", "start_date", "end_date",
    },
    "calendar_dates.txt": {"service_id", "date", "exception_type"},
    "shapes.txt": {"shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"},
}
WEEKDAY_COLUMNS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)


class GtfsValidationError(ValueError):
    """The downloaded archive does not satisfy the schedule contract."""


@dataclass(frozen=True, slots=True)
class GtfsImportResult:
    status: str
    agency_id: str
    database_path: Path
    version: str | None
    valid_from: date | None
    valid_until: date | None
    counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class _Stop:
    stop_id: str
    name: str
    latitude: float
    longitude: float


def _parse_gtfs_date(value: str, context: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y%m%d").date()
    except ValueError:
        raise GtfsValidationError(f"{context} must use YYYYMMDD format") from None


def _parse_gtfs_time(value: str, context: str) -> int:
    match = re.fullmatch(r"(\d{1,2}):([0-5]\d):([0-5]\d)", value.strip())
    if not match:
        raise GtfsValidationError(f"{context} is not a valid GTFS time")
    hours, minutes, seconds = (int(part) for part in match.groups())
    if hours > 47:
        raise GtfsValidationError(f"{context} exceeds the supported 47-hour service window")
    return hours * 3_600 + minutes * 60 + seconds


def _float(value: str, minimum: float, maximum: float, context: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise GtfsValidationError(f"{context} must be numeric") from None
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise GtfsValidationError(f"{context} is outside its valid range")
    return parsed


def _integer(value: str, minimum: int, context: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise GtfsValidationError(f"{context} must be an integer") from None
    if parsed < minimum:
        raise GtfsValidationError(f"{context} is outside its valid range")
    return parsed


def _required(value: str | None, context: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise GtfsValidationError(f"{context} is required")
    return cleaned


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(value))


def _chunks(rows: Iterable[tuple], size: int = 5_000) -> Iterator[list[tuple]]:
    batch: list[tuple] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE metadata (
            agency_id TEXT PRIMARY KEY,
            source_url TEXT NOT NULL,
            source_etag TEXT,
            source_last_modified TEXT,
            archive_sha256 TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            timezone TEXT NOT NULL,
            valid_from TEXT NOT NULL,
            valid_until TEXT NOT NULL,
            counts_json TEXT NOT NULL
        );
        CREATE TABLE routes (
            route_id TEXT PRIMARY KEY,
            route_short_name TEXT NOT NULL,
            route_long_name TEXT NOT NULL,
            route_type INTEGER NOT NULL
        );
        CREATE TABLE stops (
            stop_id TEXT PRIMARY KEY,
            stop_name TEXT NOT NULL,
            stop_lat REAL NOT NULL,
            stop_lon REAL NOT NULL
        );
        CREATE TABLE calendar (
            service_id TEXT PRIMARY KEY,
            monday INTEGER NOT NULL,
            tuesday INTEGER NOT NULL,
            wednesday INTEGER NOT NULL,
            thursday INTEGER NOT NULL,
            friday INTEGER NOT NULL,
            saturday INTEGER NOT NULL,
            sunday INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        );
        CREATE TABLE calendar_dates (
            service_id TEXT NOT NULL,
            service_date TEXT NOT NULL,
            exception_type INTEGER NOT NULL,
            PRIMARY KEY (service_id, service_date)
        );
        CREATE TABLE trips (
            trip_id TEXT PRIMARY KEY,
            route_id TEXT NOT NULL REFERENCES routes(route_id),
            service_id TEXT NOT NULL,
            trip_headsign TEXT,
            direction_id INTEGER,
            shape_id TEXT
        );
        CREATE TABLE stop_times (
            trip_id TEXT NOT NULL REFERENCES trips(trip_id),
            stop_id TEXT NOT NULL REFERENCES stops(stop_id),
            stop_sequence INTEGER NOT NULL,
            arrival_seconds INTEGER NOT NULL,
            departure_seconds INTEGER NOT NULL,
            pickup_type INTEGER NOT NULL,
            drop_off_type INTEGER NOT NULL,
            shape_dist_traveled REAL,
            PRIMARY KEY (trip_id, stop_sequence)
        );
        CREATE TABLE shapes (
            shape_id TEXT NOT NULL,
            shape_pt_sequence INTEGER NOT NULL,
            shape_pt_lat REAL NOT NULL,
            shape_pt_lon REAL NOT NULL,
            shape_dist_traveled REAL,
            PRIMARY KEY (shape_id, shape_pt_sequence)
        );
        CREATE INDEX idx_stop_times_stop_departure
            ON stop_times(stop_id, departure_seconds);
        CREATE INDEX idx_trips_service_route ON trips(service_id, route_id);
        CREATE INDEX idx_calendar_dates_date ON calendar_dates(service_date);
        CREATE INDEX idx_shapes_id_sequence ON shapes(shape_id, shape_pt_sequence);
        """,
    )


class _Archive:
    def __init__(self, content: bytes, max_uncompressed_bytes: int) -> None:
        try:
            self.zip_file = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile:
            raise GtfsValidationError("The GTFS download is not a valid ZIP archive") from None
        names = {Path(name).name for name in self.zip_file.namelist() if not name.endswith("/")}
        missing = REQUIRED_FILES - names
        if missing:
            raise GtfsValidationError(f"GTFS archive is missing: {', '.join(sorted(missing))}")
        if not names & CALENDAR_FILES:
            raise GtfsValidationError("GTFS archive needs calendar.txt or calendar_dates.txt")
        total_size = sum(info.file_size for info in self.zip_file.infolist())
        if total_size > max_uncompressed_bytes:
            raise GtfsValidationError("GTFS archive expands beyond the configured size limit")
        self.names = names

    def rows(self, name: str) -> Iterator[tuple[int, dict[str, str]]]:
        if name not in self.names:
            return
        with self.zip_file.open(name) as binary:
            with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
                reader = csv.DictReader(text)
                fields = set(reader.fieldnames or [])
                missing = REQUIRED_COLUMNS[name] - fields
                if missing:
                    raise GtfsValidationError(
                        f"{name} is missing columns: {', '.join(sorted(missing))}",
                    )
                for row_number, row in enumerate(reader, start=2):
                    yield row_number, row


class GtfsImporter:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    @property
    def database_path(self) -> Path:
        return self.settings.gtfs_cache_dir / f"{DURHAM_AGENCY_ID}.sqlite3"

    def _existing_metadata(self) -> sqlite3.Row | None:
        if not self.database_path.is_file():
            return None
        try:
            connection = sqlite3.connect(self.database_path)
            connection.row_factory = sqlite3.Row
            return connection.execute("SELECT * FROM metadata WHERE agency_id = ?", (DURHAM_AGENCY_ID,)).fetchone()
        except sqlite3.Error:
            return None
        finally:
            if "connection" in locals():
                connection.close()

    def sync(self) -> GtfsImportResult:
        existing = self._existing_metadata()
        headers = {"User-Agent": self.settings.gtfs_user_agent}
        if existing:
            if existing["source_etag"]:
                headers["If-None-Match"] = existing["source_etag"]
            if existing["source_last_modified"]:
                headers["If-Modified-Since"] = existing["source_last_modified"]

        try:
            with httpx.Client(
                timeout=self.settings.gtfs_request_timeout_seconds,
                transport=self.transport,
                follow_redirects=True,
            ) as client:
                with client.stream("GET", self.settings.gtfs_durham_feed_url, headers=headers) as response:
                    if response.status_code == 304 and existing:
                        return self._result_from_metadata("unchanged", existing)
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > self.settings.gtfs_max_archive_bytes:
                            raise GtfsValidationError("GTFS download exceeds the configured size limit")
                    source_headers = {
                        "etag": response.headers.get("etag"),
                        "last_modified": response.headers.get("last-modified"),
                    }
        except httpx.TimeoutException:
            raise ApiError(504, "gtfs_download_timeout", "The Durham GTFS feed did not respond in time.") from None
        except httpx.HTTPError as error:
            raise ApiError(502, "gtfs_download_failed", f"The Durham GTFS feed could not be downloaded ({type(error).__name__}).") from None

        return self.import_archive(bytes(content), source_headers)

    def import_archive(
        self,
        content: bytes,
        source_headers: dict[str, str | None] | None = None,
    ) -> GtfsImportResult:
        if len(content) > self.settings.gtfs_max_archive_bytes:
            raise GtfsValidationError("GTFS download exceeds the configured size limit")
        archive_hash = hashlib.sha256(content).hexdigest()
        existing = self._existing_metadata()
        if existing and existing["archive_sha256"] == archive_hash:
            return self._result_from_metadata("unchanged", existing)

        archive = _Archive(content, self.settings.gtfs_max_uncompressed_bytes)
        cache_dir = self.settings.gtfs_cache_dir.resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=".sqlite3.tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)

        try:
            connection = sqlite3.connect(temporary_path)
            _schema(connection)
            metadata = self._load(connection, archive, archive_hash, source_headers or {})
            connection.commit()
            connection.close()
            os.replace(temporary_path, self.database_path)
        except Exception:
            if "connection" in locals():
                connection.close()
            temporary_path.unlink(missing_ok=True)
            raise
        return self._result_from_metadata("updated", metadata)

    def _load(
        self,
        connection: sqlite3.Connection,
        archive: _Archive,
        archive_hash: str,
        source_headers: dict[str, str | None],
    ) -> dict[str, object]:
        counts: dict[str, int] = {}
        agency_rows = list(archive.rows("agency.txt"))
        if not agency_rows:
            raise GtfsValidationError("agency.txt has no records")
        timezone_name = _required(agency_rows[0][1].get("agency_timezone"), "agency timezone")
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            raise GtfsValidationError("agency timezone is not installed or recognized") from None

        route_ids: set[str] = set()
        route_rows = []
        for row_number, row in archive.rows("routes.txt"):
            route_id = _required(row.get("route_id"), f"routes.txt row {row_number} route_id")
            route_ids.add(route_id)
            route_rows.append((
                route_id,
                (row.get("route_short_name") or "").strip(),
                (row.get("route_long_name") or "").strip(),
                _integer(row.get("route_type") or "", 0, f"routes.txt row {row_number} route_type"),
            ))
        if not route_rows:
            raise GtfsValidationError("routes.txt has no records")
        connection.executemany("INSERT INTO routes VALUES (?, ?, ?, ?)", route_rows)
        counts["routes"] = len(route_rows)

        stop_ids: set[str] = set()
        stop_rows = []
        for row_number, row in archive.rows("stops.txt"):
            stop_id = _required(row.get("stop_id"), f"stops.txt row {row_number} stop_id")
            stop_ids.add(stop_id)
            stop_rows.append((
                stop_id,
                _required(row.get("stop_name"), f"stops.txt row {row_number} stop_name"),
                _float(row.get("stop_lat") or "", -90, 90, f"stops.txt row {row_number} latitude"),
                _float(row.get("stop_lon") or "", -180, 180, f"stops.txt row {row_number} longitude"),
            ))
        if not stop_rows:
            raise GtfsValidationError("stops.txt has no records")
        connection.executemany("INSERT INTO stops VALUES (?, ?, ?, ?)", stop_rows)
        counts["stops"] = len(stop_rows)

        service_ids: set[str] = set()
        coverage_dates: list[date] = []
        calendar_rows = []
        if "calendar.txt" in archive.names:
            for row_number, row in archive.rows("calendar.txt"):
                service_id = _required(row.get("service_id"), f"calendar.txt row {row_number} service_id")
                values = [_integer(row.get(day) or "", 0, f"calendar.txt row {row_number} {day}") for day in WEEKDAY_COLUMNS]
                if any(value not in {0, 1} for value in values):
                    raise GtfsValidationError(f"calendar.txt row {row_number} has invalid weekday flags")
                start = _parse_gtfs_date(row.get("start_date") or "", f"calendar.txt row {row_number} start_date")
                end = _parse_gtfs_date(row.get("end_date") or "", f"calendar.txt row {row_number} end_date")
                if end < start:
                    raise GtfsValidationError(f"calendar.txt row {row_number} ends before it starts")
                service_ids.add(service_id)
                coverage_dates.extend((start, end))
                calendar_rows.append((service_id, *values, start.isoformat(), end.isoformat()))
        connection.executemany("INSERT INTO calendar VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", calendar_rows)
        counts["calendar"] = len(calendar_rows)

        exception_rows = []
        if "calendar_dates.txt" in archive.names:
            for row_number, row in archive.rows("calendar_dates.txt"):
                service_id = _required(row.get("service_id"), f"calendar_dates.txt row {row_number} service_id")
                service_date = _parse_gtfs_date(row.get("date") or "", f"calendar_dates.txt row {row_number} date")
                exception_type = _integer(row.get("exception_type") or "", 1, f"calendar_dates.txt row {row_number} exception_type")
                if exception_type not in {1, 2}:
                    raise GtfsValidationError(f"calendar_dates.txt row {row_number} has invalid exception_type")
                service_ids.add(service_id)
                coverage_dates.append(service_date)
                exception_rows.append((service_id, service_date.isoformat(), exception_type))
        connection.executemany("INSERT INTO calendar_dates VALUES (?, ?, ?)", exception_rows)
        counts["calendar_dates"] = len(exception_rows)
        if not service_ids or not coverage_dates:
            raise GtfsValidationError("The GTFS feed has no service calendar coverage")

        trip_ids: set[str] = set()
        relevant_shape_ids: set[str] = set()
        trip_rows = []
        for row_number, row in archive.rows("trips.txt"):
            trip_id = _required(row.get("trip_id"), f"trips.txt row {row_number} trip_id")
            route_id = _required(row.get("route_id"), f"trips.txt row {row_number} route_id")
            service_id = _required(row.get("service_id"), f"trips.txt row {row_number} service_id")
            if route_id not in route_ids:
                raise GtfsValidationError(f"trips.txt row {row_number} references an unknown route")
            if service_id not in service_ids:
                raise GtfsValidationError(f"trips.txt row {row_number} references an unknown service")
            shape_id = (row.get("shape_id") or "").strip() or None
            if shape_id:
                relevant_shape_ids.add(shape_id)
            direction_text = (row.get("direction_id") or "").strip()
            direction_id = _integer(direction_text, 0, f"trips.txt row {row_number} direction_id") if direction_text else None
            trip_ids.add(trip_id)
            trip_rows.append((
                trip_id,
                route_id,
                service_id,
                (row.get("trip_headsign") or "").strip() or None,
                direction_id,
                shape_id,
            ))
        if not trip_rows:
            raise GtfsValidationError("trips.txt has no records")
        connection.executemany("INSERT INTO trips VALUES (?, ?, ?, ?, ?, ?)", trip_rows)
        counts["trips"] = len(trip_rows)

        stop_time_count = 0

        def stop_time_rows() -> Iterator[tuple]:
            nonlocal stop_time_count
            for row_number, row in archive.rows("stop_times.txt"):
                trip_id = _required(row.get("trip_id"), f"stop_times.txt row {row_number} trip_id")
                stop_id = _required(row.get("stop_id"), f"stop_times.txt row {row_number} stop_id")
                if trip_id not in trip_ids or stop_id not in stop_ids:
                    raise GtfsValidationError(f"stop_times.txt row {row_number} references an unknown trip or stop")
                arrival = _parse_gtfs_time(row.get("arrival_time") or "", f"stop_times.txt row {row_number} arrival_time")
                departure = _parse_gtfs_time(row.get("departure_time") or "", f"stop_times.txt row {row_number} departure_time")
                if departure < arrival:
                    raise GtfsValidationError(f"stop_times.txt row {row_number} departs before arrival")
                distance_text = (row.get("shape_dist_traveled") or "").strip()
                distance = _float(distance_text, 0, float("inf"), f"stop_times.txt row {row_number} shape distance") if distance_text else None
                stop_time_count += 1
                yield (
                    trip_id,
                    stop_id,
                    _integer(row.get("stop_sequence") or "", 0, f"stop_times.txt row {row_number} stop_sequence"),
                    arrival,
                    departure,
                    _integer((row.get("pickup_type") or "0").strip() or "0", 0, f"stop_times.txt row {row_number} pickup_type"),
                    _integer((row.get("drop_off_type") or "0").strip() or "0", 0, f"stop_times.txt row {row_number} drop_off_type"),
                    distance,
                )

        for batch in _chunks(stop_time_rows()):
            connection.executemany("INSERT INTO stop_times VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch)
        if not stop_time_count:
            raise GtfsValidationError("stop_times.txt has no records")
        counts["stop_times"] = stop_time_count

        found_shape_ids: set[str] = set()
        shape_count = 0
        if relevant_shape_ids:
            if "shapes.txt" not in archive.names:
                raise GtfsValidationError("Trips reference shapes but shapes.txt is missing")

            def shape_rows() -> Iterator[tuple]:
                nonlocal shape_count
                for row_number, row in archive.rows("shapes.txt"):
                    shape_id = _required(row.get("shape_id"), f"shapes.txt row {row_number} shape_id")
                    if shape_id not in relevant_shape_ids:
                        continue
                    found_shape_ids.add(shape_id)
                    distance_text = (row.get("shape_dist_traveled") or "").strip()
                    distance = _float(distance_text, 0, float("inf"), f"shapes.txt row {row_number} shape distance") if distance_text else None
                    shape_count += 1
                    yield (
                        shape_id,
                        _integer(row.get("shape_pt_sequence") or "", 0, f"shapes.txt row {row_number} sequence"),
                        _float(row.get("shape_pt_lat") or "", -90, 90, f"shapes.txt row {row_number} latitude"),
                        _float(row.get("shape_pt_lon") or "", -180, 180, f"shapes.txt row {row_number} longitude"),
                        distance,
                    )

            for batch in _chunks(shape_rows()):
                connection.executemany("INSERT INTO shapes VALUES (?, ?, ?, ?, ?)", batch)
            missing_shapes = relevant_shape_ids - found_shape_ids
            if missing_shapes:
                raise GtfsValidationError("One or more trips reference missing shape records")
        counts["shapes"] = shape_count

        imported_at = datetime.now(timezone.utc)
        valid_from, valid_until = min(coverage_dates), max(coverage_dates)
        metadata = {
            "agency_id": DURHAM_AGENCY_ID,
            "source_url": self.settings.gtfs_durham_feed_url,
            "source_etag": source_headers.get("etag"),
            "source_last_modified": source_headers.get("last_modified"),
            "archive_sha256": archive_hash,
            "imported_at": imported_at.isoformat(),
            "timezone": timezone_name,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
            "counts_json": json.dumps(counts, sort_keys=True),
        }
        connection.execute(
            "INSERT INTO metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(metadata.values()),
        )
        return metadata

    def _result_from_metadata(self, status: str, metadata: sqlite3.Row | dict[str, object]) -> GtfsImportResult:
        counts_value = metadata["counts_json"]
        counts = json.loads(str(counts_value)) if counts_value else {}
        version_value = str(metadata["archive_sha256"])
        return GtfsImportResult(
            status=status,
            agency_id=DURHAM_AGENCY_ID,
            database_path=self.database_path,
            version=version_value[:12],
            valid_from=date.fromisoformat(str(metadata["valid_from"])),
            valid_until=date.fromisoformat(str(metadata["valid_until"])),
            counts=counts,
        )


class GtfsJourneyService:
    def __init__(self, settings: Settings, clock=lambda: datetime.now(timezone.utc)) -> None:
        self.settings = settings
        self.clock = clock
        self.database_path = settings.gtfs_cache_dir / f"{DURHAM_AGENCY_ID}.sqlite3"

    @property
    def available(self) -> bool:
        return self.database_path.is_file()

    def _connect(self) -> sqlite3.Connection:
        if not self.available:
            raise ApiError(
                503,
                "gtfs_schedule_unavailable",
                "Durham scheduled transit data has not been imported yet.",
            )
        try:
            connection = sqlite3.connect(f"file:{self.database_path.as_posix()}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return connection
        except sqlite3.Error:
            raise ApiError(503, "gtfs_schedule_unavailable", "Durham scheduled transit data is unavailable.") from None

    def search(self, request: TransitJourneySearchRequest) -> TransitJourneySearchResponse:
        if request.agency_id != DURHAM_AGENCY_ID:
            raise ApiError(422, "unsupported_schedule_agency", "Schedule search currently supports Durham Region Transit only.")
        with closing(self._connect()) as connection:
            metadata = connection.execute("SELECT * FROM metadata WHERE agency_id = ?", (DURHAM_AGENCY_ID,)).fetchone()
            if metadata is None:
                raise ApiError(503, "gtfs_schedule_unavailable", "Durham scheduled transit data is unavailable.")
            valid_from = date.fromisoformat(metadata["valid_from"])
            valid_until = date.fromisoformat(metadata["valid_until"])
            if not valid_from <= request.service_date <= valid_until:
                raise ApiError(
                    422,
                    "schedule_date_outside_feed",
                    f"The imported Durham schedule covers {valid_from.isoformat()} through {valid_until.isoformat()}.",
                )
            timezone_info = ZoneInfo(metadata["timezone"])
            origin_stops = self._resolve_stops(connection, request.origin, request.max_walking_distance_meters)
            destination_stops = self._resolve_stops(connection, request.destination, request.max_walking_distance_meters)
            if not origin_stops:
                raise ApiError(404, "origin_stop_not_found", "No Durham GTFS stop matched the requested origin.")
            if not destination_stops:
                raise ApiError(404, "destination_stop_not_found", "No Durham GTFS stop matched the requested destination.")
            active_services = self._active_services(connection, request.service_date)
            if not active_services:
                raise ApiError(404, "no_scheduled_service", "The GTFS feed has no scheduled Durham service on that date.")
            requested_seconds = int(request.departure_time[:2]) * 3_600 + int(request.departure_time[3:]) * 60
            rows = self._direct_rows(
                connection,
                origin_stops,
                destination_stops,
                active_services,
                requested_seconds,
                min(request.max_results, self.settings.gtfs_max_journeys),
            )
            if not rows:
                raise ApiError(
                    422,
                    "unsupported_journey",
                    "No direct scheduled trip was found. Journeys requiring transfers are not implemented yet.",
                )
            service_midnight = datetime.combine(request.service_date, time.min, tzinfo=timezone_info)
            journeys = [self._journey(row, service_midnight) for row in rows]
            today = self.clock().astimezone(timezone_info).date()
            freshness = "upcoming" if today < valid_from else "expired" if today > valid_until else "current"
            feed = GtfsFeedMetadata(
                source_url=metadata["source_url"],
                imported_at=datetime.fromisoformat(metadata["imported_at"]),
                source_last_modified=metadata["source_last_modified"],
                version=metadata["archive_sha256"][:12],
                valid_from=valid_from,
                valid_until=valid_until,
                freshness=freshness,
            )
            return TransitJourneySearchResponse(
                timezone=metadata["timezone"],
                service_date=request.service_date,
                requested_departure_time=request.departure_time,
                retrieved_at=self.clock(),
                feed=feed,
                journeys=journeys,
            )

    def _resolve_stops(
        self,
        connection: sqlite3.Connection,
        point: JourneyPointInput,
        radius_meters: int,
    ) -> list[_Stop]:
        if point.stop_id:
            row = connection.execute(
                "SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops WHERE stop_id = ?",
                (point.stop_id,),
            ).fetchone()
            return [self._stop(row)] if row else []
        if point.latitude is not None and point.longitude is not None:
            latitude_delta = radius_meters / 111_320
            longitude_delta = radius_meters / max(1, 111_320 * math.cos(math.radians(point.latitude)))
            rows = connection.execute(
                """SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops
                   WHERE stop_lat BETWEEN ? AND ? AND stop_lon BETWEEN ? AND ?""",
                (
                    point.latitude - latitude_delta,
                    point.latitude + latitude_delta,
                    point.longitude - longitude_delta,
                    point.longitude + longitude_delta,
                ),
            ).fetchall()
            ranked = sorted(
                (
                    (_haversine_meters(point.latitude, point.longitude, row["stop_lat"], row["stop_lon"]), self._stop(row))
                    for row in rows
                ),
                key=lambda item: item[0],
            )
            return [stop for distance, stop in ranked if distance <= radius_meters][:12]

        query_tokens = self._name_tokens(point.name or "")
        if not query_tokens:
            return []
        ranked_names = []
        normalized_query = " ".join(sorted(query_tokens))
        for row in connection.execute("SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops"):
            stop_tokens = self._name_tokens(row["stop_name"])
            overlap = len(query_tokens & stop_tokens)
            if not overlap:
                continue
            exact_bonus = 10 if normalized_query == " ".join(sorted(stop_tokens)) else 0
            ranked_names.append((exact_bonus + overlap / len(query_tokens), self._stop(row)))
        ranked_names.sort(key=lambda item: (-item[0], item[1].name.casefold(), item[1].stop_id))
        return [stop for _, stop in ranked_names[:12]]

    @staticmethod
    def _name_tokens(value: str) -> set[str]:
        ignored = {"at", "canada", "on", "ontario", "region", "the"}
        return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 1 and token not in ignored}

    @staticmethod
    def _stop(row: sqlite3.Row) -> _Stop:
        return _Stop(row["stop_id"], row["stop_name"], row["stop_lat"], row["stop_lon"])

    @staticmethod
    def _active_services(connection: sqlite3.Connection, service_date: date) -> set[str]:
        weekday = WEEKDAY_COLUMNS[service_date.weekday()]
        active = {
            row["service_id"]
            for row in connection.execute(
                f"SELECT service_id FROM calendar WHERE start_date <= ? AND end_date >= ? AND {weekday} = 1",
                (service_date.isoformat(), service_date.isoformat()),
            )
        }
        for row in connection.execute(
            "SELECT service_id, exception_type FROM calendar_dates WHERE service_date = ?",
            (service_date.isoformat(),),
        ):
            if row["exception_type"] == 1:
                active.add(row["service_id"])
            else:
                active.discard(row["service_id"])
        return active

    @staticmethod
    def _direct_rows(
        connection: sqlite3.Connection,
        origins: list[_Stop],
        destinations: list[_Stop],
        services: set[str],
        requested_seconds: int,
        limit: int,
    ) -> list[sqlite3.Row]:
        origin_ids = [stop.stop_id for stop in origins]
        destination_ids = [stop.stop_id for stop in destinations]
        service_ids = sorted(services)
        origin_marks = ",".join("?" for _ in origin_ids)
        destination_marks = ",".join("?" for _ in destination_ids)
        service_marks = ",".join("?" for _ in service_ids)
        query = f"""
            SELECT t.trip_id, t.route_id, t.trip_headsign, t.shape_id,
                   r.route_short_name, r.route_long_name,
                   board.stop_id AS board_stop_id, bs.stop_name AS board_name,
                   bs.stop_lat AS board_lat, bs.stop_lon AS board_lon,
                   alight.stop_id AS alight_stop_id, ds.stop_name AS alight_name,
                   ds.stop_lat AS alight_lat, ds.stop_lon AS alight_lon,
                   board.departure_seconds, alight.arrival_seconds
            FROM stop_times AS board
            JOIN stop_times AS alight ON alight.trip_id = board.trip_id
            JOIN trips AS t ON t.trip_id = board.trip_id
            JOIN routes AS r ON r.route_id = t.route_id
            JOIN stops AS bs ON bs.stop_id = board.stop_id
            JOIN stops AS ds ON ds.stop_id = alight.stop_id
            WHERE board.stop_id IN ({origin_marks})
              AND alight.stop_id IN ({destination_marks})
              AND t.service_id IN ({service_marks})
              AND board.stop_sequence < alight.stop_sequence
              AND board.departure_seconds >= ?
              AND alight.arrival_seconds >= board.departure_seconds
              AND board.pickup_type != 1
              AND alight.drop_off_type != 1
            ORDER BY board.departure_seconds, alight.arrival_seconds
            LIMIT ?
        """
        combination_limit = min(1_000, limit * len(origin_ids) * len(destination_ids))
        parameters = (*origin_ids, *destination_ids, *service_ids, requested_seconds, combination_limit)
        rows = connection.execute(query, parameters).fetchall()
        origin_rank = {stop.stop_id: index for index, stop in enumerate(origins)}
        destination_rank = {stop.stop_id: index for index, stop in enumerate(destinations)}
        rows.sort(key=lambda row: (
            row["departure_seconds"],
            origin_rank[row["board_stop_id"]],
            destination_rank[row["alight_stop_id"]],
            row["arrival_seconds"],
        ))
        unique: list[sqlite3.Row] = []
        seen_trips: set[str] = set()
        for row in rows:
            if row["trip_id"] in seen_trips:
                continue
            seen_trips.add(row["trip_id"])
            unique.append(row)
            if len(unique) >= limit:
                break
        return unique

    @staticmethod
    def _journey(row: sqlite3.Row, service_midnight: datetime) -> ScheduledTransitJourney:
        departure = service_midnight + timedelta(seconds=row["departure_seconds"])
        arrival = service_midnight + timedelta(seconds=row["arrival_seconds"])
        route_number = row["route_short_name"] or row["route_long_name"] or row["route_id"]
        return ScheduledTransitJourney(
            trip_id=row["trip_id"],
            route_id=row["route_id"],
            route_number=route_number,
            route_name=row["route_long_name"] or None,
            headsign=row["trip_headsign"],
            boarding_stop=ScheduledStop(
                stop_id=row["board_stop_id"],
                name=row["board_name"],
                latitude=row["board_lat"],
                longitude=row["board_lon"],
            ),
            alighting_stop=ScheduledStop(
                stop_id=row["alight_stop_id"],
                name=row["alight_name"],
                latitude=row["alight_lat"],
                longitude=row["alight_lon"],
            ),
            scheduled_departure=departure,
            scheduled_arrival=arrival,
            scheduled_duration_seconds=row["arrival_seconds"] - row["departure_seconds"],
            shape_id=row["shape_id"],
        )
