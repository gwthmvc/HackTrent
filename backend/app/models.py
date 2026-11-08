import datetime as dt
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Freshness(ApiModel):
    status: Literal["current", "stale"]
    age_seconds: int
    stale_after_seconds: int


class VehiclePosition(ApiModel):
    vehicle_id: str
    agency_id: str
    route_id: str | None
    latitude: float
    longitude: float
    observed_at: datetime
    freshness: Freshness


class TransitContextRequest(ApiModel):
    starting_location: str = Field(min_length=2, max_length=240)
    outing_request: str = Field(min_length=2, max_length=2_000)


class TransitVehiclesResponse(ApiModel):
    agency_id: str
    status: Literal["current", "mixed", "stale"]
    retrieved_at: datetime
    latest_observation_at: datetime
    stale_after_seconds: int
    vehicles: list[VehiclePosition]


class JourneyPointInput(ApiModel):
    stop_id: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=2, max_length=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_selector(self) -> "JourneyPointInput":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.stop_id is None and self.name is None and self.latitude is None:
            raise ValueError("provide a stop ID, name, or coordinates")
        return self


class TransitJourneySearchRequest(ApiModel):
    agency_id: str = Field(default="durham", min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    origin: JourneyPointInput
    destination: JourneyPointInput
    service_date: dt.date
    departure_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    max_walking_distance_meters: int = Field(default=800, ge=100, le=3_000)
    max_results: int = Field(default=5, ge=1, le=10)


class ScheduledStop(ApiModel):
    stop_id: str
    name: str
    latitude: float
    longitude: float


class ScheduledTransitJourney(ApiModel):
    trip_id: str
    route_id: str
    route_number: str
    route_name: str | None
    headsign: str | None
    boarding_stop: ScheduledStop
    alighting_stop: ScheduledStop
    scheduled_departure: datetime
    scheduled_arrival: datetime
    scheduled_duration_seconds: int
    shape_id: str | None


class GtfsFeedMetadata(ApiModel):
    source_url: str
    imported_at: datetime
    source_last_modified: str | None
    version: str
    valid_from: dt.date
    valid_until: dt.date
    freshness: Literal["current", "upcoming", "expired"]


class TransitJourneySearchResponse(ApiModel):
    agency_id: Literal["durham"] = "durham"
    timezone: str
    service_date: dt.date
    requested_departure_time: str
    retrieved_at: datetime
    journey_type: Literal["direct"] = "direct"
    feed: GtfsFeedMetadata
    journeys: list[ScheduledTransitJourney]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Direct scheduled trips only; transfers and real-time arrival predictions are not implemented.",
        ],
    )


class HealthResponse(ApiModel):
    status: Literal["ok"] = "ok"
    database_configured: bool
    authentication_required: bool
    authentication_configured: bool
    events_configured: bool
    places_configured: bool


class EventSearchRequest(ApiModel):
    starting_location: str = Field(min_length=2, max_length=240)
    outing_request: str = Field(min_length=2, max_length=2_000)
    date: dt.date | None = None
    time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    interests: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(
        default_factory=list, max_length=5,
    )


class EventPriceRange(ApiModel):
    min: float | None
    max: float | None
    currency: str


class EventVenue(ApiModel):
    name: str
    address: str | None
    city: str | None
    province: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    coordinate_status: Literal["verified", "missing", "outside_search_area"]


class TicketmasterEvent(ApiModel):
    id: str
    name: str
    url: str | None
    start_local_date: str
    start_local_time: str | None
    start_date_time: datetime | None
    status: str | None
    price_range: EventPriceRange | None
    venue: EventVenue
    image_url: str | None
    classification: str | None


class EventSearchWindow(ApiModel):
    start: datetime
    end: datetime
    description: str
    time_from: str | None
    time_to: str | None


class EventSource(ApiModel):
    name: str = "Ticketmaster Discovery API"
    url: str = "https://developer.ticketmaster.com/"


class EventSearchResponse(ApiModel):
    area_id: str
    area_name: str
    transit_coverage: bool
    retrieved_at: datetime
    cached: bool
    window: EventSearchWindow
    classifications: list[str]
    total_available: int
    events: list[TicketmasterEvent]
    source: EventSource = Field(default_factory=EventSource)


PlaceCategory = Literal["food", "parks_outdoors", "culture", "entertainment_family"]


class PlaceSearchRequest(ApiModel):
    starting_location: str = Field(min_length=2, max_length=240)
    outing_request: str = Field(min_length=2, max_length=2_000)
    destination_name: str | None = Field(default=None, max_length=240)
    destination_latitude: float | None = Field(default=None, ge=-90, le=90)
    destination_longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_destination_coordinates(self) -> "PlaceSearchRequest":
        if (self.destination_latitude is None) != (self.destination_longitude is None):
            raise ValueError("destination latitude and longitude must be provided together")
        return self


class PlaceSearchAnchor(ApiModel):
    name: str
    latitude: float
    longitude: float
    kind: Literal["verified_destination", "area_center"]


class DiscoveredPlace(ApiModel):
    id: str
    name: str
    category: PlaceCategory
    subtype: str
    address: str | None
    latitude: float
    longitude: float
    distance_meters: int
    source_url: str


class PlacesSource(ApiModel):
    name: str = "OpenStreetMap contributors"
    url: str = "https://www.openstreetmap.org/copyright"
    service: str = "Overpass API"


class PlaceSearchResponse(ApiModel):
    area_id: str
    area_name: str
    anchor: PlaceSearchAnchor
    radius_meters: int
    retrieved_at: datetime
    data_timestamp: datetime | None
    cached: bool
    total_available: int
    places: list[DiscoveredPlace]
    source: PlacesSource = Field(default_factory=PlacesSource)


class ErrorBody(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorBody


class OutingPlanRequest(ApiModel):
    outing_request: str = Field(min_length=2, max_length=2_000)
    starting_location: str = Field(min_length=2, max_length=240)
    date: dt.date | None = None
    time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    interests: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(
        default_factory=list, max_length=5,
    )


class OutingDataSource(ApiModel):
    name: str
    url: str | None = None
    retrieved_at: datetime | None = None


class OutingRecommendation(ApiModel):
    id: str
    name: str
    description: str | None
    category: str | None
    location_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    price_range: EventPriceRange | None = Field(
        default=None, exclude_if=lambda value: value is None,
    )
    source: OutingDataSource


class OutingItineraryItem(ApiModel):
    id: str
    title: str
    start_at: datetime
    end_at: datetime | None = None
    description: str | None
    location_id: str | None = None
    price_range: EventPriceRange | None = Field(
        default=None, exclude_if=lambda value: value is None,
    )


class TransitObservation(ApiModel):
    id: str
    description: str
    observed_at: datetime
    freshness: str
    source: OutingDataSource


class OutingTransit(ApiModel):
    status: Literal["available", "unavailable"]
    items: list[TransitObservation] | None = None
    reason: str | None = None


class OutingScheduledJourney(ScheduledTransitJourney):
    feed: OutingDataSource


class OutingJourneys(ApiModel):
    status: Literal["available", "unavailable"]
    code: str | None = None
    reason: str | None = None
    timezone: str | None = None
    items: list[OutingScheduledJourney] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class OutingPoliceIncidents(ApiModel):
    status: Literal["unavailable"] = "unavailable"
    reason: str


class OutingLocation(ApiModel):
    id: str
    name: str
    address: str | None = None
    latitude: float
    longitude: float
    source: OutingDataSource


class OutingSourceStatus(ApiModel):
    status: Literal["available", "unavailable"]
    code: str | None = None
    reason: str | None = None


class OutingSourceStatuses(ApiModel):
    events: OutingSourceStatus
    places: OutingSourceStatus
    transit: OutingSourceStatus
    journeys: OutingSourceStatus


class OutingSummary(ApiModel):
    title: str
    description: str


class OutingPlanResponse(ApiModel):
    request_id: str
    generated_at: datetime
    summary: OutingSummary
    recommendations: list[OutingRecommendation]
    itinerary: list[OutingItineraryItem]
    transit: OutingTransit
    journeys: OutingJourneys
    police_incidents: OutingPoliceIncidents
    locations: list[OutingLocation]
    source_status: OutingSourceStatuses
