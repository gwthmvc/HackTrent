import { useContext, useEffect, useMemo } from 'react';
import {
    DashboardMapContext,
    type DashboardMapLayer,
} from './dashboardMapContext';

type RegisterLayerOptions = DashboardMapLayer & {
    enabled?: boolean;
};

export function useDashboardMapLayer({
    enabled = true,
    id,
    label,
    locations,
    routes,
    stopNumbers,
    onSelectLocation,
}: RegisterLayerOptions) {
    const context = useContext(DashboardMapContext);
    if (!context) {
        throw new Error('Dashboard map layers must be used inside DashboardMapProvider.');
    }
    const { registerLayer, selectLocation, highlightLocation } = context;

    useEffect(() => {
        if (!enabled) return undefined;
        return registerLayer({ id, label, locations, routes, stopNumbers, onSelectLocation });
    }, [enabled, id, label, locations, onSelectLocation, registerLayer, routes, stopNumbers]);

    return useMemo(() => ({
        selectLocation: (locationId?: string) => selectLocation(id, locationId),
        highlightLocation: (locationId?: string) => highlightLocation(id, locationId),
    }), [highlightLocation, id, selectLocation]);
}
