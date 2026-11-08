from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import AuthContext, require_auth
from .config import Settings, get_settings
from .database import Database
from .errors import ApiError
from .events import TicketmasterEventService
from .places import OverpassPlaceService
from .gtfs import GtfsJourneyService
from .models import (
    ErrorBody,
    ErrorResponse,
    EventSearchRequest,
    EventSearchResponse,
    HealthResponse,
    PlaceSearchRequest,
    PlaceSearchResponse,
    TransitContextRequest,
    TransitJourneySearchRequest,
    TransitJourneySearchResponse,
    TransitVehiclesResponse,
)
from .repository import TigerDataTransitRepository, TransitPositionReader
from .service import TransitService


def create_app(
    settings: Settings | None = None,
    repository: TransitPositionReader | None = None,
    event_service: TicketmasterEventService | None = None,
    place_service: OverpassPlaceService | None = None,
    journey_service: GtfsJourneyService | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    database = Database(app_settings)
    transit_repository = repository or TigerDataTransitRepository(database, app_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database.close()

    app = FastAPI(
        title="SmartMove Ontario API",
        version="0.1.0",
        description="Read-only TigerData observations and validated GTFS static schedules.",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.transit_service = TransitService(transit_repository, app_settings)
    app.state.event_service = event_service or TicketmasterEventService(app_settings)
    app.state.place_service = place_service or OverpassPlaceService(app_settings)
    app.state.journey_service = journey_service or GtfsJourneyService(app_settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, error: ApiError) -> JSONResponse:
        body = ErrorResponse(error=ErrorBody(code=error.code, message=error.message))
        headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
        return JSONResponse(
            status_code=error.status_code,
            content=body.model_dump(by_alias=True),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        first_error = error.errors()[0] if error.errors() else None
        message = str(first_error.get("msg")) if first_error else "Invalid request."
        body = ErrorResponse(error=ErrorBody(code="invalid_request", message=message))
        return JSONResponse(status_code=422, content=body.model_dump(by_alias=True))

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            database_configured=database.configured,
            authentication_required=app_settings.auth_required,
            authentication_configured=app_settings.auth_configured,
            events_configured=app.state.event_service.configured,
            places_configured=app.state.place_service.configured,
        )

    @app.get(
        "/api/transit/vehicles",
        response_model=TransitVehiclesResponse,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["transit"],
    )
    def get_transit_vehicles(
        agency_id: str = Query(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$"),
        _: AuthContext = Depends(require_auth),
    ) -> TransitVehiclesResponse:
        service: TransitService = app.state.transit_service
        return service.get_latest_vehicles(agency_id)

    @app.post(
        "/api/transit/context",
        response_model=TransitVehiclesResponse,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["transit"],
    )
    def get_transit_context(
        request_body: TransitContextRequest,
        _: AuthContext = Depends(require_auth),
    ) -> TransitVehiclesResponse:
        service: TransitService = app.state.transit_service
        return service.get_relevant_vehicles(
            request_body.starting_location,
            request_body.outing_request,
        )

    @app.post(
        "/api/transit/journeys/search",
        response_model=TransitJourneySearchResponse,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["transit"],
    )
    def search_scheduled_journeys(
        request_body: TransitJourneySearchRequest,
        _: AuthContext = Depends(require_auth),
    ) -> TransitJourneySearchResponse:
        service: GtfsJourneyService = app.state.journey_service
        return service.search(request_body)

    @app.post(
        "/api/events/search",
        response_model=EventSearchResponse,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
        tags=["events"],
    )
    def search_events(
        request_body: EventSearchRequest,
        auth_context: AuthContext = Depends(require_auth),
    ) -> EventSearchResponse:
        service: TicketmasterEventService = app.state.event_service
        return service.search(request_body, auth_context.subject)

    @app.post(
        "/api/places/search",
        response_model=PlaceSearchResponse,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
        tags=["places"],
    )
    def search_places(
        request_body: PlaceSearchRequest,
        auth_context: AuthContext = Depends(require_auth),
    ) -> PlaceSearchResponse:
        service: OverpassPlaceService = app.state.place_service
        return service.search(request_body, auth_context.subject)

    return app


app = create_app()
