import { createContext } from 'react';
import type { VerifiedLocation, VerifiedRoute } from '../types/outing';

export type DashboardMapLayerId = 'plan' | 'events' | 'places';

export type MapTarget = {
    layerId: DashboardMapLayerId;
    locationId: string;
};

export type DashboardMapLayer = {
    id: DashboardMapLayerId;
    label: string;
    locations: VerifiedLocation[];
    routes: VerifiedRoute[];
    stopNumbers: Map<string, number>;
    onSelectLocation: (locationId: string) => void;
};

export type DashboardMapContextValue = {
    layers: Map<DashboardMapLayerId, DashboardMapLayer>;
    selected?: MapTarget;
    highlighted?: MapTarget;
    registerLayer: (layer: DashboardMapLayer) => () => void;
    selectLocation: (layerId: DashboardMapLayerId, locationId?: string) => void;
    highlightLocation: (layerId: DashboardMapLayerId, locationId?: string) => void;
};

export const DashboardMapContext = createContext<DashboardMapContextValue | null>(null);
