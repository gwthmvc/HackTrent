"""GTFS schedule ingestion and direct-journey tests; all downloads are mocked."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.gtfs import GtfsImporter, GtfsJourneyService, GtfsValidationError
from app.main import create_app
from app.models import JourneyPointInput, TransitJourneySearchRequest

from test_transit_api import FakeTransitRepository


def gtfs_archive(*, missing_shape: bool = False) -> bytes:
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
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "SVC,1,1,1,1,1,1,1,20261101,20261130\n"
        ),
        "calendar_dates.txt": (
            "service_id,date,exception_type\n"
            "SVC,20261110,2\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id,trip_headsign,direction_id,shape_id\n"
            "R1,SVC,T1,Arena,0,SH1\n"
            "R1,SVC,T2,Arena Night,0,SH1\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type,shape_dist_traveled\n"
            "T1,08:00:00,08:00:00,A,1,0,0,0\n"
            "T1,08:20:00,08:20:00,B,2,0,0,7000\n"
            "T1,08:25:00,08:25:00,C,3,0,0,7500\n"
            "T2,25:00:00,25:00:00,A,1,0,0,0\n"
            "T2,25:25:00,25:25:00,C,2,0,0,7500\n"
        ),
        "shapes.txt": (
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\n"
            + ("OTHER,43.9,-78.9,1,0\n" if missing_shape else "SH1,43.945,-78.896,1,0\nSH1,43.897,-78.860,2,7500\n")
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def settings(tmp_path, **overrides) -> Settings:
    return Settings(
        _env_file=None,
        auth_required=False,
        gtfs_cache_dir=tmp_path,
        **overrides,
    )


def imported_service(tmp_path) -> GtfsJourneyService:
    app_settings = settings(tmp_path)
    GtfsImporter(app_settings).import_archive(
        gtfs_archive(),
        {"etag": '"fixture-v1"', "last_modified": "Sat, 07 Nov 2026 12:00:00 GMT"},
    )
    return GtfsJourneyService(
        app_settings,
        clock=lambda: datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc),
    )


def request(**overrides) -> TransitJourneySearchRequest:
    values = {
        "origin": JourneyPointInput(name="Durham College, Oshawa, Ontario"),
        "destination": JourneyPointInput(latitude=43.8970, longitude=-78.8600),
        "service_date": "2026-11-09",
        "departure_time": "07:30",
    }
    values.update(overrides)
    return TransitJourneySearchRequest(**values)


def test_import_validates_and_deduplicates_archive(tmp_path) -> None:
    importer = GtfsImporter(settings(tmp_path))
    archive = gtfs_archive()

    first = importer.import_archive(archive, {"etag": '"fixture-v1"'})
    second = importer.import_archive(archive, {"etag": '"fixture-v1"'})

    assert first.status == "updated"
    assert second.status == "unchanged"
    assert first.valid_from.isoformat() == "2026-11-01"
    assert first.valid_until.isoformat() == "2026-11-30"
    assert first.counts == {
        "calendar": 1,
        "calendar_dates": 1,
        "routes": 1,
        "shapes": 2,
        "stop_times": 5,
        "stops": 3,
        "trips": 2,
    }


def test_conditional_sync_uses_etag_and_skips_duplicate_download(tmp_path) -> None:
    archive = gtfs_archive()
    requests: list[httpx.Request] = []

    def handler(incoming: httpx.Request) -> httpx.Response:
        requests.append(incoming)
        if len(requests) == 1:
            return httpx.Response(
                200,
                content=archive,
                headers={"ETag": '"fixture-v1"', "Last-Modified": "Sat, 07 Nov 2026 12:00:00 GMT"},
            )
        return httpx.Response(304)

    importer = GtfsImporter(settings(tmp_path), transport=httpx.MockTransport(handler))
    assert importer.sync().status == "updated"
    assert importer.sync().status == "unchanged"
    assert len(requests) == 2
    assert requests[1].headers["if-none-match"] == '"fixture-v1"'
    assert "if-modified-since" in requests[1].headers


def test_direct_journey_returns_schedule_contract(tmp_path) -> None:
    result = imported_service(tmp_path).search(request())

    assert result.agency_id == "durham"
    assert result.journey_type == "direct"
    assert result.timezone == "America/Toronto"
    assert result.feed.freshness == "current"
    assert result.feed.source_last_modified == "Sat, 07 Nov 2026 12:00:00 GMT"
    assert len(result.journeys) == 2
    journey = result.journeys[0]
    assert journey.route_number == "901"
    assert journey.boarding_stop.stop_id == "A"
    assert journey.alighting_stop.stop_id == "C"
    assert journey.scheduled_departure.isoformat() == "2026-11-09T08:00:00-05:00"
    assert journey.scheduled_arrival.isoformat() == "2026-11-09T08:25:00-05:00"
    assert journey.scheduled_duration_seconds == 1_500
    assert journey.shape_id == "SH1"


def test_after_midnight_gtfs_time_rolls_into_next_day(tmp_path) -> None:
    result = imported_service(tmp_path).search(request(departure_time="23:30"))
    journey = result.journeys[0]
    assert journey.trip_id == "T2"
    assert journey.scheduled_departure.isoformat() == "2026-11-10T01:00:00-05:00"
    assert journey.scheduled_arrival.isoformat() == "2026-11-10T01:25:00-05:00"


def test_calendar_removal_and_transfer_limit_are_truthful(tmp_path) -> None:
    service = imported_service(tmp_path)
    with pytest.raises(Exception) as removed:
        service.search(request(service_date="2026-11-10"))
    assert getattr(removed.value, "code", None) == "no_scheduled_service"

    with pytest.raises(Exception) as unsupported:
        service.search(request(
            origin=JourneyPointInput(stop_id="C"),
            destination=JourneyPointInput(stop_id="A"),
        ))
    assert getattr(unsupported.value, "code", None) == "unsupported_journey"


def test_api_is_protected_contract_and_missing_cache(tmp_path) -> None:
    app_settings = settings(tmp_path)
    service = imported_service(tmp_path)
    app = create_app(
        app_settings,
        FakeTransitRepository([]),
        journey_service=service,
    )
    body = {
        "agencyId": "durham",
        "origin": {"stopId": "A"},
        "destination": {"stopId": "C"},
        "serviceDate": "2026-11-09",
        "departureTime": "07:30",
    }
    with TestClient(app) as client:
        response = client.post("/api/transit/journeys/search", json=body)

    assert response.status_code == 200
    payload = response.json()
    assert payload["journeyType"] == "direct"
    assert payload["journeys"][0]["scheduledDurationSeconds"] == 1_500
    assert "real-time arrival predictions" in payload["limitations"][0]

    empty_settings = settings(tmp_path / "empty")
    with TestClient(create_app(empty_settings, FakeTransitRepository([]))) as client:
        unavailable = client.post("/api/transit/journeys/search", json=body)
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "gtfs_schedule_unavailable"

    with TestClient(app) as client:
        unsupported = client.post(
            "/api/transit/journeys/search",
            json={**body, "agencyId": "kingston"},
        )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "unsupported_schedule_agency"


def test_rejects_missing_referenced_shape(tmp_path) -> None:
    with pytest.raises(GtfsValidationError, match="missing shape records"):
        GtfsImporter(settings(tmp_path)).import_archive(gtfs_archive(missing_shape=True))
