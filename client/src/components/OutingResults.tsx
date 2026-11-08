import { useCallback, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { useDashboardMapLayer } from './useDashboardMapLayer';
import type {
    DataSource,
    ItineraryStop,
    OutingPlan,
    OutingRecommendation,
    PriceRange,
    VerifiedLocation,
    VerifiedRoute,
} from '../types/outing';

type OutingResultsProps = {
    plan: OutingPlan;
};
type LocationFilter = 'all' | 'itinerary' | 'activities';

type ResultCard = {
    key: string;
    location?: VerifiedLocation;
    recommendation?: OutingRecommendation;
    stop?: ItineraryStop;
};

const EMPTY_ROUTES: VerifiedRoute[] = [];

function matchesFilter(card: ResultCard, filter: LocationFilter): boolean {
    if (filter === 'itinerary') return Boolean(card.stop);
    if (filter === 'activities') return Boolean(card.recommendation);
    return true;
}

function formatDateTime(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en-CA', {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(date);
}

function formatDate(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en-CA', {
        dateStyle: 'medium',
    }).format(date);
}

function formatTime(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en-CA', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
    }).format(date);
}

type JourneyTimelineAxis = {
    start: number;
    end: number;
};

function journeyTimeline(
    scheduledDeparture: string,
    scheduledArrival: string,
    axis: JourneyTimelineAxis | undefined,
): { start: string; width: string } | undefined {
    const departure = new Date(scheduledDeparture).getTime();
    const arrival = new Date(scheduledArrival).getTime();
    if (!axis || !Number.isFinite(departure) || !Number.isFinite(arrival) || arrival < departure) {
        return undefined;
    }
    const span = axis.end - axis.start;
    if (span <= 0) return undefined;
    return {
        start: `${((departure - axis.start) / span) * 100}%`,
        width: `${((arrival - departure) / span) * 100}%`,
    };
}

function formatPriceRange(priceRange: PriceRange): string {
    try {
        const formatter = new Intl.NumberFormat('en-CA', {
            style: 'currency',
            currency: priceRange.currency,
        });
        return `${formatter.format(priceRange.min)} – ${formatter.format(priceRange.max)}`;
    } catch {
        return `${priceRange.min} – ${priceRange.max} ${priceRange.currency}`;
    }
}

function safeSourceUrl(url?: string | null): string | undefined {
    if (!url) return undefined;
    try {
        const parsedUrl = new URL(url);
        return parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:'
            ? parsedUrl.toString()
            : undefined;
    } catch {
        return undefined;
    }
}

function SourceLine({ source }: { source: DataSource }) {
    const url = safeSourceUrl(source.url);
    return (
        <p className="result-source">
            Source:{' '}
            {url ? <a href={url} target="_blank" rel="noreferrer">{source.name}</a> : source.name}
            {source.retrievedAt && ` · Retrieved ${formatDateTime(source.retrievedAt)}`}
        </p>
    );
}

export default function OutingResults({ plan }: OutingResultsProps) {
    const [showAllObservations, setShowAllObservations] = useState(false);
    const stopNumbers = useMemo(() => {
        const numbers = new Map<string, number>();
        plan.itinerary.forEach((stop, index) => {
            if (stop.locationId && !numbers.has(stop.locationId)) {
                numbers.set(stop.locationId, index + 1);
            }
        });
        return numbers;
    }, [plan.itinerary]);

    const cards = useMemo(() => {
        const locationsById = new Map(
            plan.locations.map((location) => [location.id, location]),
        );
        const nextCards: ResultCard[] = plan.recommendations.map((recommendation) => ({
            key: `recommendation-${recommendation.id}`,
            recommendation,
            location: recommendation.locationId
                ? locationsById.get(recommendation.locationId)
                : undefined,
            stop: recommendation.locationId
                ? plan.itinerary.find((stop) => stop.locationId === recommendation.locationId)
                : undefined,
        }));
        const representedLocationIds = new Set(
            nextCards.flatMap((card) => card.location ? [card.location.id] : []),
        );
        plan.locations.forEach((location) => {
            if (!representedLocationIds.has(location.id)) {
                nextCards.push({
                    key: `location-${location.id}`,
                    location,
                    stop: plan.itinerary.find((stop) => stop.locationId === location.id),
                });
            }
        });
        return nextCards;
    }, [plan.itinerary, plan.locations, plan.recommendations]);

    const [filter, setFilter] = useState<LocationFilter>('all');
    const [selectedCardKey, setSelectedCardKey] = useState<string | undefined>(cards[0]?.key);
    const cardRefs = useRef<Map<string, HTMLElement>>(new Map());
    const journeyTimelineAxis = useMemo<JourneyTimelineAxis | undefined>(() => {
        if (plan.journeys.status !== 'available' || plan.journeys.items.length === 0) {
            return undefined;
        }
        const departures = plan.journeys.items.map((journey) => new Date(journey.scheduledDeparture).getTime());
        const arrivals = plan.journeys.items.map((journey) => new Date(journey.scheduledArrival).getTime());
        if (departures.some((value) => !Number.isFinite(value)) || arrivals.some((value) => !Number.isFinite(value))) {
            return undefined;
        }
        return {
            start: Math.min(...departures),
            end: Math.max(...arrivals),
        };
    }, [plan.journeys]);

    const filteredCards = useMemo(
        () => cards.filter((card) => matchesFilter(card, filter)),
        [cards, filter],
    );
    const filteredLocations = useMemo(() => plan.locations.filter((location) => (
        filteredCards.some((card) => card.location?.id === location.id)
    )), [filteredCards, plan.locations]);
    const selectFromMap = useCallback((locationId: string) => {
        const card = filteredCards.find((candidate) => candidate.location?.id === locationId);
        if (card) {
            setSelectedCardKey(card.key);
            cardRefs.current.get(card.key)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }, [filteredCards]);

    const mapLayer = useDashboardMapLayer({
        id: 'plan',
        label: 'Itinerary',
        locations: filteredLocations,
        routes: EMPTY_ROUTES,
        stopNumbers,
        onSelectLocation: selectFromMap,
    });

    const selectCard = (card: ResultCard) => {
        setSelectedCardKey(card.key);
        mapLayer.selectLocation(card.location?.id);
    };

    const applyFilter = (nextFilter: LocationFilter) => {
        setFilter(nextFilter);
        const firstCard = cards.find((card) => matchesFilter(card, nextFilter));
        setSelectedCardKey(firstCard?.key);
        mapLayer.selectLocation(firstCard?.location?.id);
    };

    const handleCardKeyDown = (event: KeyboardEvent<HTMLElement>, card: ResultCard) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            selectCard(card);
        }
    };

    return (
        <section className="outing-results" aria-labelledby="results-heading">
            <div className="results-heading">
                <div>
                    <p className="home-eyebrow">Your SmartMove plan</p>
                    <h2 id="results-heading">{plan.summary.title}</h2>
                </div>
                <p>Generated {formatDateTime(plan.generatedAt)}</p>
            </div>
            <p className="results-summary">{plan.summary.description}</p>

            <div className="outing-explorer cards-only">
                <section className="explorer-list-panel" aria-labelledby="recommendations-heading">
                    <div className="explorer-list-header">
                        <div>
                            <p className="home-eyebrow">Verified recommendations</p>
                            <h3 id="recommendations-heading">Places in your plan</h3>
                        </div>
                        <span>{filteredCards.length} shown</span>
                    </div>
                    <div className="map-filters" aria-label="Filter locations">
                        {(['all', 'itinerary', 'activities'] as LocationFilter[]).map((value) => (
                            <button
                                key={value}
                                className={filter === value ? 'active' : ''}
                                type="button"
                                onClick={() => applyFilter(value)}
                                aria-pressed={filter === value}
                            >
                                {value === 'all' ? 'All places' : value === 'itinerary' ? 'Itinerary stops' : 'Activities'}
                            </button>
                        ))}
                    </div>
                    <div className="result-location-list">
                        {filteredCards.map((card) => {
                            const title = card.recommendation?.name ?? card.stop?.title ?? card.location?.name ?? 'Verified place';
                            const description = card.recommendation?.description ?? card.stop?.description;
                            const source = card.recommendation?.source ?? card.location?.source;
                            const stopNumber = card.location ? stopNumbers.get(card.location.id) : undefined;
                            const selected = card.key === selectedCardKey;
                            return (
                                <article
                                    key={card.key}
                                    ref={(element) => {
                                        if (element) cardRefs.current.set(card.key, element);
                                        else cardRefs.current.delete(card.key);
                                    }}
                                    className={`result-location-card${selected ? ' selected' : ''}${!card.location ? ' unmapped' : ''}`}
                                    tabIndex={0}
                                    role="button"
                                    aria-pressed={selected}
                                    onClick={() => selectCard(card)}
                                    onKeyDown={(event) => handleCardKeyDown(event, card)}
                                    onMouseEnter={() => mapLayer.highlightLocation(card.location?.id)}
                                    onMouseLeave={() => mapLayer.highlightLocation()}
                                    onFocus={() => mapLayer.highlightLocation(card.location?.id)}
                                    onBlur={() => mapLayer.highlightLocation()}
                                >
                                    <div className="location-card-number">{stopNumber ? String(stopNumber).padStart(2, '0') : '•'}</div>
                                    <div>
                                        <div className="result-card-heading">
                                            <div>
                                                <p className="result-kicker">{card.recommendation?.category ?? (card.stop ? 'Itinerary stop' : 'Verified location')}</p>
                                                <h4>{title}</h4>
                                            </div>
                                            {card.recommendation?.priceRange
                                                ? <strong>{formatPriceRange(card.recommendation.priceRange)}</strong>
                                                : <span className="result-unavailable-inline">Price unavailable</span>}
                                        </div>
                                        {description && <p>{description}</p>}
                                        {card.location?.address && <p className="result-meta">{card.location.address}</p>}
                                        {!card.location && <p className="map-link-unavailable">Verified coordinates unavailable — no marker shown</p>}
                                        {source && <SourceLine source={source} />}
                                    </div>
                                </article>
                            );
                        })}
                        {filteredCards.length === 0 && (
                            <p className="unavailable-note">No verified places match this filter.</p>
                        )}
                    </div>
                </section>

            </div>

            <div className="results-grid details-grid">
                <section className="result-panel itinerary-panel" aria-labelledby="itinerary-heading">
                    <div className="section-number" aria-hidden="true">01</div>
                    <h3 id="itinerary-heading">Suggested itinerary</h3>
                    {plan.itinerary.length > 0 ? (
                        <ol className="itinerary-list">
                            {plan.itinerary.map((stop) => (
                                <li key={stop.id}>
                                    <time dateTime={stop.startAt}>{formatDateTime(stop.startAt)}</time>
                                    <div>
                                        <div className="result-card-heading">
                                            <h4>{stop.title}</h4>
                                            {stop.priceRange
                                                ? <strong>{formatPriceRange(stop.priceRange)}</strong>
                                                : <span className="result-unavailable-inline">Price unavailable</span>}
                                        </div>
                                        {stop.endAt && <p className="result-meta">Until {formatDateTime(stop.endAt)}</p>}
                                        {stop.description && <p>{stop.description}</p>}
                                    </div>
                                </li>
                            ))}
                        </ol>
                    ) : <p className="unavailable-note">No verified itinerary stops were returned.</p>}
                </section>

                <section className="result-panel transit-panel" aria-labelledby="transit-heading">
                    <div className="section-number" aria-hidden="true">02</div>
                    <h3 id="transit-heading">Transit observations</h3>
                    {plan.transit.status === 'available' ? (
                        plan.transit.items.length > 0 ? (
                            <>
                                <div className="observation-list">
                                {(showAllObservations ? plan.transit.items : plan.transit.items.slice(0, 5)).map((observation) => (
                                    <article className="transit-observation-row" key={observation.id}>
                                        <p>{observation.description}</p>
                                        <p className="result-meta">Observed {formatDateTime(observation.observedAt)} · {observation.freshness}</p>
                                    </article>
                                ))}
                                </div>
                                {plan.transit.items.length > 5 && (
                                    <button
                                        className="observation-toggle"
                                        type="button"
                                        onClick={() => setShowAllObservations((expanded) => !expanded)}
                                    >
                                        {showAllObservations
                                            ? 'Show fewer'
                                            : `Show all ${plan.transit.items.length} observations`}
                                    </button>
                                )}
                                <SourceLine source={plan.transit.items[0].source} />
                            </>
                        ) : <p className="unavailable-note">Transit information unavailable: no verified observations were returned.</p>
                    ) : <p className="unavailable-note">Transit information unavailable: {plan.transit.reason}</p>}
                    {plan.transit.coverage && <p className="coverage-note">Coverage: {plan.transit.coverage}</p>}
                </section>

                <section className="result-panel transit-panel" aria-labelledby="scheduled-transit-heading">
                    <div className="section-number" aria-hidden="true">03</div>
                    <h3 id="scheduled-transit-heading">Scheduled transit</h3>
                    {plan.journeys.status === 'available' ? (
                        plan.journeys.items.length > 0 ? (
                            <div className="observation-list">
                                {plan.journeys.items.map((journey) => (
                                    (() => {
                                        const timeline = journeyTimeline(
                                            journey.scheduledDeparture,
                                            journey.scheduledArrival,
                                            journeyTimelineAxis,
                                        );
                                        return (
                                            <article key={journey.tripId}>
                                                <p><strong>Route {journey.routeNumber}</strong>{journey.headsign && ` · ${journey.headsign}`}</p>
                                                {timeline && (
                                                    <div
                                                        className="scheduled-journey-timeline"
                                                        style={{
                                                            '--journey-start': timeline.start,
                                                            '--journey-width': timeline.width,
                                                        } as CSSProperties}
                                                        aria-label={`Scheduled journey from ${formatDateTime(journey.scheduledDeparture)} to ${formatDateTime(journey.scheduledArrival)}`}
                                                    >
                                                        <span className="scheduled-journey-time">
                                                            <span className="timeline-label-date">{formatDate(journey.scheduledDeparture)}, </span>
                                                            <span className="timeline-label-time">{formatTime(journey.scheduledDeparture)}</span>
                                                        </span>
                                                        <span className="scheduled-journey-track" aria-hidden="true">
                                                            <span className="scheduled-journey-bar" />
                                                        </span>
                                                        <span className="scheduled-journey-time">
                                                            <span className="timeline-label-date">{formatDate(journey.scheduledArrival)}, </span>
                                                            <span className="timeline-label-time">{formatTime(journey.scheduledArrival)}</span>
                                                        </span>
                                                    </div>
                                                )}
                                                <p className="result-meta">Boards at {journey.boardingStop.name}, {formatDateTime(journey.scheduledDeparture)}</p>
                                                <p className="result-meta">Gets off at {journey.alightingStop.name}, {formatDateTime(journey.scheduledArrival)}</p>
                                            </article>
                                        );
                                    })()
                                ))}
                            </div>
                        ) : <p className="unavailable-note">No direct scheduled trip found.</p>
                    ) : (
                        <p className="unavailable-note">
                            Scheduled transit unavailable{plan.journeys.code && ` (${plan.journeys.code})`}: {plan.journeys.reason}
                        </p>
                    )}
                    {plan.journeys.limitations.map((limitation) => (
                        <p className="coverage-note" key={limitation}>{limitation}</p>
                    ))}
                </section>

                <section className="result-panel safety-panel" aria-labelledby="safety-heading">
                    <div className="section-number" aria-hidden="true">04</div>
                    <h3 id="safety-heading">Public incident context</h3>
                    <p className="unavailable-note">
                        Police incident information unavailable: {plan.policeIncidents.reason}
                    </p>
                </section>
            </div>

            <section className="result-panel" aria-labelledby="source-status-heading">
                <h3 id="source-status-heading">Source status</h3>
                <ul>
                    {(['events', 'places', 'transit', 'journeys'] as const).map((sourceName) => {
                        const status = plan.sourceStatus[sourceName];
                        return (
                            <li key={sourceName}>
                                <strong>{sourceName}: {status.status}</strong>
                                {status.status === 'unavailable' && (
                                    <span>
                                        {status.code && ` (${status.code})`}: {status.reason ?? 'Reason unavailable'}
                                    </span>
                                )}
                            </li>
                        );
                    })}
                </ul>
            </section>
        </section>
    );
}
