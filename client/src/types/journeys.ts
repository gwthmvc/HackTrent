export type JourneyPointInput = {
    stopId?: string;
    name?: string;
    latitude?: number;
    longitude?: number;
};

export type TransitJourneySearchRequest = {
    agencyId?: 'durham';
    origin: JourneyPointInput;
    destination: JourneyPointInput;
    serviceDate: string;
    departureTime: string;
    maxWalkingDistanceMeters?: number;
    maxResults?: number;
};

export type ScheduledStop = {
    stopId: string;
    name: string;
    latitude: number;
    longitude: number;
};

export type ScheduledTransitJourney = {
    tripId: string;
    routeId: string;
    routeNumber: string;
    routeName: string | null;
    headsign: string | null;
    boardingStop: ScheduledStop;
    alightingStop: ScheduledStop;
    scheduledDeparture: string;
    scheduledArrival: string;
    scheduledDurationSeconds: number;
    shapeId: string | null;
};

export type TransitJourneySearchResponse = {
    agencyId: 'durham';
    timezone: string;
    serviceDate: string;
    requestedDepartureTime: string;
    retrievedAt: string;
    journeyType: 'direct';
    feed: {
        sourceUrl: string;
        importedAt: string;
        sourceLastModified: string | null;
        version: string;
        validFrom: string;
        validUntil: string;
        freshness: 'current' | 'upcoming' | 'expired';
    };
    journeys: ScheduledTransitJourney[];
    limitations: string[];
};
