import type {
    Availability,
    DataSource,
    GenerateOutingRequest,
    ItineraryStop,
    OutingPlan,
    OutingPlaces,
    OutingRecommendation,
    PriceRange,
    ScheduledJourney,
    ScheduledStop,
    TransitObservation,
    VerifiedLocation,
} from '../types/outing';

const API_BASE_URL = import.meta.env.VITE_SMARTMOVE_API_URL?.trim().replace(/\/$/, '');
const API_TIMEOUT_MS = 30_000;

type ApiErrorResponse = {
    error?: {
        code?: string;
        message?: string;
    };
};

export const isOutingPlannerConfigured = Boolean(API_BASE_URL);

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function isString(value: unknown): value is string {
    return typeof value === 'string' && value.trim().length > 0;
}

function isNullableString(value: unknown): value is string | null | undefined {
    return value === undefined || value === null || typeof value === 'string';
}

function isSource(value: unknown): value is DataSource {
    return isObject(value)
        && isString(value.name)
        && isNullableString(value.url)
        && isNullableString(value.retrievedAt);
}

function isPriceRange(value: unknown): value is PriceRange {
    return isObject(value)
        && typeof value.min === 'number'
        && Number.isFinite(value.min)
        && typeof value.max === 'number'
        && Number.isFinite(value.max)
        && isString(value.currency);
}

function isRecommendation(value: unknown): value is OutingRecommendation {
    return isObject(value)
        && isString(value.id)
        && isString(value.name)
        && isNullableString(value.description)
        && isNullableString(value.category)
        && isNullableString(value.locationId)
        && isNullableString(value.startAt)
        && isNullableString(value.endAt)
        && (value.priceRange === undefined || isPriceRange(value.priceRange))
        && isSource(value.source);
}

function isItineraryStop(value: unknown): value is ItineraryStop {
    return isObject(value)
        && isString(value.id)
        && isString(value.title)
        && isString(value.startAt)
        && isNullableString(value.endAt)
        && isNullableString(value.description)
        && isNullableString(value.locationId)
        && (value.priceRange === undefined || isPriceRange(value.priceRange));
}

function isTransitObservation(value: unknown): value is TransitObservation {
    return isObject(value)
        && isString(value.id)
        && isString(value.description)
        && isString(value.observedAt)
        && isString(value.freshness)
        && isSource(value.source);
}

function isScheduledStop(value: unknown): value is ScheduledStop {
    return isObject(value)
        && isString(value.stopId)
        && isString(value.name)
        && typeof value.latitude === 'number'
        && value.latitude >= -90
        && value.latitude <= 90
        && typeof value.longitude === 'number'
        && value.longitude >= -180
        && value.longitude <= 180;
}

function isScheduledJourney(value: unknown): value is ScheduledJourney {
    return isObject(value)
        && isString(value.tripId)
        && isString(value.routeId)
        && isString(value.routeNumber)
        && isNullableString(value.routeName)
        && isNullableString(value.headsign)
        && isScheduledStop(value.boardingStop)
        && isScheduledStop(value.alightingStop)
        && isString(value.scheduledDeparture)
        && isString(value.scheduledArrival)
        && typeof value.scheduledDurationSeconds === 'number'
        && Number.isInteger(value.scheduledDurationSeconds)
        && value.scheduledDurationSeconds >= 0
        && isNullableString(value.shapeId)
        && isSource(value.feed);
}

function isJourneys(value: unknown): boolean {
    return isObject(value)
        && (value.status === 'available' || value.status === 'unavailable')
        && isNullableString(value.code)
        && isNullableString(value.reason)
        && isNullableString(value.timezone)
        && Array.isArray(value.items)
        && value.items.every(isScheduledJourney)
        && Array.isArray(value.limitations)
        && value.limitations.every(isString);
}

function isLocation(value: unknown): value is VerifiedLocation {
    return isObject(value)
        && isString(value.id)
        && isString(value.name)
        && isNullableString(value.address)
        && typeof value.latitude === 'number'
        && value.latitude >= -90
        && value.latitude <= 90
        && typeof value.longitude === 'number'
        && value.longitude >= -180
        && value.longitude <= 180
        && isSource(value.source);
}

function isSourceStatus(value: unknown): boolean {
    return isObject(value)
        && (value.status === 'available' || value.status === 'unavailable')
        && isNullableString(value.code)
        && isNullableString(value.reason);
}

function isCoordinate(value: unknown, min: number, max: number): value is number {
    return typeof value === 'number'
        && Number.isFinite(value)
        && value >= min
        && value <= max;
}

function isPlace(value: unknown): boolean {
    return isObject(value)
        && isString(value.id)
        && isString(value.name)
        && (value.category === 'food'
            || value.category === 'parks_outdoors'
            || value.category === 'culture'
            || value.category === 'entertainment_family')
        && isString(value.subtype)
        && (value.address === null || isString(value.address))
        && isCoordinate(value.latitude, -90, 90)
        && isCoordinate(value.longitude, -180, 180)
        && typeof value.distanceMeters === 'number'
        && Number.isInteger(value.distanceMeters)
        && value.distanceMeters >= 0
        && isString(value.sourceUrl);
}

function isOutingPlaces(value: unknown): value is OutingPlaces {
    return isObject(value)
        && isString(value.areaId)
        && isString(value.areaName)
        && isObject(value.anchor)
        && isString(value.anchor.name)
        && isCoordinate(value.anchor.latitude, -90, 90)
        && isCoordinate(value.anchor.longitude, -180, 180)
        && (value.anchor.kind === 'verified_destination' || value.anchor.kind === 'area_center')
        && typeof value.radiusMeters === 'number'
        && Number.isInteger(value.radiusMeters)
        && value.radiusMeters >= 0
        && isString(value.retrievedAt)
        && (value.dataTimestamp === null || isString(value.dataTimestamp))
        && typeof value.cached === 'boolean'
        && typeof value.totalAvailable === 'number'
        && Number.isInteger(value.totalAvailable)
        && value.totalAvailable >= 0
        && Array.isArray(value.places)
        && value.places.every(isPlace)
        && isObject(value.source)
        && isString(value.source.name)
        && isString(value.source.url)
        && isString(value.source.service);
}

function isTransit(value: unknown): value is Availability<TransitObservation> {
    if (!isObject(value)) return false;
    if (value.status === 'unavailable') return isString(value.reason);
    return value.status === 'available'
        && Array.isArray(value.items)
        && value.items.every(isTransitObservation);
}

function isOutingPlan(value: unknown): value is OutingPlan {
    return isObject(value)
        && isString(value.requestId)
        && isString(value.generatedAt)
        && isObject(value.summary)
        && isString(value.summary.title)
        && isString(value.summary.description)
        && Array.isArray(value.recommendations)
        && value.recommendations.every(isRecommendation)
        && Array.isArray(value.itinerary)
        && value.itinerary.every(isItineraryStop)
        && isTransit(value.transit)
        && isJourneys(value.journeys)
        && isObject(value.policeIncidents)
        && value.policeIncidents.status === 'unavailable'
        && isString(value.policeIncidents.reason)
        && Array.isArray(value.locations)
        && value.locations.every(isLocation)
        && isObject(value.sourceStatus)
        && isSourceStatus(value.sourceStatus.events)
        && isSourceStatus(value.sourceStatus.places)
        && isSourceStatus(value.sourceStatus.transit)
        && isSourceStatus(value.sourceStatus.journeys)
        && (value.places === null || isOutingPlaces(value.places));
}

export async function generateOuting(
    request: GenerateOutingRequest,
    accessToken: string,
): Promise<OutingPlan> {
    if (!API_BASE_URL) {
        throw new Error(
            'Trip planning is unavailable because the backend generation endpoint is not configured.',
        );
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    let response: Response;
    try {
        response = await fetch(`${API_BASE_URL}/api/outings/generate`, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
            signal: controller.signal,
        });
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('The server took too long to respond. Please try again.', {
                cause: error,
            });
        }
        throw new Error('Unable to connect to the server. Please try again.', {
            cause: error,
        });
    } finally {
        window.clearTimeout(timeoutId);
    }

    const contentType = response.headers.get('content-type');
    const responseBody: unknown = contentType?.includes('application/json')
        ? await response.json()
        : await response.text();

    if (!response.ok) {
        const apiError = typeof responseBody === 'object' && responseBody !== null
            ? responseBody as ApiErrorResponse
            : undefined;
        const message = apiError?.error?.message
            ?? (typeof responseBody === 'string' ? responseBody : undefined)
            ?? `Request failed with status ${response.status}`;

        throw new Error(message);
    }

    if (!isOutingPlan(responseBody)) {
        throw new Error(
            'The server returned an unsupported trip-plan response. No itinerary was displayed.',
        );
    }

    return responseBody;
}
