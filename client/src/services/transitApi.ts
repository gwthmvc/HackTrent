import type {
    TransitContextRequest,
    TransitContextResponse,
    TransitVehicleObservation,
} from '../types/transit';

const API_BASE_URL = import.meta.env.VITE_SMARTMOVE_API_URL?.trim().replace(/\/$/, '');
const API_TIMEOUT_MS = 12_000;

export const isTransitApiConfigured = Boolean(API_BASE_URL);

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}
function isDateString(value: unknown): value is string {
    return typeof value === 'string' && !Number.isNaN(Date.parse(value));
}
function isFiniteCoordinate(value: unknown, min: number, max: number): value is number {
    return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}

function isVehicle(value: unknown): value is TransitVehicleObservation {
    return isObject(value)
        && typeof value.vehicleId === 'string'
        && (value.agencyId === 'durham' || value.agencyId === 'kingston')
        && (value.routeId === null || typeof value.routeId === 'string')
        && isFiniteCoordinate(value.latitude, -90, 90)
        && isFiniteCoordinate(value.longitude, -180, 180)
        && isDateString(value.observedAt)
        && isObject(value.freshness)
        && (value.freshness.status === 'current' || value.freshness.status === 'stale')
        && typeof value.freshness.ageSeconds === 'number'
        && typeof value.freshness.staleAfterSeconds === 'number';
}

function isTransitContextResponse(value: unknown): value is TransitContextResponse {
    return isObject(value)
        && (value.agencyId === 'durham' || value.agencyId === 'kingston')
        && (value.status === 'current' || value.status === 'mixed' || value.status === 'stale')
        && isDateString(value.retrievedAt)
        && isDateString(value.latestObservationAt)
        && typeof value.staleAfterSeconds === 'number'
        && Array.isArray(value.vehicles)
        && value.vehicles.every(isVehicle);
}

function apiErrorMessage(value: unknown, fallback: string): string {
    if (!isObject(value)) return fallback;
    if (isObject(value.error) && typeof value.error.message === 'string') {
        return value.error.message;
    }
    return typeof value.detail === 'string' ? value.detail : fallback;
}

export async function fetchTransitContext(
    request: TransitContextRequest,
    accessToken: string,
): Promise<TransitContextResponse> {
    if (!API_BASE_URL) {
        throw new Error('The transit API URL is not configured in the frontend.');
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    try {
        const response = await fetch(`${API_BASE_URL}/api/transit/context`, {
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
            throw new Error(apiErrorMessage(body, `Transit request failed with status ${response.status}.`));
        }
        if (!isTransitContextResponse(body)) {
            throw new Error('The transit API returned an unsupported response. No vehicle markers were shown.');
        }

        return body;
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
            throw new Error('The transit service took too long to respond.', { cause: error });
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

