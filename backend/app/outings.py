from __future__ import annotations

from datetime import datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from .errors import ApiError
from .models import (
    EventSearchRequest,
    OutingDataSource,
    OutingItineraryItem,
    OutingLocation,
    OutingPlanRequest,
    OutingPlanResponse,
    OutingPoliceIncidents,
    OutingRecommendation,
    OutingSourceStatus,
    OutingSourceStatuses,
    OutingSummary,
    OutingTransit,
    PlaceSearchRequest,
    TransitObservation,
)

LOCAL_TZ = ZoneInfo("America/Toronto")
POLICE_UNAVAILABLE = "No public-safety data source is implemented."


class OutingOrchestrator:
    def __init__(self, event_service, place_service, transit_service) -> None:
        self._event_service = event_service
        self._place_service = place_service
        self._transit_service = transit_service

    def plan(self, request: OutingPlanRequest, subject: str) -> OutingPlanResponse:
        event_status = OutingSourceStatus(status="available")
        place_status = OutingSourceStatus(status="available")
        transit_status = OutingSourceStatus(status="available")

        event_request = EventSearchRequest(
            starting_location=request.starting_location,
            outing_request=request.outing_request,
            date=request.date,
            time=request.time,
            interests=request.interests,
        )
        try:
            events_response = self._event_service.search(event_request, subject)
        except ApiError as error:
            if error.status_code == 422:
                raise
            event_status = OutingSourceStatus(
                status="unavailable", code=error.code, reason=error.message,
            )
            events_response = None

        events = events_response.events if events_response else []
        anchor = next(
            (
                event for event in events
                if event.venue.coordinate_status == "verified"
                and event.venue.latitude is not None
                and event.venue.longitude is not None
            ),
            None,
        )
        place_request = PlaceSearchRequest(
            starting_location=request.starting_location,
            outing_request=request.outing_request,
            destination_name=anchor.venue.name if anchor else None,
            destination_latitude=anchor.venue.latitude if anchor else None,
            destination_longitude=anchor.venue.longitude if anchor else None,
        )
        try:
            places_response = self._place_service.search(place_request, subject)
        except ApiError as error:
            if error.code == "invalid_place_destination":
                retry_request = PlaceSearchRequest(
                    starting_location=request.starting_location,
                    outing_request=request.outing_request,
                )
                try:
                    places_response = self._place_service.search(retry_request, subject)
                except ApiError as retry_error:
                    if retry_error.code == "unsupported_event_area":
                        raise
                    place_status = OutingSourceStatus(
                        status="unavailable",
                        code=retry_error.code,
                        reason=retry_error.message,
                    )
                    places_response = None
            elif error.code == "unsupported_event_area":
                raise
            else:
                place_status = OutingSourceStatus(
                    status="unavailable", code=error.code, reason=error.message,
                )
                places_response = None

        try:
            transit_response = self._transit_service.get_relevant_vehicles(
                request.starting_location, request.outing_request,
            )
        except ApiError as error:
            transit_status = OutingSourceStatus(
                status="unavailable", code=error.code, reason=error.message,
            )
            transit_response = None

        recommendations: list[OutingRecommendation] = []
        itinerary: list[OutingItineraryItem] = []
        locations: list[OutingLocation] = []
        if events_response:
            for event in events_response.events:
                location_id = f"{event.id}-venue"
                start_at = event.start_date_time or self._local_start(event.start_local_date, event.start_local_time)
                recommendations.append(
                    OutingRecommendation(
                        id=event.id,
                        name=event.name,
                        description=event.classification,
                        category=event.classification,
                        location_id=location_id,
                        start_at=start_at,
                        price_range=event.price_range,
                        source=OutingDataSource(
                            name=events_response.source.name,
                            url=event.url,
                            retrieved_at=events_response.retrieved_at,
                        ),
                    ),
                )
                if event.start_local_time and start_at:
                    itinerary.append(
                        OutingItineraryItem(
                            id=event.id,
                            title=event.name,
                            start_at=start_at,
                            description=event.classification,
                            location_id=location_id,
                            price_range=event.price_range,
                        ),
                    )
                if event.venue.coordinate_status == "verified" and event.venue.latitude is not None and event.venue.longitude is not None:
                    locations.append(
                        OutingLocation(
                            id=location_id,
                            name=event.venue.name,
                            address=event.venue.address,
                            latitude=event.venue.latitude,
                            longitude=event.venue.longitude,
                            source=OutingDataSource(
                                name=events_response.source.name,
                                url=event.url,
                                retrieved_at=events_response.retrieved_at,
                            ),
                        ),
                    )

        if places_response:
            for place in places_response.places:
                recommendations.append(
                    OutingRecommendation(
                        id=place.id,
                        name=place.name,
                        description=place.subtype,
                        category=place.category,
                        source=OutingDataSource(
                            name=places_response.source.name,
                            url=place.source_url,
                            retrieved_at=places_response.retrieved_at,
                        ),
                    ),
                )

        transit = (
            OutingTransit(
                status="available",
                items=[
                    TransitObservation(
                        id=vehicle.vehicle_id,
                        description=(
                            f"Route {vehicle.route_id}, vehicle {vehicle.vehicle_id}"
                            if vehicle.route_id
                            else f"Vehicle {vehicle.vehicle_id}"
                        ),
                        observed_at=vehicle.observed_at,
                        freshness=vehicle.freshness.status,
                        source=OutingDataSource(name="TigerData transit observations"),
                    )
                    for vehicle in transit_response.vehicles
                ],
            )
            if transit_response
            else OutingTransit(
                status="unavailable",
                reason=transit_status.reason or "Transit data is unavailable.",
            )
        )
        event_count = len(events)
        place_count = len(places_response.places) if places_response else 0
        return OutingPlanResponse(
            request_id=str(uuid4()),
            generated_at=datetime.now(timezone.utc),
            summary=OutingSummary(
                title="Outing plan",
                description=f"{event_count} events and {place_count} places found.",
            ),
            recommendations=recommendations,
            itinerary=itinerary,
            transit=transit,
            police_incidents=OutingPoliceIncidents(reason=POLICE_UNAVAILABLE),
            locations=locations,
            source_status=OutingSourceStatuses(
                events=event_status, places=place_status, transit=transit_status,
            ),
        )

    @staticmethod
    def _local_start(local_date: str, local_time: str | None) -> datetime | None:
        if not local_time:
            return None
        try:
            return datetime.combine(
                datetime.strptime(local_date, "%Y-%m-%d").date(),
                time.fromisoformat(local_time),
                LOCAL_TZ,
            )
        except ValueError:
            return None
