from __future__ import annotations

from contextlib import closing
from datetime import datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from .errors import ApiError
from .models import (
    EventSearchRequest,
    OutingDataSource,
    OutingItineraryItem,
    OutingJourneys,
    OutingLocation,
    OutingPlaces,
    OutingPlanRequest,
    OutingPlanResponse,
    OutingPoliceIncidents,
    OutingRecommendation,
    OutingScheduledJourney,
    OutingSourceStatus,
    OutingSourceStatuses,
    OutingSummary,
    OutingTransit,
    JourneyPointInput,
    PlaceSearchRequest,
    TransitJourneySearchRequest,
    TransitObservation,
)

LOCAL_TZ = ZoneInfo("America/Toronto")
POLICE_UNAVAILABLE = "No public-safety data source is implemented."


class OutingOrchestrator:
    def __init__(self, event_service, place_service, transit_service, journey_service=None) -> None:
        self._event_service = event_service
        self._place_service = place_service
        self._transit_service = transit_service
        self._journey_service = journey_service

    def plan(self, request: OutingPlanRequest, subject: str) -> OutingPlanResponse:
        event_status = OutingSourceStatus(status="available")
        place_status = OutingSourceStatus(status="available")
        transit_status = OutingSourceStatus(status="available")
        journey_status = OutingSourceStatus(status="available")

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

        journeys_response = None
        journeys_no_direct_trip = False
        if self._journey_service is None:
            journey_status = OutingSourceStatus(
                status="unavailable",
                code="journeys_not_configured",
                reason="Scheduled transit journeys are not configured.",
            )
        elif "durham college" not in request.starting_location.casefold():
            journey_status = OutingSourceStatus(
                status="unavailable",
                code="origin_not_supported",
                reason="Scheduled journeys are only available from Durham College.",
            )
        elif anchor is None:
            journey_status = OutingSourceStatus(
                status="unavailable",
                code="no_verified_destination",
                reason="No verified event destination is available for scheduled journeys.",
            )
        elif request.date is None or request.time is None:
            journey_status = OutingSourceStatus(
                status="unavailable",
                code="departure_time_required",
                reason="A departure date and time are required for scheduled journeys.",
            )
        else:
            try:
                origin_stop = self._find_durham_college_stop()
                if origin_stop is None:
                    if callable(getattr(self._journey_service, "_connect", None)):
                        journey_status = OutingSourceStatus(
                            status="unavailable",
                            code="origin_not_supported",
                            reason="No Durham College stop was found in the imported GTFS stops.",
                        )
                    else:
                        journey_request = TransitJourneySearchRequest(
                            agency_id="durham",
                            origin=JourneyPointInput(name="Durham College"),
                            destination=JourneyPointInput(
                                latitude=anchor.venue.latitude,
                                longitude=anchor.venue.longitude,
                            ),
                            service_date=request.date,
                            departure_time=request.time,
                        )
                        journeys_response = self._journey_service.search(journey_request)
                        if journeys_response.journeys:
                            journeys_response = self._journey_service.search(
                                journey_request.model_copy(
                                    update={
                                        "origin": JourneyPointInput(
                                            stop_id=journeys_response.journeys[0].boarding_stop.stop_id,
                                        ),
                                    },
                                ),
                            )
                else:
                    journeys_response = self._journey_service.search(
                        TransitJourneySearchRequest(
                            agency_id="durham",
                            origin=JourneyPointInput(stop_id=origin_stop),
                            destination=JourneyPointInput(
                                latitude=anchor.venue.latitude,
                                longitude=anchor.venue.longitude,
                            ),
                            service_date=request.date,
                            departure_time=request.time,
                        ),
                    )
            except ApiError as error:
                if error.code == "unsupported_journey":
                    journeys_no_direct_trip = True
                else:
                    journey_status = OutingSourceStatus(
                        status="unavailable", code=error.code, reason=error.message,
                    )

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
        journeys = (
            OutingJourneys(
                status="available",
                timezone=journeys_response.timezone,
                items=[
                    OutingScheduledJourney(
                        **journey.model_dump(),
                        feed=OutingDataSource(
                            name="Durham GTFS schedule",
                            url=journeys_response.feed.source_url,
                            retrieved_at=journeys_response.feed.imported_at,
                        ),
                    )
                    for journey in journeys_response.journeys
                ],
                limitations=(
                    journeys_response.limitations
                    if journeys_response.journeys
                    else [*journeys_response.limitations, "No direct scheduled trip found."]
                ),
            )
            if journeys_response
            else OutingJourneys(
                status="available",
                limitations=[
                    "Direct scheduled trips only; transfers and real-time arrival predictions are not implemented.",
                    "No direct scheduled trip found.",
                ],
            )
            if journeys_no_direct_trip
            else OutingJourneys(
                status="unavailable",
                code=journey_status.code,
                reason=journey_status.reason or "Scheduled transit journeys are unavailable.",
            )
        )
        summary_parts = []
        if event_status.status == "available":
            if (
                events_response
                and events_response.window.time_from is not None
                and len(events) < events_response.total_available
            ):
                event_date = events_response.window.start.astimezone(LOCAL_TZ).date().isoformat()
                summary_parts.append(
                    f"{events_response.total_available} events found on {event_date}; "
                    f"{len(events)} start within the requested time window. "
                    "Clear the time to see all events.",
                )
            else:
                summary_parts.append(f"{len(events)} events found.")
        else:
            summary_parts.append(
                f"Events could not be searched ({event_status.code}).",
            )
        if place_status.status == "available":
            summary_parts.append(
                f"{len(places_response.places) if places_response else 0} places found.",
            )
        else:
            summary_parts.append(
                f"Places could not be searched ({place_status.code}).",
            )
        return OutingPlanResponse(
            request_id=str(uuid4()),
            generated_at=datetime.now(timezone.utc),
            summary=OutingSummary(
                title="Outing plan",
                description=" ".join(summary_parts),
            ),
            recommendations=recommendations,
            itinerary=itinerary,
            transit=transit,
            journeys=journeys,
            police_incidents=OutingPoliceIncidents(reason=POLICE_UNAVAILABLE),
            locations=locations,
            source_status=OutingSourceStatuses(
                events=event_status, places=place_status, transit=transit_status,
                journeys=journey_status,
            ),
            places=(
                OutingPlaces(
                    area_id=places_response.area_id,
                    area_name=places_response.area_name,
                    anchor=places_response.anchor,
                    radius_meters=places_response.radius_meters,
                    retrieved_at=places_response.retrieved_at,
                    data_timestamp=places_response.data_timestamp,
                    cached=places_response.cached,
                    total_available=places_response.total_available,
                    places=places_response.places,
                    source=places_response.source,
                )
                if places_response else None
            ),
        )

    def _find_durham_college_stop(self) -> str | None:
        connect = getattr(self._journey_service, "_connect", None)
        resolve_stops = getattr(self._journey_service, "_resolve_stops", None)
        if not callable(connect) or not callable(resolve_stops):
            return None
        with closing(connect()) as connection:
            stops = resolve_stops(
                connection,
                JourneyPointInput(name="Durham College"),
                800,
            )
        matching = [stop for stop in stops if "durham college" in stop.name.casefold()]
        return matching[0].stop_id if matching else None

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
