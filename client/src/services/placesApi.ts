import type {
    DiscoveredPlace,
    PlaceSearchRequest,
    PlaceSearchResponse,
} from '../types/places';

const API_BASE_URL = import.meta.env.VITE_SMARTMOVE_API_URL?.trim().replace(/\/$/, '');
const API_TIMEOUT_MS = 24_000;
const CATEGORIES = new Set(['food', 'parks_outdoors', 'culture', 'entertainment_family']);

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}
function isNullableString(value: unknown): value is string | null {
    return value === null || typeof value === 'string';
}
function isCoordinate(value: unknown, min: number, max: number): value is number {
    return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}

function isPlace(value: unknown): value is DiscoveredPlace {
    return isObject(value)
        && typeof value.id === 'string'
        && typeof value.name === 'string'
        && typeof value.category === 'string'
        && CATEGORIES.has(value.category)
        && typeof value.subtype === 'string'
        && isNullableString(value.address)
        && isCoordinate(value.latitude, -90, 90)
        && isCoordinate(value.longitude, -180, 180)
        && typeof value.distanceMeters === 'number'
        && value.distanceMeters >= 0
        && typeof value.sourceUrl === 'string';
}

function isPlaceSearchResponse(value: unknown): value is PlaceSearchResponse {
    return isObject(value)
        && typeof value.areaId === 'string'
        && typeof value.areaName === 'string'
        && isObject(value.anchor)
        && typeof value.anchor.name === 'string'
        && isCoordinate(value.anchor.latitude, -90, 90)
        && isCoordinate(value.anchor.longitude, -180, 180)
        && (value.anchor.kind === 'verified_destination' || value.anchor.kind === 'area_center')
        && typeof value.radiusMeters === 'number'
        && typeof value.retrievedAt === 'string'
        && isNullableString(value.dataTimestamp)
        && typeof value.cached === 'boolean'
        && typeof value.totalAvailable === 'number'
        && Array.isArray(value.places)
        && value.places.every(isPlace)
        && isObject(value.source)
        && typeof value.source.name === 'string'
        && typeof value.source.url === 'string'
        && typeof value.source.service === 'string';
}

function apiErrorMessage(value: unknown, fallback: string): string {
    if (isObject(value) && isObject(value.error) && typeof value.error.message === 'string') {
        return value.error.message;
    }
    return fallback;
}

export async function searchPlaces(
    request: PlaceSearchRequest,
    accessToken: string,
): Promise<PlaceSearchResponse> {
    if (!API_BASE_URL) {
        throw new Error('The SmartMove API URL is not configured in the frontend.');
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    try {
        const response = await fetch(`${API_BASE_URL}/api/places/search`, {
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
            throw new Error(apiErrorMessage(body, `Place search failed with status ${response.status}.`));
        }
        if (!isPlaceSearchResponse(body)) {
            throw new Error('The place service returned an unsupported response. No places were shown.');
        }
        return body;
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('OpenStreetMap place search took too long to respond.', { cause: error });
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

