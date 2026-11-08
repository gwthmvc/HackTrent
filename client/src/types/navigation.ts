import type { OutingPlan, VerifiedLocation } from './outing';
import type { EventSearchResponse } from './events';
import type { PlaceSearchResponse } from './places';
import type { TransitContextResponse } from './transit';

export type DashboardLocationState = {
    request: string;
    startingLocation: string;
    startingLocationSource: 'field' | 'prompt';
    startingPoint?: VerifiedLocation;
    transitContext?: TransitContextResponse;
    transitError?: string;
    eventsContext?: EventSearchResponse;
    eventsError?: string;
    placesContext?: PlaceSearchResponse;
    placesError?: string;
    plan?: OutingPlan;
    integrationUnavailable?: boolean;
};
