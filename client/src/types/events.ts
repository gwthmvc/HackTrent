export type EventCoordinateStatus = 'verified' | 'missing' | 'outside_search_area';

export type EventPriceRange = {
    min: number | null;
    max: number | null;
    currency: string;
};

export type EventVenue = {
    name: string;
    address: string | null;
    city: string | null;
    province: string | null;
    postalCode: string | null;
    latitude: number | null;
    longitude: number | null;
    coordinateStatus: EventCoordinateStatus;
};

export type TicketmasterEvent = {
    id: string;
    name: string;
    url: string | null;
    startLocalDate: string;
    startLocalTime: string | null;
    startDateTime: string | null;
    status: string | null;
    priceRange: EventPriceRange | null;
    venue: EventVenue;
    imageUrl: string | null;
    classification: string | null;
};

export type EventSearchResponse = {
    areaId: string;
    areaName: string;
    transitCoverage: boolean;
    retrievedAt: string;
    cached: boolean;
    window: {
        start: string;
        end: string;
        description: string;
        timeFrom: string | null;
        timeTo: string | null;
    };
    classifications: string[];
    totalAvailable: number;
    events: TicketmasterEvent[];
    source: { name: string; url: string };
};

export type EventSearchRequest = {
    startingLocation: string;
    outingRequest: string;
    date?: string;
    time?: string;
    interests?: string[];
};
