export type PlaceCategory = 'food' | 'parks_outdoors' | 'culture' | 'entertainment_family';

export type DiscoveredPlace = {
    id: string;
    name: string;
    category: PlaceCategory;
    subtype: string;
    address: string | null;
    latitude: number;
    longitude: number;
    distanceMeters: number;
    sourceUrl: string;
};
export type PlaceSearchAnchor = {
    name: string;
    latitude: number;
    longitude: number;
    kind: 'verified_destination' | 'area_center';
};
export type PlacesSource = {
    name: string;
    url: string;
    service: string;
};
export type PlaceSearchResponse = {
    areaId: string;
    areaName: string;
    anchor: PlaceSearchAnchor;
    radiusMeters: number;
    retrievedAt: string;
    dataTimestamp: string | null;
    cached: boolean;
    totalAvailable: number;
    places: DiscoveredPlace[];
    source: PlacesSource;
};
export type PlaceSearchRequest = {
    startingLocation: string;
    outingRequest: string;
    destinationName?: string;
    destinationLatitude?: number;
    destinationLongitude?: number;
};
