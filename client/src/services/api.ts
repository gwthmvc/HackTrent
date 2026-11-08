import type {
    Availability,
    DataSource,
    GenerateOutingRequest,
    ItineraryStop,
    OutingPlan,
    OutingRecommendation,
    PoliceIncident,
    TransitObservation,
    VerifiedLocation,
    VerifiedRoute,
} from '../types/outing';

const GENERATE_OUTING_URL = import.meta.env.VITE_SMARTMOVE_GENERATE_URL?.trim();
const API_TIMEOUT_MS = 30_000;

type ApiErrorResponse = {
    message?: string;
    error?: string;
    detail?: string;
};

export const isOutingPlannerConfigured = Boolean(GENERATE_OUTING_URL);

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function isString(value: unknown): value is string {
    return typeof value === 'string' && value.trim().length > 0;
}

function isOptionalString(value: unknown): value is string | undefined {
    return value === undefined || typeof value === 'string';
}

function isSource(value: unknown): value is DataSource {
    return isObject(value)
        && isString(value.name)
        && isOptionalString(value.url)
        && isOptionalString(value.retrievedAt);
}

function isMoney(value: unknown): boolean {
    return isObject(value)
        && typeof value.amount === 'number'
        && Number.isFinite(value.amount)
        && isString(value.currency);
}

function isRecommendation(value: unknown): value is OutingRecommendation {
    return isObject(value)
        && isString(value.id)
        && isString(value.name)
        && isString(value.description)
        && isOptionalString(value.category)
        && isOptionalString(value.locationId)
        && isOptionalString(value.startAt)
        && isOptionalString(value.endAt)
        && (value.price === undefined || isMoney(value.price))
        && isSource(value.source);
}

function isItineraryStop(value: unknown): value is ItineraryStop {
    return isObject(value)
        && isString(value.id)
        && isString(value.title)
        && isString(value.startAt)
        && isOptionalString(value.endAt)
        && isOptionalString(value.description)
        && isOptionalString(value.locationId)
        && (value.cost === undefined || isMoney(value.cost));
}

function isTransitObservation(value: unknown): value is TransitObservation {
    return isObject(value)
        && isString(value.id)
        && isString(value.description)
        && isString(value.observedAt)
        && isString(value.freshness)
        && isSource(value.source);
}

function isPoliceIncident(value: unknown): value is PoliceIncident {
    return isObject(value)
        && isString(value.id)
        && isString(value.type)
        && isString(value.occurredAt)
        && isString(value.area)
        && isString(value.geographicLimitations)
        && isSource(value.source);
}

function isLocation(value: unknown): value is VerifiedLocation {
    return isObject(value)
        && isString(value.id)
        && isString(value.name)
        && isOptionalString(value.address)
        && typeof value.latitude === 'number'
        && value.latitude >= -90
        && value.latitude <= 90
        && typeof value.longitude === 'number'
        && value.longitude >= -180
        && value.longitude <= 180
        && isSource(value.source);
}

function isRoute(value: unknown): value is VerifiedRoute {
    return isObject(value)
        && isString(value.id)
        && Array.isArray(value.coordinates)
        && value.coordinates.length >= 2
        && value.coordinates.every((coordinate) => (
            isObject(coordinate)
            && typeof coordinate.latitude === 'number'
            && coordinate.latitude >= -90
            && coordinate.latitude <= 90
            && typeof coordinate.longitude === 'number'
            && coordinate.longitude >= -180
            && coordinate.longitude <= 180
        ))
        && isSource(value.source)
        && isOptionalString(value.mode)
        && isOptionalString(value.fromLocationId)
        && isOptionalString(value.toLocationId);
}

function isAvailability<T>(
    value: unknown,
    itemGuard: (item: unknown) => item is T,
): value is Availability<T> {
    if (!isObject(value) || !isOptionalString(value.coverage) || !isOptionalString(value.retrievedAt)) {
        return false;
    }

    if (value.status === 'unavailable') {
        return isString(value.reason);
    }

    return value.status === 'available'
        && Array.isArray(value.items)
        && value.items.every(itemGuard);
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
        && isAvailability(value.transit, isTransitObservation)
        && isAvailability(value.policeIncidents, isPoliceIncident)
        && Array.isArray(value.locations)
        && value.locations.every(isLocation)
        && (value.startingLocation === undefined || isLocation(value.startingLocation))
        && (value.routes === undefined
            || (Array.isArray(value.routes) && value.routes.every(isRoute)));
}

export async function generateOuting(
    request: GenerateOutingRequest,
): Promise<OutingPlan> {
    if (!GENERATE_OUTING_URL) {
        throw new Error(
            'Trip planning is unavailable because the backend generation endpoint is not configured.',
        );
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    let response: Response;
    try {
        response = await fetch(GENERATE_OUTING_URL, {
            method: 'POST',
            headers: {
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
        const message = apiError?.message ?? apiError?.error ?? apiError?.detail
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
