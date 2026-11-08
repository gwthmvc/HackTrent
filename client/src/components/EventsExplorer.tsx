import { useCallback, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useDashboardMapLayer } from './useDashboardMapLayer';
import type { EventPriceRange, EventSearchResponse, TicketmasterEvent } from '../types/events';
import type { VerifiedLocation } from '../types/outing';

type EventsExplorerProps = {
    context?: EventSearchResponse;
    error?: string;
};

const STATUS_LABELS: Record<string, string> = {
    offsale: 'Not currently on sale',
    postponed: 'Postponed',
    rescheduled: 'Rescheduled',
};

const NO_ROUTES: [] = [];

function locationId(event: TicketmasterEvent): string {
    return `event-${event.id}`;
}

function formatEventDate(event: TicketmasterEvent): string {
    const [year, month, day] = event.startLocalDate.split('-').map(Number);
    const [hour, minute] = (event.startLocalTime ?? '00:00').split(':').map(Number);
    // Ticketmaster's local date/time is the venue's wall-clock time; format it without timezone shifts.
    const parsed = new Date(year, month - 1, day, hour, minute);
    if (Number.isNaN(parsed.getTime())) return event.startLocalDate;
    const datePart = parsed.toLocaleDateString('en-CA', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
    return event.startLocalTime
        ? `${datePart} · ${parsed.toLocaleTimeString('en-CA', { hour: 'numeric', minute: '2-digit' })}`
        : `${datePart} · Time to be announced`;
}

function formatPrice(price: EventPriceRange): string {
    const format = (amount: number) => {
        try {
            return new Intl.NumberFormat('en-CA', { style: 'currency', currency: price.currency }).format(amount);
        } catch {
            return `${amount} ${price.currency}`;
        }
    };
    if (price.min !== null && price.max !== null && price.min !== price.max) {
        return `${format(price.min)} – ${format(price.max)}`;
    }
    const single = price.min ?? price.max;
    return single === null ? 'Price not listed' : format(single);
}

function venueAddress(event: TicketmasterEvent): string | undefined {
    const parts = [event.venue.address, event.venue.city, event.venue.province].filter(Boolean);
    return parts.length > 0 ? parts.join(', ') : undefined;
}

function safeHttpsUrl(url: string | null): string | undefined {
    if (!url) return undefined;
    try {
        return new URL(url).protocol === 'https:' ? url : undefined;
    } catch {
        return undefined;
    }
}

function missingCoordinatesNote(event: TicketmasterEvent): string {
    return event.venue.coordinateStatus === 'outside_search_area'
        ? 'Venue coordinates fall outside the search area — no marker shown'
        : 'Venue coordinates not provided by Ticketmaster — no marker shown';
}

export default function EventsExplorer({ context, error }: EventsExplorerProps) {
    const events = useMemo(() => context?.events ?? [], [context]);
    const [selectedEventId, setSelectedEventId] = useState<string>();
    const cardRefs = useRef<Map<string, HTMLElement>>(new Map());

    const { locations, pinNumbers } = useMemo(() => {
        const mapped: VerifiedLocation[] = [];
        const numbers = new Map<string, number>();
        events.forEach((event) => {
            if (event.venue.coordinateStatus !== 'verified' || event.venue.latitude === null || event.venue.longitude === null) {
                return;
            }
            const id = locationId(event);
            mapped.push({
                id,
                name: event.name,
                address: [event.venue.name, venueAddress(event)].filter(Boolean).join(' — '),
                latitude: event.venue.latitude,
                longitude: event.venue.longitude,
                source: { name: 'Ticketmaster', url: safeHttpsUrl(event.url) },
            });
            numbers.set(id, mapped.length);
        });
        return { locations: mapped, pinNumbers: numbers };
    }, [events]);

    const selectFromMap = useCallback((id: string) => {
        const event = events.find((candidate) => locationId(candidate) === id);
        if (!event) return;
        setSelectedEventId(event.id);
        cardRefs.current.get(event.id)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, [events]);

    const mapLayer = useDashboardMapLayer({
        id: 'events',
        label: 'Events',
        locations,
        routes: NO_ROUTES,
        stopNumbers: pinNumbers,
        onSelectLocation: selectFromMap,
        enabled: Boolean(context),
    });

    const selectCard = (event: TicketmasterEvent) => {
        setSelectedEventId(event.id);
        const id = locationId(event);
        if (pinNumbers.has(id)) mapLayer.selectLocation(id);
    };

    const handleCardKeyDown = (keyEvent: KeyboardEvent<HTMLElement>, event: TicketmasterEvent) => {
        if (keyEvent.target !== keyEvent.currentTarget) return;
        if (keyEvent.key === 'Enter' || keyEvent.key === ' ') {
            keyEvent.preventDefault();
            selectCard(event);
        }
    };

    if (!context) {
        return (
            <aside className="transit-data-status unavailable events-status" role="status">
                <div>
                    <p className="dashboard-eyebrow">Ticketmaster events</p>
                    <strong>Event listings unavailable</strong>
                </div>
                <p>{error ?? 'No event search was performed.'}</p>
            </aside>
        );
    }

    const unmappedCount = events.length - locations.length;

    return (
        <section className="events-explorer-section" aria-labelledby="events-heading">
            <div className="outing-explorer cards-only">
                <section className="explorer-list-panel" aria-labelledby="events-heading">
                    <div className="explorer-list-header">
                        <div>
                            <p className="home-eyebrow">Ticketmaster events · {context.areaName}</p>
                            <h3 id="events-heading">Events {context.window.description}</h3>
                        </div>
                        <span>{events.length} shown</span>
                    </div>
                    <p className="result-meta events-summary">
                        {context.classifications.length > 0 && <>Matching {context.classifications.join(', ')}. </>}
                        {unmappedCount > 0 && <>{unmappedCount} without verified map coordinates. </>}
                        {!context.transitCoverage && <>TigerData transit coverage is not available for this area.</>}
                    </p>
                    <div className="result-location-list">
                        {events.map((event) => {
                            const id = locationId(event);
                            const pinNumber = pinNumbers.get(id);
                            const selected = event.id === selectedEventId;
                            const url = safeHttpsUrl(event.url);
                            const address = venueAddress(event);
                            const statusLabel = event.status ? STATUS_LABELS[event.status] : undefined;
                            return (
                                <article
                                    key={event.id}
                                    ref={(element) => {
                                        if (element) cardRefs.current.set(event.id, element);
                                        else cardRefs.current.delete(event.id);
                                    }}
                                    className={`result-location-card event-card${selected ? ' selected' : ''}${pinNumber ? '' : ' unmapped'}`}
                                    tabIndex={0}
                                    role="button"
                                    aria-pressed={selected}
                                    aria-label={`${event.name}${pinNumber ? `, map pin ${pinNumber}` : ''}`}
                                    onClick={() => selectCard(event)}
                                    onKeyDown={(keyEvent) => handleCardKeyDown(keyEvent, event)}
                                    onMouseEnter={() => mapLayer.highlightLocation(pinNumber ? id : undefined)}
                                    onMouseLeave={() => mapLayer.highlightLocation()}
                                    onFocus={() => mapLayer.highlightLocation(pinNumber ? id : undefined)}
                                    onBlur={() => mapLayer.highlightLocation()}
                                >
                                    <div className="location-card-number">{pinNumber ? String(pinNumber).padStart(2, '0') : '•'}</div>
                                    <div>
                                        {event.imageUrl && (
                                            <img className="event-card-image" src={event.imageUrl} alt="" loading="lazy" referrerPolicy="no-referrer" />
                                        )}
                                        <div className="result-card-heading">
                                            <div>
                                                <p className="result-kicker">{event.classification ?? 'Event'}</p>
                                                <h4>{event.name}</h4>
                                            </div>
                                            {event.priceRange
                                                ? <strong>{formatPrice(event.priceRange)}</strong>
                                                : <span className="result-unavailable-inline">Price not listed</span>}
                                        </div>
                                        <p className="result-meta">{formatEventDate(event)}</p>
                                        <p className="result-meta">
                                            {event.venue.name}{address && ` — ${address}`}
                                        </p>
                                        {statusLabel && <p className="event-status-note">{statusLabel}</p>}
                                        {!pinNumber && <p className="map-link-unavailable">{missingCoordinatesNote(event)}</p>}
                                        <p className="result-source">
                                            Source:{' '}
                                            {url
                                                ? <a href={url} target="_blank" rel="noreferrer" onClick={(clickEvent) => clickEvent.stopPropagation()}>View on Ticketmaster</a>
                                                : 'Ticketmaster (official link unavailable)'}
                                        </p>
                                    </div>
                                </article>
                            );
                        })}
                        {events.length === 0 && (
                            <p className="unavailable-note">
                                Ticketmaster returned no events in {context.areaName} for {context.window.description}.
                                Try a different date or broader interests.
                            </p>
                        )}
                    </div>
                </section>

            </div>
        </section>
    );
}
