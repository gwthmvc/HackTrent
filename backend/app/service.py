from __future__ import annotations

from datetime import datetime, timezone

from .config import Settings
from .errors import ApiError, DatabaseNotConfiguredError, DatabaseUnavailableError, SchemaVerificationError
from .models import Freshness, TransitVehiclesResponse, VehiclePosition
from .repository import TransitPositionReader


AGENCY_AREA_TERMS = {
    "durham": (
        "durham",
        "oshawa",
        "whitby",
        "ajax",
        "pickering",
        "clarington",
        "bowmanville",
        "uxbridge",
        "scugog",
        "port perry",
    ),
    "kingston": ("kingston",),
}


class TransitService:
    def __init__(self, repository: TransitPositionReader, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def get_latest_vehicles(self, requested_agency: str) -> TransitVehiclesResponse:
        agency_id = requested_agency.strip().lower()
        agency_value = self._settings.agency_values.get(agency_id)
        if agency_value is None:
            supported = ", ".join(sorted(self._settings.agency_values))
            raise ApiError(
                status_code=422,
                code="unsupported_agency",
                message=f"Unsupported agency_id. Supported values: {supported}.",
            )

        try:
            records = self._repository.latest_positions(agency_value)
        except DatabaseNotConfiguredError as error:
            raise ApiError(
                status_code=503,
                code="database_not_configured",
                message="TigerData connection settings are not configured on the server.",
            ) from error
        except SchemaVerificationError as error:
            raise ApiError(
                status_code=503,
                code="schema_not_verified",
                message=f"The bus_positions schema could not be verified: {error}",
            ) from error
        except DatabaseUnavailableError as error:
            raise ApiError(
                status_code=503,
                code="database_unavailable",
                message="TigerData is currently unavailable.",
            ) from error

        if not records:
            raise ApiError(
                status_code=404,
                code="no_transit_records",
                message=f"No verified vehicle observations were found for {agency_id}.",
            )

        now = datetime.now(timezone.utc)
        vehicles: list[VehiclePosition] = []
        for record in records:
            if not record.vehicle_id.strip():
                raise ApiError(
                    status_code=503,
                    code="invalid_transit_record",
                    message="TigerData returned a vehicle observation without a vehicle ID.",
                )
            if not (-90 <= record.latitude <= 90 and -180 <= record.longitude <= 180):
                raise ApiError(
                    status_code=503,
                    code="invalid_transit_record",
                    message="TigerData returned a vehicle observation with invalid coordinates.",
                )
            if record.observed_at.tzinfo is None:
                raise ApiError(
                    status_code=503,
                    code="schema_not_verified",
                    message="Observation timestamps do not include timezone information.",
                )

            age_seconds = max(0, int((now - record.observed_at).total_seconds()))
            freshness_status = (
                "stale"
                if age_seconds > self._settings.transit_stale_after_seconds
                else "current"
            )
            vehicles.append(
                VehiclePosition(
                    vehicle_id=record.vehicle_id,
                    agency_id=agency_id,
                    route_id=record.route_id,
                    latitude=record.latitude,
                    longitude=record.longitude,
                    observed_at=record.observed_at,
                    freshness=Freshness(
                        status=freshness_status,
                        age_seconds=age_seconds,
                        stale_after_seconds=self._settings.transit_stale_after_seconds,
                    ),
                )
            )

        latest_observation = max(vehicle.observed_at for vehicle in vehicles)
        freshness_values = {vehicle.freshness.status for vehicle in vehicles}
        response_status = (
            "mixed"
            if len(freshness_values) > 1
            else next(iter(freshness_values))
        )

        return TransitVehiclesResponse(
            agency_id=agency_id,
            status=response_status,
            retrieved_at=now,
            latest_observation_at=latest_observation,
            stale_after_seconds=self._settings.transit_stale_after_seconds,
            vehicles=vehicles,
        )

    def get_relevant_vehicles(
        self,
        starting_location: str,
        outing_request: str,
    ) -> TransitVehiclesResponse:
        starting_matches = self._matching_agencies(starting_location)
        request_matches = self._matching_agencies(outing_request)

        destination_matches = request_matches - starting_matches
        if destination_matches:
            agency_id = self._first_mentioned_agency(outing_request, destination_matches)
        elif request_matches:
            agency_id = self._first_mentioned_agency(outing_request, request_matches)
        elif starting_matches:
            agency_id = self._first_mentioned_agency(starting_location, starting_matches)
        else:
            supported = ", ".join(sorted(AGENCY_AREA_TERMS))
            raise ApiError(
                status_code=422,
                code="unsupported_area",
                message=(
                    "No supported transit area was found in the starting location or outing "
                    f"request. Initial coverage: {supported}."
                ),
            )

        return self.get_latest_vehicles(agency_id)

    @staticmethod
    def _matching_agencies(value: str) -> set[str]:
        normalized = value.casefold()
        return {
            agency_id
            for agency_id, terms in AGENCY_AREA_TERMS.items()
            if any(term in normalized for term in terms)
        }

    @staticmethod
    def _first_mentioned_agency(value: str, agencies: set[str]) -> str:
        normalized = value.casefold()
        return min(
            agencies,
            key=lambda agency_id: min(
                normalized.find(term)
                for term in AGENCY_AREA_TERMS[agency_id]
                if term in normalized
            ),
        )
