import { useCallback, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useDashboardMapLayer } from './useDashboardMapLayer';
import type { VerifiedLocation } from '../types/outing';
import type { DiscoveredPlace, PlaceCategory, PlaceSearchResponse } from '../types/places';

type PlacesExplorerProps = {
    context?: PlaceSearchResponse;
    error?: string;
};

type CategoryFilter = 'all' | PlaceCategory;
type ProximityFilter = 'all' | '1000' | '3000' | '5000';
const NO_ROUTES: [] = [];
const CATEGORY_LABELS: Record<PlaceCategory, string> = {
    food: 'Restaurants & cafés',
    parks_outdoors: 'Parks & outdoors',
    culture: 'Museums & culture',
    entertainment_family: 'Entertainment & family',
};

function locationId(place: DiscoveredPlace): string {
    return `place-${place.id}`;
}
function formatDistance(distanceMeters: number): string {
    if (distanceMeters < 100) return 'Under 100 m';
    if (distanceMeters < 1_000) return `${Math.round(distanceMeters / 50) * 50} m`;
    return `${(distanceMeters / 1_000).toFixed(1)} km`;
}
function safeOsmUrl(value: string): string | undefined {
    try {
        const url = new URL(value);
        return url.protocol === 'https:' && url.hostname === 'www.openstreetmap.org'
            ? url.toString()
            : undefined;
    } catch {
        return undefined;
    }
}

export default function PlacesExplorer({
    context,
    error,
}: PlacesExplorerProps) {
    const places = useMemo(() => context?.places ?? [], [context]);
    const [category, setCategory] = useState<CategoryFilter>('all');
    const [proximity, setProximity] = useState<ProximityFilter>('all');
    const [selectedPlaceId, setSelectedPlaceId] = useState<string>();
    const cardRefs = useRef<Map<string, HTMLElement>>(new Map());

    const filteredPlaces = useMemo(() => places.filter((place) => {
        const categoryMatches = category === 'all' || place.category === category;
        const proximityMatches = proximity === 'all'
            || place.distanceMeters <= Number(proximity);
        return categoryMatches && proximityMatches;
    }), [category, places, proximity]);

    const { locations, pinNumbers } = useMemo(() => {
        const mapped: VerifiedLocation[] = [];
        const numbers = new Map<string, number>();
        filteredPlaces.forEach((place) => {
            const id = locationId(place);
            mapped.push({
                id,
                name: place.name,
                address: place.address ?? undefined,
                latitude: place.latitude,
                longitude: place.longitude,
                source: { name: 'OpenStreetMap', url: safeOsmUrl(place.sourceUrl) },
            });
            numbers.set(id, mapped.length);
        });
        return { locations: mapped, pinNumbers: numbers };
    }, [filteredPlaces]);

    const selectFromMap = useCallback((id: string) => {
        const place = filteredPlaces.find((candidate) => locationId(candidate) === id);
        if (!place) return;
        setSelectedPlaceId(place.id);
        cardRefs.current.get(place.id)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, [filteredPlaces]);

    const mapLayer = useDashboardMapLayer({
        id: 'places',
        label: 'Places',
        locations,
        routes: NO_ROUTES,
        stopNumbers: pinNumbers,
        onSelectLocation: selectFromMap,
        enabled: Boolean(context),
    });

    const selectCard = (place: DiscoveredPlace) => {
        setSelectedPlaceId(place.id);
        mapLayer.selectLocation(locationId(place));
    };

    const handleCardKeyDown = (event: KeyboardEvent<HTMLElement>, place: DiscoveredPlace) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            selectCard(place);
        }
    };

    if (!context) {
        return (
            <aside className="transit-data-status unavailable places-status" role="status">
                <div>
                    <p className="dashboard-eyebrow">OpenStreetMap places</p>
                    <strong>Place discovery unavailable</strong>
                </div>
                <p>{error ?? 'No place search was performed.'}</p>
            </aside>
        );
    }

    return (
        <section className="places-explorer-section" aria-labelledby="places-heading">
            <div className="outing-explorer cards-only">
                <section className="explorer-list-panel" aria-labelledby="places-heading">
                    <div className="explorer-list-header">
                        <div>
                            <p className="home-eyebrow">OpenStreetMap · {context.areaName}</p>
                            <h3 id="places-heading">Places near {context.anchor.name}</h3>
                        </div>
                        <span>{filteredPlaces.length} shown</span>
                    </div>

                    <div className="place-filter-row">
                        <div className="map-filters" aria-label="Filter places by category">
                            {(['all', ...Object.keys(CATEGORY_LABELS)] as CategoryFilter[]).map((value) => (
                                <button
                                    key={value}
                                    className={category === value ? 'active' : ''}
                                    type="button"
                                    onClick={() => {
                                        setCategory(value);
                                        setSelectedPlaceId(undefined);
                                        mapLayer.selectLocation();
                                    }}
                                    aria-pressed={category === value}
                                >
                                    {value === 'all' ? 'All places' : CATEGORY_LABELS[value]}
                                </button>
                            ))}
                        </div>
                        <label className="proximity-filter">
                            Proximity
                            <select
                                value={proximity}
                                onChange={(event) => {
                                    setProximity(event.target.value as ProximityFilter);
                                    setSelectedPlaceId(undefined);
                                    mapLayer.selectLocation();
                                }}
                            >
                                <option value="all">Entire search area</option>
                                <option value="1000">Within 1 km</option>
                                <option value="3000">Within 3 km</option>
                                <option value="5000">Within 5 km</option>
                            </select>
                        </label>
                    </div>

                    <p className="result-meta places-summary">
                        Sorted by straight-line distance from {context.anchor.name}. No ratings, prices,
                        opening hours, availability, routes, or travel times are inferred.
                    </p>

                    <div className="result-location-list">
                        {filteredPlaces.map((place) => {
                            const id = locationId(place);
                            const selected = place.id === selectedPlaceId;
                            const sourceUrl = safeOsmUrl(place.sourceUrl);
                            return (
                                <article
                                    key={place.id}
                                    ref={(element) => {
                                        if (element) cardRefs.current.set(place.id, element);
                                        else cardRefs.current.delete(place.id);
                                    }}
                                    className={`result-location-card place-card${selected ? ' selected' : ''}`}
                                    tabIndex={0}
                                    role="button"
                                    aria-pressed={selected}
                                    onClick={() => selectCard(place)}
                                    onKeyDown={(event) => handleCardKeyDown(event, place)}
                                    onMouseEnter={() => mapLayer.highlightLocation(id)}
                                    onMouseLeave={() => mapLayer.highlightLocation()}
                                    onFocus={() => mapLayer.highlightLocation(id)}
                                    onBlur={() => mapLayer.highlightLocation()}
                                >
                                    <div className="location-card-number">{String(pinNumbers.get(id)).padStart(2, '0')}</div>
                                    <div>
                                        <div className="result-card-heading">
                                            <div>
                                                <p className="result-kicker">{CATEGORY_LABELS[place.category]} · {place.subtype}</p>
                                                <h4>{place.name}</h4>
                                            </div>
                                            <strong>{formatDistance(place.distanceMeters)}</strong>
                                        </div>
                                        {place.address
                                            ? <p className="result-meta">{place.address}</p>
                                            : <p className="map-link-unavailable">Address unavailable from OpenStreetMap</p>}
                                        <p className="result-source">
                                            Source:{' '}
                                            {sourceUrl
                                                ? <a href={sourceUrl} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>View on OpenStreetMap</a>
                                                : 'OpenStreetMap source link unavailable'}
                                        </p>
                                    </div>
                                </article>
                            );
                        })}
                        {filteredPlaces.length === 0 && (
                            <p className="unavailable-note">No verified places match these filters.</p>
                        )}
                    </div>
                    <p className="osm-attribution">
                        Data © <a href={context.source.url} target="_blank" rel="noreferrer">OpenStreetMap contributors</a>, queried through {context.source.service}.
                    </p>
                </section>

            </div>
        </section>
    );
}

