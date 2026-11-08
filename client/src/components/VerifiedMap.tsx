import { useEffect, useRef, type MutableRefObject } from 'react';
import { divIcon, latLngBounds, type Marker as LeafletMarker } from 'leaflet';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { VerifiedLocation, VerifiedRoute } from '../types/outing';
import type { TransitVehicleObservation } from '../types/transit';

const ONTARIO_CENTER: [number, number] = [49.2, -84.7];

export type MapMarkerVariant = 'plan' | 'event' | 'place';

type VerifiedMapProps = {
    startingPoint?: VerifiedLocation;
    transitVehicles?: TransitVehicleObservation[];
    locations: VerifiedLocation[];
    routes: VerifiedRoute[];
    selectedLocationId?: string;
    highlightedLocationId?: string;
    stopNumbers: Map<string, number>;
    markerLabels?: Map<string, string>;
    markerVariants?: Map<string, MapMarkerVariant>;
    resizeToken?: string;
    onSelectLocation: (locationId: string) => void;
};

type MapBehaviourProps = {
    startingPoint?: VerifiedLocation;
    transitVehicles: TransitVehicleObservation[];
    locations: VerifiedLocation[];
    routes: VerifiedRoute[];
    selectedLocationId?: string;
    resizeToken?: string;
    markerRefs: MutableRefObject<Map<string, LeafletMarker>>;
};

function MapBehaviour({ startingPoint, transitVehicles, locations, routes, selectedLocationId, resizeToken, markerRefs }: MapBehaviourProps) {
    const map = useMap();

    useEffect(() => {
        const routePositions = routes.flatMap((route) => route.coordinates.map(
            (coordinate) => [coordinate.latitude, coordinate.longitude] as [number, number],
        ));
        const positions = [
            ...(startingPoint
                ? [[startingPoint.latitude, startingPoint.longitude] as [number, number]]
                : []),
            ...transitVehicles.map((vehicle) => [vehicle.latitude, vehicle.longitude] as [number, number]),
            ...locations.map((location) => [location.latitude, location.longitude] as [number, number]),
            ...routePositions,
        ];

        if (positions.length === 0) {
            map.setView(ONTARIO_CENTER, 5);
            return;
        }

        if (positions.length === 1) {
            map.setView(positions[0], 14);
            return;
        }

        const bounds = latLngBounds(positions);
        map.fitBounds(bounds, { padding: [48, 48], maxZoom: 15 });
    }, [locations, map, resizeToken, routes, startingPoint, transitVehicles]);

    useEffect(() => {
        const frame = window.requestAnimationFrame(() => map.invalidateSize());
        return () => window.cancelAnimationFrame(frame);
    }, [map, resizeToken]);

    useEffect(() => {
        if (!selectedLocationId) return;

        const selected = locations.find((location) => location.id === selectedLocationId);
        const marker = markerRefs.current.get(selectedLocationId);
        if (selected) {
            map.panTo([selected.latitude, selected.longitude]);
        }
        marker?.openPopup();
    }, [locations, map, markerRefs, selectedLocationId]);

    return null;
}

function markerIcon(label: string, active: boolean, variant: MapMarkerVariant) {
    return divIcon({
        className: 'smartmove-marker-shell',
        html: `<span class="smartmove-marker ${variant}${active ? ' active' : ''}"><b>${label}</b></span>`,
        iconSize: [38, 38],
        iconAnchor: [19, 19],
        popupAnchor: [0, -21],
    });
}

function startingMarkerIcon() {
    return divIcon({
        className: 'smartmove-marker-shell',
        html: '<span class="smartmove-marker starting"><b>S</b></span>',
        iconSize: [42, 42],
        iconAnchor: [21, 21],
        popupAnchor: [0, -23],
    });
}

function transitMarkerIcon(freshness: TransitVehicleObservation['freshness']['status']) {
    return divIcon({
        className: 'smartmove-marker-shell',
        html: `<span class="smartmove-transit-marker ${freshness}"><b aria-hidden="true">T</b></span>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
        popupAnchor: [0, -17],
    });
}

function formatObservationTime(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('en-CA');
}

export default function VerifiedMap({
    startingPoint,
    transitVehicles = [],
    locations,
    routes,
    selectedLocationId,
    highlightedLocationId,
    stopNumbers,
    markerLabels,
    markerVariants,
    resizeToken,
    onSelectLocation,
}: VerifiedMapProps) {
    const markerRefs = useRef<Map<string, LeafletMarker>>(new Map());

    return (
        <div className="leaflet-map-shell">
            <MapContainer
                className="smartmove-map"
                center={ONTARIO_CENTER}
                zoom={5}
                minZoom={4}
                maxZoom={18}
                scrollWheelZoom
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <MapBehaviour
                    startingPoint={startingPoint}
                    transitVehicles={transitVehicles}
                    locations={locations}
                    routes={routes}
                    selectedLocationId={selectedLocationId}
                    resizeToken={resizeToken}
                    markerRefs={markerRefs}
                />
                {routes.map((route) => (
                    <Polyline
                        key={route.id}
                        positions={route.coordinates.map((coordinate) => [
                            coordinate.latitude,
                            coordinate.longitude,
                        ])}
                        pathOptions={{ color: '#1e4d8c', weight: 5, opacity: 0.78 }}
                    >
                        <Popup>
                            <strong>{route.mode ? `${route.mode} route` : 'Verified route'}</strong>
                            <br />
                            Source: {route.source.name}
                        </Popup>
                    </Polyline>
                ))}
                {startingPoint && (
                    <Marker
                        position={[startingPoint.latitude, startingPoint.longitude]}
                        icon={startingMarkerIcon()}
                        zIndexOffset={1000}
                    >
                        <Popup>
                            <strong>Starting point</strong>
                            <br />
                            {startingPoint.name}
                            {startingPoint.address && <><br />{startingPoint.address}</>}
                            <br />
                            <small>Verified by {startingPoint.source.name}</small>
                        </Popup>
                    </Marker>
                )}
                {transitVehicles.map((vehicle) => (
                    <Marker
                        key={`transit-${vehicle.agencyId}-${vehicle.vehicleId}`}
                        position={[vehicle.latitude, vehicle.longitude]}
                        icon={transitMarkerIcon(vehicle.freshness.status)}
                    >
                        <Popup>
                            <strong>{vehicle.agencyId === 'durham' ? 'Durham Region Transit' : 'Kingston Transit'} observation</strong>
                            <br />
                            Vehicle {vehicle.vehicleId}
                            {vehicle.routeId && <><br />Reported route ID: {vehicle.routeId}</>}
                            <br />
                            Observed {formatObservationTime(vehicle.observedAt)}
                            <br />
                            <span className={`transit-popup-status ${vehicle.freshness.status}`}>
                                {vehicle.freshness.status === 'current'
                                    ? 'Current observation'
                                    : 'Historical observation — not live'}
                            </span>
                            <br />
                            <small>TigerData vehicle position only — no route directions or ETA</small>
                        </Popup>
                    </Marker>
                ))}
                {locations.map((location) => {
                    const stopNumber = stopNumbers.get(location.id);
                    const markerLabel = markerLabels?.get(location.id)
                        ?? (stopNumber ? String(stopNumber) : '•');
                    const markerVariant = markerVariants?.get(location.id) ?? 'plan';
                    const active = location.id === selectedLocationId
                        || location.id === highlightedLocationId;
                    return (
                        <Marker
                            key={location.id}
                            position={[location.latitude, location.longitude]}
                            icon={markerIcon(markerLabel, active, markerVariant)}
                            ref={(marker) => {
                                if (marker) markerRefs.current.set(location.id, marker);
                                else markerRefs.current.delete(location.id);
                            }}
                            eventHandlers={{ click: () => onSelectLocation(location.id) }}
                        >
                            <Popup>
                                <strong>{markerLabel !== '•' ? `${markerLabel}. ` : ''}{location.name}</strong>
                                {location.address && <><br />{location.address}</>}
                                <br />
                                <small>Verified by {location.source.name}</small>
                            </Popup>
                        </Marker>
                    );
                })}
            </MapContainer>
            {locations.length === 0 && (
                <div className="map-empty-state" role="status">
                    <strong>{startingPoint || transitVehicles.length > 0 ? 'No verified recommendations yet' : 'No verified locations yet'}</strong>
                    <span>
                        {transitVehicles.length > 0
                            ? `${transitVehicles.length} verified transit observation${transitVehicles.length === 1 ? '' : 's'} shown separately from routes and arrival estimates.`
                            : startingPoint
                                ? 'The starting point is shown. Recommendation markers will appear after the planning API returns sourced coordinates.'
                            : 'The map is live. Markers will appear when the planning API returns sourced coordinates.'}
                    </span>
                </div>
            )}
        </div>
    );
}
