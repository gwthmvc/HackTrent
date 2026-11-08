import type {
    EventSearchRequest,
    EventSearchResponse,
    TicketmasterEvent,
} from '../types/events';

const API_BASE_URL = import.meta.env.VITE_SMARTMOVE_API_URL?.trim().replace(/\/$/, '');
const API_TIMEOUT_MS = 12_000;
const COORDINATE_STATUSES = new Set(['verified', 'missing', 'outside_search_area']);

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function isNullableString(value: unknown): value is string | null {
    return value === null || typeof value === 'string';
}

function isNullableNumber(value: unknown): value is number | null {
    return value === null || (typeof value === 'number' && Number.isFinite(value));
}

function isEvent(value: unknown): value is TicketmasterEvent {
    if (!isObject(value) || !isObject(value.venue)) return false;
    const venue = value.venue;
    const hasValidCoordinates = venue.coordinateStatus === 'verified'
        ? typeof venue.latitude === 'number' && typeof venue.longitude === 'number'
            && Math.abs(venue.latitude) <= 90 && Math.abs(venue.longitude) <= 180
        : venue.latitude === null && venue.longitude === null;
    const price = value.priceRange;
    return typeof value.id === 'string'
        && typeof value.name === 'string'
        && isNullableString(value.url)
        && typeof value.startLocalDate === 'string'
        && isNullableString(value.startLocalTime)
        && isNullableString(value.startDateTime)
        && isNullableString(value.status)
        && (price === null || (isObject(price)
            && isNullableNumber(price.min) && isNullableNumber(price.max)
            && typeof price.currency === 'string'))
        && typeof venue.name === 'string'
        && isNullableString(venue.address)
        && isNullableString(venue.city)
        && typeof venue.coordinateStatus === 'string'
        && COORDINATE_STATUSES.has(venue.coordinateStatus)
        && hasValidCoordinates
        && isNullableString(value.imageUrl)
        && isNullableString(value.classification);
}

function isEventSearchResponse(value: unknown): value is EventSearchResponse {
    return isObject(value)
        && typeof value.areaId === 'string'
        && typeof value.areaName === 'string'
        && typeof value.retrievedAt === 'string'
        && isObject(value.window)
        && typeof value.window.description === 'string'
        && typeof value.totalAvailable === 'number'
        && Array.isArray(value.events)
        && value.events.every(isEvent)
        && isObject(value.source)
        && typeof value.source.name === 'string';
}

function apiErrorMessage(value: unknown, fallback: string): string {
    if (isObject(value) && isObject(value.error) && typeof value.error.message === 'string') {
        return value.error.message;
    }
    return fallback;
}

export async function searchEvents(
    request: EventSearchRequest,
    accessToken: string,
): Promise<EventSearchResponse> {
    if (!API_BASE_URL) {
        throw new Error('The SmartMove API URL is not configured in the frontend.');
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    try {
        const response = await fetch(`${API_BASE_URL}/api/events/search`, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
            signal: controller.signal,
        });
        const body: unknown = await response.json().catch(() => undefined);

        if (!response.ok) {
            throw new Error(apiErrorMessage(body, `Event search failed with status ${response.status}.`));
        }
        if (!isEventSearchResponse(body)) {
            throw new Error('The event service returned an unsupported response. No events were shown.');
        }
        return body;
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('The event service took too long to respond.', { cause: error });
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}
