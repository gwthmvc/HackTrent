export type DataSource = {
    name: string;
    url?: string;
    retrievedAt?: string;
};

export type Money = {
    amount: number;
    currency: string;
};

export type OutingRecommendation = {
    id: string;
    name: string;
    description: string;
    category?: string;
    locationId?: string;
    startAt?: string;
    endAt?: string;
    price?: Money;
    source: DataSource;
};

export type ItineraryStop = {
    id: string;
    title: string;
    startAt: string;
    endAt?: string;
    description?: string;
    locationId?: string;
    cost?: Money;
};

export type TransitObservation = {
    id: string;
    description: string;
    observedAt: string;
    freshness: string;
    source: DataSource;
};

export type PoliceIncident = {
    id: string;
    type: string;
    occurredAt: string;
    area: string;
    geographicLimitations: string;
    source: DataSource;
};

export type VerifiedLocation = {
    id: string;
    name: string;
    address?: string;
    latitude: number;
    longitude: number;
    source: DataSource;
};

export type RouteCoordinate = {
    latitude: number;
    longitude: number;
};

export type VerifiedRoute = {
    id: string;
    coordinates: RouteCoordinate[];
    source: DataSource;
    mode?: string;
    fromLocationId?: string;
    toLocationId?: string;
};

export type Availability<T> = {
    status: 'available';
    items: T[];
    coverage?: string;
    retrievedAt?: string;
} | {
    status: 'unavailable';
    reason: string;
    coverage?: string;
    retrievedAt?: string;
};

export type OutingPlan = {
    requestId: string;
    generatedAt: string;
    summary: {
        title: string;
        description: string;
    };
    recommendations: OutingRecommendation[];
    itinerary: ItineraryStop[];
    transit: Availability<TransitObservation>;
    policeIncidents: Availability<PoliceIncident>;
    locations: VerifiedLocation[];
    startingLocation?: VerifiedLocation;
    routes?: VerifiedRoute[];
};

export type GenerateOutingRequest = {
    message: string;
    startingLocation: string;
};
