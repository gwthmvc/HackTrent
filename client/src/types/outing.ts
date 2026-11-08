export type DataSource = {
    name: string;
    url?: string | null;
    retrievedAt?: string | null;
};

export type PriceRange = {
    min: number;
    max: number;
    currency: string;
};

export type OutingRecommendation = {
    id: string;
    name: string;
    description: string | null;
    category?: string | null;
    locationId?: string | null;
    startAt?: string | null;
    endAt?: string | null;
    priceRange?: PriceRange;
    source: DataSource;
};

export type ItineraryStop = {
    id: string;
    title: string;
    startAt: string;
    endAt?: string | null;
    description?: string | null;
    locationId?: string | null;
    priceRange?: PriceRange;
};

export type TransitObservation = {
    id: string;
    description: string;
    observedAt: string;
    freshness: string;
    source: DataSource;
};

export type VerifiedLocation = {
    id: string;
    name: string;
    address?: string | null;
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

export type SourceStatus = {
    status: 'available' | 'unavailable';
    code?: string | null;
    reason?: string | null;
};

export type OutingSourceStatuses = {
    events: SourceStatus;
    places: SourceStatus;
    transit: SourceStatus;
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
    policeIncidents: {
        status: 'unavailable';
        reason: string;
    };
    locations: VerifiedLocation[];
    sourceStatus: OutingSourceStatuses;
};

export type GenerateOutingRequest = {
    outingRequest: string;
    startingLocation: string;
    date?: string;
    time?: string;
    interests?: string[];
};
