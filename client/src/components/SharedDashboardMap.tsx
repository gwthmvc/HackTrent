import { useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import VerifiedMap, { type MapMarkerVariant } from './VerifiedMap';
import {
    DashboardMapContext,
    type DashboardMapContextValue,
    type DashboardMapLayer,
    type DashboardMapLayerId,
    type MapTarget,
} from './dashboardMapContext';
import type { VerifiedLocation, VerifiedRoute } from '../types/outing';
import type { TransitVehicleObservation } from '../types/transit';

type SharedDashboardLayoutProps = {
    children: ReactNode;
    startingPoint?: VerifiedLocation;
    transitVehicles?: TransitVehicleObservation[];
};

type SharedDashboardMapProps = {
    startingPoint?: VerifiedLocation;
    transitVehicles?: TransitVehicleObservation[];
    resizeToken: string;
};

const LAYER_VARIANTS: Record<DashboardMapLayerId, MapMarkerVariant> = {
    plan: 'plan',
    events: 'event',
    places: 'place',
};

const LAYER_PREFIXES: Record<DashboardMapLayerId, string> = {
    plan: '',
    events: 'E',
    places: 'P',
};

const EMPTY_STOP_NUMBERS = new Map<string, number>();
const SIGHTING_RADIUS_KM = 5;

function haversineDistanceKm(
    latitudeA: number,
    longitudeA: number,
    latitudeB: number,
    longitudeB: number,
): number {
    const toRadians = (degrees: number) => degrees * Math.PI / 180;
    const latitudeDelta = toRadians(latitudeB - latitudeA);
    const longitudeDelta = toRadians(longitudeB - longitudeA);
    const a = Math.sin(latitudeDelta / 2) ** 2
        + Math.cos(toRadians(latitudeA))
        * Math.cos(toRadians(latitudeB))
        * Math.sin(longitudeDelta / 2) ** 2;
    return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function formatObservationTime(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('en-CA');
}

function sentencePeriod(value: string): string {
    return value.endsWith('.') ? '' : '.';
}

function compositeLocationId(layerId: DashboardMapLayerId, locationId: string): string {
    return `${layerId}::${locationId}`;
}

function locationDedupeKey(location: VerifiedLocation): string {
    const latitude = location.latitude.toFixed(5);
    const longitude = location.longitude.toFixed(5);
    return `${latitude}::${longitude}::${location.name.trim().toLocaleLowerCase()}`;
}

export function DashboardMapProvider({ children }: { children: ReactNode }) {
    const [layers, setLayers] = useState<Map<DashboardMapLayerId, DashboardMapLayer>>(
        () => new Map(),
    );
    const [selected, setSelected] = useState<MapTarget>();
    const [highlighted, setHighlighted] = useState<MapTarget>();

    const registerLayer = useCallback((layer: DashboardMapLayer) => {
        setLayers((current) => {
            const next = new Map(current);
            next.set(layer.id, layer);
            return next;
        });

        return () => {
            setLayers((current) => {
                if (current.get(layer.id) !== layer) return current;
                const next = new Map(current);
                next.delete(layer.id);
                return next;
            });
        };
    }, []);

    const selectLocation = useCallback((layerId: DashboardMapLayerId, locationId?: string) => {
        setSelected(locationId ? { layerId, locationId } : undefined);
    }, []);

    const highlightLocation = useCallback((layerId: DashboardMapLayerId, locationId?: string) => {
        setHighlighted(locationId ? { layerId, locationId } : undefined);
    }, []);

    const value = useMemo<DashboardMapContextValue>(() => ({
        layers,
        selected,
        highlighted,
        registerLayer,
        selectLocation,
        highlightLocation,
    }), [highlightLocation, highlighted, layers, registerLayer, selectLocation, selected]);

    return (
        <DashboardMapContext.Provider value={value}>
            {children}
        </DashboardMapContext.Provider>
    );
}

function SharedDashboardMap({
    startingPoint,
    transitVehicles = [],
    resizeToken,
}: SharedDashboardMapProps) {
    const context = useContext(DashboardMapContext);
    if (!context) {
        throw new Error('SharedDashboardMap must be used inside DashboardMapProvider.');
    }
    const { layers, selected, highlighted, selectLocation } = context;
    const [layerVisibility, setLayerVisibility] = useState<Partial<Record<DashboardMapLayerId, boolean>>>({});
    const [showTransit, setShowTransit] = useState(true);

    const registeredLayers = useMemo(() => Array.from(layers.values()), [layers]);
    const visibleLayers = useMemo(
        () => registeredLayers.filter((layer) => layerVisibility[layer.id] !== false),
        [layerVisibility, registeredLayers],
    );
    const nearbyTransitVehicles = useMemo(() => {
        if (!startingPoint
            || !Number.isFinite(startingPoint.latitude)
            || !Number.isFinite(startingPoint.longitude)) {
            return transitVehicles;
        }
        return transitVehicles.filter((vehicle) => haversineDistanceKm(
            startingPoint.latitude,
            startingPoint.longitude,
            vehicle.latitude,
            vehicle.longitude,
        ) <= SIGHTING_RADIUS_KM);
    }, [startingPoint, transitVehicles]);
    const latestNearbyObservation = useMemo(
        () => nearbyTransitVehicles.reduce<string | undefined>((latest, vehicle) => {
            if (!latest || new Date(vehicle.observedAt).getTime() > new Date(latest).getTime()) {
                return vehicle.observedAt;
            }
            return latest;
        }, undefined),
        [nearbyTransitVehicles],
    );
    const transitLegend = startingPoint
        && Number.isFinite(startingPoint.latitude)
        && Number.isFinite(startingPoint.longitude)
        ? latestNearbyObservation
        ? (() => {
            const formattedObservation = formatObservationTime(latestNearbyObservation);
            return `Historical sightings, not live. Last observed ${formattedObservation}${sentencePeriod(formattedObservation)}`;
        })()
            : 'No historical sightings within 5 km of your starting point.'
        : 'Historical sightings across Durham Region, not live.';
    const hasStartingCoordinates = Boolean(
        startingPoint
        && Number.isFinite(startingPoint.latitude)
        && Number.isFinite(startingPoint.longitude),
    );

    const mapContent = useMemo(() => {
        const locations: VerifiedLocation[] = [];
        const routes: VerifiedRoute[] = [];
        const markerLabels = new Map<string, string>();
        const markerVariants = new Map<string, MapMarkerVariant>();
        const owners = new Map<string, MapTarget>();
        const seenLocationIds = new Set<string>();
        const seenLocationKeys = new Set<string>();
        let mergedLocationCount = 0;
        // Events are processed first so duplicate locations keep their event marker and label.
        const layersInMarkerOrder = [...visibleLayers].sort((left, right) => (
            left.id === 'events' ? -1 : right.id === 'events' ? 1 : 0
        ));

        layersInMarkerOrder.forEach((layer) => {
            layer.locations.forEach((location, index) => {
                if (!Number.isFinite(location.latitude) || !Number.isFinite(location.longitude)) {
                    return;
                }
                const compositeId = compositeLocationId(layer.id, location.id);
                const locationKey = locationDedupeKey(location);
                if (seenLocationIds.has(location.id) || seenLocationKeys.has(locationKey)) {
                    mergedLocationCount += 1;
                    return;
                }
                seenLocationIds.add(location.id);
                seenLocationKeys.add(locationKey);
                const number = layer.stopNumbers.get(location.id) ?? index + 1;
                locations.push({ ...location, id: compositeId });
                markerLabels.set(compositeId, `${LAYER_PREFIXES[layer.id]}${number}`);
                markerVariants.set(compositeId, LAYER_VARIANTS[layer.id]);
                owners.set(compositeId, { layerId: layer.id, locationId: location.id });
            });
            routes.push(...layer.routes);
        });

        return { locations, routes, markerLabels, markerVariants, owners, mergedLocationCount };
    }, [visibleLayers]);

    const selectedLocationId = selected && layerVisibility[selected.layerId] !== false
        ? compositeLocationId(selected.layerId, selected.locationId)
        : undefined;
    const highlightedLocationId = highlighted && layerVisibility[highlighted.layerId] !== false
        ? compositeLocationId(highlighted.layerId, highlighted.locationId)
        : undefined;

    const handleSelectLocation = useCallback((compositeId: string) => {
        const owner = mapContent.owners.get(compositeId);
        if (!owner) return;
        selectLocation(owner.layerId, owner.locationId);
        layers.get(owner.layerId)?.onSelectLocation(owner.locationId);
    }, [layers, mapContent.owners, selectLocation]);

    const toggleLayer = (layerId: DashboardMapLayerId) => {
        setLayerVisibility((current) => ({
            ...current,
            [layerId]: current[layerId] === false,
        }));
    };

    return (
        <aside className="shared-dashboard-map-column" aria-labelledby="shared-map-heading">
            <div className="shared-map-header">
                <div>
                    <p className="dashboard-eyebrow">One shared map</p>
                    <h2 id="shared-map-heading">Your outing at a glance</h2>
                </div>
                <p>Choose which verified layers appear.</p>
            </div>
            <div className="shared-map-layer-controls" aria-label="Map layers">
                {registeredLayers.map((layer) => {
                    const visible = layerVisibility[layer.id] !== false;
                    return (
                        <button
                            key={layer.id}
                            className={`${layer.id}${visible ? ' active' : ''}`}
                            type="button"
                            aria-pressed={visible}
                            onClick={() => toggleLayer(layer.id)}
                        >
                            <span aria-hidden="true" />
                            {layer.label} ({layer.locations.length})
                        </button>
                    );
                })}
                {transitVehicles.length > 0 && (
                    <button
                        className={`transit${showTransit ? ' active' : ''}`}
                        type="button"
                        aria-pressed={showTransit}
                        onClick={() => setShowTransit((current) => !current)}
                    >
                        <span aria-hidden="true" />
                        {hasStartingCoordinates
                            ? `Nearby sightings (${nearbyTransitVehicles.length})`
                            : `TigerData (${nearbyTransitVehicles.length})`}
                    </button>
                )}
            </div>
            <VerifiedMap
                startingPoint={startingPoint}
                transitVehicles={showTransit ? nearbyTransitVehicles : []}
                locations={mapContent.locations}
                routes={mapContent.routes}
                selectedLocationId={selectedLocationId}
                highlightedLocationId={highlightedLocationId}
                stopNumbers={EMPTY_STOP_NUMBERS}
                markerLabels={mapContent.markerLabels}
                markerVariants={mapContent.markerVariants}
                resizeToken={resizeToken}
                onSelectLocation={handleSelectLocation}
            />
            <p className="shared-map-note">
                Event, place, itinerary, and vehicle markers share this map. TigerData points are observations,
                not inferred routes or arrival estimates.
            </p>
            {transitVehicles.length > 0 && <p className="shared-map-transit-legend">{transitLegend}</p>}
        </aside>
    );
}

export function SharedDashboardLayout({
    children,
    startingPoint,
    transitVehicles,
}: SharedDashboardLayoutProps) {
    const [mobileView, setMobileView] = useState<'list' | 'map'>('list');

    return (
        <>
            <div className="mobile-view-toggle shared-dashboard-view-toggle" aria-label="Choose dashboard view">
                <button className={mobileView === 'list' ? 'active' : ''} type="button" onClick={() => setMobileView('list')}>List</button>
                <button className={mobileView === 'map' ? 'active' : ''} type="button" onClick={() => setMobileView('map')}>Map</button>
            </div>
            <div className={`shared-dashboard-layout mobile-${mobileView}`}>
                <div className="shared-dashboard-list-column">{children}</div>
                <SharedDashboardMap
                    startingPoint={startingPoint}
                    transitVehicles={transitVehicles}
                    resizeToken={mobileView}
                />
            </div>
        </>
    );
}
