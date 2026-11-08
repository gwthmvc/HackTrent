import type { VerifiedLocation } from '../types/outing';

export const DEFAULT_STARTING_LOCATION = 'Durham College, Oshawa, Ontario';

export const STARTING_LOCATION_SUGGESTIONS = [
    DEFAULT_STARTING_LOCATION,
    'Kingston, Ontario',
];

const DURHAM_COLLEGE_STARTING_POINT: VerifiedLocation = {
    id: 'starting-point-durham-college-oshawa',
    name: 'Durham College — Oshawa campus',
    address: '2000 Simcoe Street North, Oshawa, Ontario L1G 0C5',
    latitude: 43.94304,
    longitude: -78.89515,
    source: {
        name: 'OpenStreetMap',
        url: 'https://www.openstreetmap.org/way/775640674',
    },
};

const DURHAM_COLLEGE_ALIASES = new Set([
    DEFAULT_STARTING_LOCATION,
    'Durham College, Oshawa',
    'Durham College Oshawa campus',
    '2000 Simcoe Street North, Oshawa, Ontario L1G 0C5',
].map(normalizeLocation));

function normalizeLocation(value: string): string {
    return value
        .trim()
        .toLocaleLowerCase('en-CA')
        .replace(/[^a-z0-9]+/g, ' ')
        .trim();
}
export function getKnownStartingPoint(value: string): VerifiedLocation | undefined {
    return DURHAM_COLLEGE_ALIASES.has(normalizeLocation(value))
        ? DURHAM_COLLEGE_STARTING_POINT
        : undefined;
}
