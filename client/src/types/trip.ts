export interface TripPreferences {
    prompt: string;
    location: string;
    date: string;
    departureTime: string;
    returnTime: string;
    interests: string;
    budget: number;
}

export interface Coordinates {
    lat: number;
    lng: number;
}

export interface SuggestedPlace {
    id: string;
    name: string;
    type: 'Event' | 'Location';
    description: string;
    time: string;
    price: string;
    coordinates: Coordinates;
}

export interface ItineraryStop {
    id: string;
    time: string;
    title: string;
    description: string;
    placeId?: string;
}

export interface TripPlan {
    source: 'mock' | 'live';
    request: TripPreferences;
    mapCenter: Coordinates;
    itinerary: ItineraryStop[];
    places: SuggestedPlace[];
}
