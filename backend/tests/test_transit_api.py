from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import auth
from app.config import Settings
from app.main import create_app
from app.repository import PositionRecord


class FakeTransitRepository:
    def __init__(self, records: list[PositionRecord]) -> None:
        self.records = records
        self.requested_agency: str | None = None

    def latest_positions(self, agency_value: str) -> list[PositionRecord]:
        self.requested_agency = agency_value
        return self.records


class FakeJwksClient:
    def get_signing_key_from_jwt(self, _: str) -> SimpleNamespace:
        return SimpleNamespace(key="test-public-key")


def test_returns_structured_current_positions() -> None:
    observed_at = datetime.now(timezone.utc) - timedelta(seconds=20)
    repository = FakeTransitRepository([
        PositionRecord(
            vehicle_id="vehicle-17",
            agency="kingston",
            route_id="7",
            latitude=44.2312,
            longitude=-76.486,
            observed_at=observed_at,
        ),
    ])
    settings = Settings(
        _env_file=None,
        auth_required=False,
        transit_stale_after_seconds=300,
    )

    with TestClient(create_app(settings, repository)) as client:
        response = client.get("/api/transit/vehicles", params={"agency_id": "kingston"})

    assert response.status_code == 200
    body = response.json()
    assert body["agencyId"] == "kingston"
    assert body["status"] == "current"
    assert body["vehicles"][0]["vehicleId"] == "vehicle-17"
    assert body["vehicles"][0]["routeId"] == "7"
    assert body["vehicles"][0]["freshness"]["status"] == "current"
    assert repository.requested_agency == "kingston"


def test_marks_old_positions_stale() -> None:
    repository = FakeTransitRepository([
        PositionRecord(
            vehicle_id="vehicle-old",
            agency="kingston",
            route_id=None,
            latitude=44.2,
            longitude=-76.5,
            observed_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        ),
    ])
    settings = Settings(_env_file=None, auth_required=False, transit_stale_after_seconds=300)

    with TestClient(create_app(settings, repository)) as client:
        response = client.get("/api/transit/vehicles?agency_id=kingston")

    assert response.status_code == 200
    assert response.json()["status"] == "stale"
    assert response.json()["vehicles"][0]["freshness"]["status"] == "stale"


def test_marks_mixed_freshness_without_presenting_everything_as_current() -> None:
    repository = FakeTransitRepository([
        PositionRecord(
            vehicle_id="vehicle-current",
            agency="durham",
            route_id="901",
            latitude=43.9,
            longitude=-78.9,
            observed_at=datetime.now(timezone.utc) - timedelta(seconds=20),
        ),
        PositionRecord(
            vehicle_id="vehicle-stale",
            agency="durham",
            route_id="902",
            latitude=43.91,
            longitude=-78.91,
            observed_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        ),
    ])
    settings = Settings(_env_file=None, auth_required=False, transit_stale_after_seconds=300)

    with TestClient(create_app(settings, repository)) as client:
        response = client.get("/api/transit/vehicles?agency_id=durham")

    assert response.status_code == 200
    assert response.json()["status"] == "mixed"
    assert [vehicle["freshness"]["status"] for vehicle in response.json()["vehicles"]] == [
        "current",
        "stale",
    ]


def test_context_prefers_supported_destination_over_starting_area() -> None:
    observed_at = datetime.now(timezone.utc) - timedelta(seconds=20)
    repository = FakeTransitRepository([
        PositionRecord(
            vehicle_id="kingston-17",
            agency="kingston",
            route_id="7",
            latitude=44.2312,
            longitude=-76.486,
            observed_at=observed_at,
        ),
    ])
    settings = Settings(_env_file=None, auth_required=False)

    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/transit/context",
            json={
                "startingLocation": "Durham College, Oshawa, Ontario",
                "outingRequest": "I want a day out in Kingston using transit.",
            },
        )

    assert response.status_code == 200
    assert response.json()["agencyId"] == "kingston"
    assert repository.requested_agency == "kingston"


def test_context_uses_supported_start_when_request_has_no_supported_area() -> None:
    repository = FakeTransitRepository([
        PositionRecord(
            vehicle_id="durham-1",
            agency="durham",
            route_id=None,
            latitude=43.94,
            longitude=-78.89,
            observed_at=datetime.now(timezone.utc) - timedelta(seconds=20),
        ),
    ])
    settings = Settings(_env_file=None, auth_required=False)

    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/transit/context",
            json={
                "startingLocation": "Durham College, Oshawa, Ontario",
                "outingRequest": "A quiet museum afternoon.",
            },
        )

    assert response.status_code == 200
    assert response.json()["agencyId"] == "durham"
    assert repository.requested_agency == "durham"


def test_context_rejects_unsupported_area_without_database_read() -> None:
    repository = FakeTransitRepository([])
    settings = Settings(_env_file=None, auth_required=False)

    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/transit/context",
            json={
                "startingLocation": "Ottawa, Ontario",
                "outingRequest": "Museums near Parliament Hill.",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_area"
    assert repository.requested_agency is None


def test_rejects_unsupported_agency() -> None:
    settings = Settings(_env_file=None, auth_required=False)
    with TestClient(create_app(settings, FakeTransitRepository([]))) as client:
        response = client.get("/api/transit/vehicles?agency_id=ottawa")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_agency"


def test_rejects_malformed_agency_id() -> None:
    settings = Settings(_env_file=None, auth_required=False)
    with TestClient(create_app(settings, FakeTransitRepository([]))) as client:
        response = client.get("/api/transit/vehicles?agency_id=not%20an%20agency")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_returns_not_found_for_missing_records() -> None:
    settings = Settings(_env_file=None, auth_required=False)
    with TestClient(create_app(settings, FakeTransitRepository([]))) as client:
        response = client.get("/api/transit/vehicles?agency_id=durham")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_transit_records"


def test_requires_bearer_token_by_default() -> None:
    settings = Settings(_env_file=None)
    with TestClient(create_app(settings, FakeTransitRepository([]))) as client:
        response = client.get("/api/transit/vehicles?agency_id=kingston")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_access_token"


def test_cors_preflight_does_not_require_bearer_token() -> None:
    repository = FakeTransitRepository([])
    settings = Settings(_env_file=None)

    with TestClient(create_app(settings, repository)) as client:
        response = client.options(
            "/api/transit/context",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Authorization" in response.headers["access-control-allow-headers"]
    assert repository.requested_agency is None


def test_cors_headers_are_kept_on_protected_post_response() -> None:
    repository = FakeTransitRepository([])
    settings = Settings(_env_file=None)

    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/transit/context",
            headers={"Origin": "http://localhost:5173"},
            json={
                "startingLocation": "Durham College, Oshawa, Ontario",
                "outingRequest": "A local outing",
            },
        )

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.json()["error"]["code"] == "missing_access_token"
    assert repository.requested_agency is None


def test_reports_unconfigured_auth0_before_token_validation() -> None:
    settings = Settings(_env_file=None)
    with TestClient(create_app(settings, FakeTransitRepository([]))) as client:
        response = client.get(
            "/api/transit/vehicles?agency_id=kingston",
            headers={"Authorization": "Bearer not-a-real-token"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "authentication_not_configured"


def test_valid_authentication_without_required_permission_returns_403(monkeypatch) -> None:
    repository = FakeTransitRepository([])
    settings = Settings(
        _env_file=None,
        auth0_domain="tenant.example.auth0.com",
        auth0_audience="https://api.smartmove.test",
    )
    monkeypatch.setattr(auth, "get_jwks_client", lambda _: FakeJwksClient())
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_, **__: {"sub": "auth0|test-user", "scope": "openid profile"},
    )

    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/transit/context",
            headers={"Authorization": "Bearer safe-test-token"},
            json={
                "startingLocation": "Durham College, Oshawa, Ontario",
                "outingRequest": "A local outing",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_scope"
    assert repository.requested_agency is None


def test_authenticated_post_with_required_permission_reaches_service(monkeypatch) -> None:
    repository = FakeTransitRepository([
        PositionRecord(
            vehicle_id="durham-test",
            agency="durham",
            route_id="901",
            latitude=43.94,
            longitude=-78.89,
            observed_at=datetime.now(timezone.utc) - timedelta(seconds=20),
        ),
    ])
    settings = Settings(
        _env_file=None,
        auth0_domain="tenant.example.auth0.com",
        auth0_audience="https://api.smartmove.test",
    )
    monkeypatch.setattr(auth, "get_jwks_client", lambda _: FakeJwksClient())
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_, **__: {
            "sub": "auth0|test-user",
            "scope": "openid profile read:transit",
        },
    )

    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/transit/context",
            headers={"Authorization": "Bearer safe-test-token"},
            json={
                "startingLocation": "Durham College, Oshawa, Ontario",
                "outingRequest": "A local outing",
            },
        )

    assert response.status_code == 200
    assert response.json()["agencyId"] == "durham"
    assert repository.requested_agency == "durham"


def test_rbac_permissions_claim_authorizes_without_scope_claim(monkeypatch) -> None:
    repository = FakeTransitRepository([
        PositionRecord(
            vehicle_id="durham-rbac-test",
            agency="durham",
            route_id="901",
            latitude=43.94,
            longitude=-78.89,
            observed_at=datetime.now(timezone.utc) - timedelta(seconds=20),
        ),
    ])
    settings = Settings(
        _env_file=None,
        auth0_domain="tenant.example.auth0.com",
        auth0_audience="https://api.smartmove.test",
    )
    monkeypatch.setattr(auth, "get_jwks_client", lambda _: FakeJwksClient())
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_, **__: {
            "sub": "auth0|test-user",
            "scope": "openid profile",
            "permissions": ["read:transit"],
        },
    )

    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/transit/context",
            headers={"Authorization": "Bearer safe-test-token"},
            json={
                "startingLocation": "Durham College, Oshawa, Ontario",
                "outingRequest": "A local outing",
            },
        )

    assert response.status_code == 200
    assert response.json()["agencyId"] == "durham"
    assert repository.requested_agency == "durham"


def test_non_list_permissions_claim_does_not_bypass_authorization(monkeypatch) -> None:
    repository = FakeTransitRepository([])
    settings = Settings(
        _env_file=None,
        auth0_domain="tenant.example.auth0.com",
        auth0_audience="https://api.smartmove.test",
    )
    monkeypatch.setattr(auth, "get_jwks_client", lambda _: FakeJwksClient())
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_, **__: {
            "sub": "auth0|test-user",
            "scope": "openid profile",
            "permissions": "read:transit",
        },
    )

    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/transit/context",
            headers={"Authorization": "Bearer safe-test-token"},
            json={
                "startingLocation": "Durham College, Oshawa, Ontario",
                "outingRequest": "A local outing",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_scope"
    assert repository.requested_agency is None


def test_reports_unconfigured_database_without_exposing_details() -> None:
    settings = Settings(_env_file=None, auth_required=False)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/transit/vehicles?agency_id=kingston")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_not_configured",
            "message": "TigerData connection settings are not configured on the server.",
        },
    }


def test_health_reports_missing_secure_configuration() -> None:
    settings = Settings(_env_file=None)
    with TestClient(create_app(settings, FakeTransitRepository([]))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "databaseConfigured": False,
        "authenticationRequired": True,
        "authenticationConfigured": False,
        "eventsConfigured": False,
        "placesConfigured": True,
    }
