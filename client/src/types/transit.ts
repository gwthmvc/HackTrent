export type TransitFreshness = {
    status: 'current' | 'stale';
    ageSeconds: number;
    staleAfterSeconds: number;
};
export type TransitVehicleObservation = {
    vehicleId: string;
    agencyId: 'durham' | 'kingston';
    routeId: string | null;
    latitude: number;
    longitude: number;
    observedAt: string;
    freshness: TransitFreshness;
};
export type TransitContextResponse = {
    agencyId: 'durham' | 'kingston';
    status: 'current' | 'mixed' | 'stale';
    retrievedAt: string;
    latestObservationAt: string;
    staleAfterSeconds: number;
    vehicles: TransitVehicleObservation[];
};

export type TransitContextRequest = {
    startingLocation: string;
    outingRequest: string;
};

