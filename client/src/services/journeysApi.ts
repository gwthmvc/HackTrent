import type {
    ScheduledTransitJourney,
    TransitJourneySearchRequest,
    TransitJourneySearchResponse,
} from '../types/journeys';

const API_BASE_URL = import.meta.env.VITE_SMARTMOVE_API_URL?.trim().replace(/\/$/, '');
const API_TIMEOUT_MS = 12_000;

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function isStop(value: unknown): boolean {
    return isObject(value)
        && typeof value.stopId === 'string'
        && typeof value.name === 'string'
        && typeof value.latitude === 'number'
        && typeof value.longitude === 'number';
}

function isJourney(value: unknown): value is ScheduledTransitJourney {
    return isObject(value)
        && typeof value.tripId === 'string'
        && typeof value.routeId === 'string'
        && typeof value.routeNumber === 'string'
        && (value.routeName === null || typeof value.routeName === 'string')
        && (value.headsign === null || typeof value.headsign === 'string')
        && isStop(value.boardingStop)
        && isStop(value.alightingStop)
        && typeof value.scheduledDeparture === 'string'
        && typeof value.scheduledArrival === 'string'
        && typeof value.scheduledDurationSeconds === 'number'
        && (value.shapeId === null || typeof value.shapeId === 'string');
}

function isResponse(value: unknown): value is TransitJourneySearchResponse {
    return isObject(value)
        && value.agencyId === 'durham'
        && value.journeyType === 'direct'
        && typeof value.timezone === 'string'
        && typeof value.serviceDate === 'string'
        && typeof value.requestedDepartureTime === 'string'
        && typeof value.retrievedAt === 'string'
        && isObject(value.feed)
        && typeof value.feed.sourceUrl === 'string'
        && typeof value.feed.importedAt === 'string'
        && (value.feed.sourceLastModified === null || typeof value.feed.sourceLastModified === 'string')
        && typeof value.feed.version === 'string'
        && typeof value.feed.validFrom === 'string'
        && typeof value.feed.validUntil === 'string'
        && ['current', 'upcoming', 'expired'].includes(String(value.feed.freshness))
        && Array.isArray(value.journeys)
        && value.journeys.every(isJourney)
        && Array.isArray(value.limitations)
        && value.limitations.every((item) => typeof item === 'string');
}

function errorMessage(value: unknown, fallback: string): string {
    if (isObject(value) && isObject(value.error) && typeof value.error.message === 'string') {
        return value.error.message;
    }
    return fallback;
}

export async function searchScheduledJourneys(
    request: TransitJourneySearchRequest,
    accessToken: string,
): Promise<TransitJourneySearchResponse> {
    if (!API_BASE_URL) {
        throw new Error('The SmartMove API URL is not configured in the frontend.');
    }
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    try {
        const response = await fetch(`${API_BASE_URL}/api/transit/journeys/search`, {
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
            throw new Error(errorMessage(body, `Scheduled journey search failed with status ${response.status}.`));
        }
        if (!isResponse(body)) {
            throw new Error('The schedule API returned an unsupported response. No journey was shown.');
        }
        return body;
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('The scheduled journey search took too long to respond.', { cause: error });
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}
