import '../styles/Dashboard.css'
import 'leaflet/dist/leaflet.css'
import { useAuth0 } from '@auth0/auth0-react'
import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import { Link, useLocation } from 'react-router'
import type { SuggestedPlace, TripPlan, TripPreferences } from '../types/trip'

interface DashboardLocationState {
    preferences?: TripPreferences;
}

const DEFAULT_MAP_CENTER = { lat: 44.2312, lng: -76.486 };

export default function Dashboard() {
    const { logout } = useAuth0();
    const location = useLocation();
    const preferences = (location.state as DashboardLocationState | null)?.preferences;
    const [plan, setPlan] = useState<TripPlan | null>(null);
    const [isLoading, setIsLoading] = useState(Boolean(preferences));
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'itinerary' | 'details'>('itinerary');
    const [selectedPlace, setSelectedPlace] = useState<SuggestedPlace | null>(null);

    useEffect(() => {
        if (!preferences) {
            return;
        }

        const controller = new AbortController();

        fetch('/api/trips/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(preferences),
            signal: controller.signal,
        })
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error(`Planner request failed (${response.status}).`);
                }
                return response.json() as Promise<TripPlan>;
            })
            .then((nextPlan) => setPlan(nextPlan))
            .catch((requestError: unknown) => {
                if (requestError instanceof DOMException && requestError.name === 'AbortError') {
                    return;
                }
                setError(requestError instanceof Error ? requestError.message : 'Unable to load trip results.');
            })
            .finally(() => setIsLoading(false));

        return () => controller.abort();
    }, [preferences]);

    const handlePlaceSelect = (place: SuggestedPlace) => {
        setSelectedPlace(place);
        setActiveTab('details');
    };

    const handleLogout = () => {
        void logout({
            logoutParams: {
                returnTo: window.location.origin,
            },
        });
    };

    return(

        <>
        <title>Dashboard</title>
        <main className="dashboard-page">
            <header className="dashboard-header">
                <div>
                    <p className="dashboard-eyebrow">SmartMove</p>
                    <h1>{preferences?.location || 'Kingston, Ontario'}</h1>
                </div>
                <nav aria-label="Dashboard navigation">
                    <Link to="/home">Edit trip</Link>
                    <button type="button" onClick={handleLogout}>Log out</button>
                </nav>
            </header>

            <div className="dashboard-layout">
                <section className="dashboard-panel" aria-label="Trip itinerary and details">
                    <div className="dashboard-panel-heading">
                        <div>
                            <p className="dashboard-eyebrow">Your outing</p>
                            <h2>{preferences?.date || 'Trip planner'}</h2>
                        </div>
                        <span className="dashboard-status">{plan?.source === 'live' ? 'Live results' : 'Awaiting results'}</span>
                    </div>

                    <div className="dashboard-tabs" role="tablist" aria-label="Trip information">
                        <button
                            className={activeTab === 'itinerary' ? 'active' : ''}
                            type="button"
                            role="tab"
                            aria-selected={activeTab === 'itinerary'}
                            onClick={() => setActiveTab('itinerary')}
                        >
                            Itinerary
                        </button>
                        <button
                            className={activeTab === 'details' ? 'active' : ''}
                            type="button"
                            role="tab"
                            aria-selected={activeTab === 'details'}
                            onClick={() => setActiveTab('details')}
                        >
                            Details
                        </button>
                    </div>

                    {isLoading ? (
                        <div className="dashboard-state">
                            <p className="dashboard-eyebrow">Planner</p>
                            <h3>Finding options...</h3>
                            <p className="dashboard-placeholder">Checking events and transit for your trip.</p>
                        </div>
                    ) : error ? (
                        <div className="dashboard-state" role="alert">
                            <p className="dashboard-eyebrow">Planner unavailable</p>
                            <h3>We couldn&apos;t load trip results.</h3>
                            <p className="dashboard-placeholder">{error}</p>
                            <p className="dashboard-placeholder">The backend endpoint is not connected yet.</p>
                        </div>
                    ) : activeTab === 'itinerary' ? (
                        <div className="itinerary-content">
                            {preferences?.prompt && (
                                <p className="trip-prompt">&ldquo;{preferences.prompt}&rdquo;</p>
                            )}
                            <div className="itinerary-summary">
                                <span>{preferences?.departureTime || '4:00 PM'}</span>
                                <strong>Explore Kingston</strong>
                                <span>{preferences?.returnTime || '7:00 PM'}</span>
                            </div>
                            <p className="dashboard-placeholder">
                                Select a suggestion below or click a pin on the map to learn more.
                            </p>
                            <div className="suggestion-list">
                                {plan?.places.map((place) => (
                                    <button
                                        className="suggestion-button"
                                        key={place.id}
                                        type="button"
                                        onClick={() => handlePlaceSelect(place)}
                                    >
                                        <span>
                                            <strong>{place.name}</strong>
                                            <small>{place.type} · {place.time}</small>
                                        </span>
                                        <span aria-hidden="true">→</span>
                                    </button>
                                ))}
                                {!plan?.places.length && (
                                    <p className="dashboard-placeholder">
                                        No suggested places have been returned yet.
                                    </p>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="details-content">
                            {selectedPlace ? (
                                <>
                                    <p className="dashboard-eyebrow">{selectedPlace.type}</p>
                                    <h3>{selectedPlace.name}</h3>
                                    <p>{selectedPlace.description}</p>
                                    <dl className="place-details">
                                        <div><dt>Hours</dt><dd>{selectedPlace.time}</dd></div>
                                        <div><dt>Cost</dt><dd>{selectedPlace.price}</dd></div>
                                    </dl>
                                    <button
                                        className="back-to-itinerary"
                                        type="button"
                                        onClick={() => setActiveTab('itinerary')}
                                    >
                                        Back to itinerary
                                    </button>
                                </>
                            ) : (
                                <>
                                    <p className="dashboard-eyebrow">Trip details</p>
                                    <h3>{preferences?.location || 'Kingston, Ontario'}</h3>
                                    <dl className="trip-details">
                                        <div><dt>Date</dt><dd>{preferences?.date || 'Not selected'}</dd></div>
                                        <div><dt>Time</dt><dd>{preferences?.departureTime || '4:00 PM'} to {preferences?.returnTime || '7:00 PM'}</dd></div>
                                        <div><dt>Interests</dt><dd>{preferences?.interests || 'Family-friendly'}</dd></div>
                                        <div><dt>Budget</dt><dd>${preferences?.budget ?? 40} CAD</dd></div>
                                    </dl>
                                    <p className="dashboard-placeholder">
                                        Select a map pin or itinerary suggestion to view more information.
                                    </p>
                                </>
                            )}
                        </div>
                    )}
                </section>

                <section className="map-panel" aria-label="Suggested places map">
                    <MapContainer
                        className="dashboard-map"
                        center={[plan?.mapCenter.lat ?? DEFAULT_MAP_CENTER.lat, plan?.mapCenter.lng ?? DEFAULT_MAP_CENTER.lng]}
                        zoom={13}
                        scrollWheelZoom
                    >
                        <TileLayer
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        />
                        {plan?.places.map((place) => (
                            <CircleMarker
                                key={place.id}
                                center={[place.coordinates.lat, place.coordinates.lng]}
                                pathOptions={{ color: '#b52b32', fillColor: '#d94a4f', fillOpacity: 0.9 }}
                                radius={9}
                                eventHandlers={{ click: () => handlePlaceSelect(place) }}
                            >
                                <Popup>
                                    <strong>{place.name}</strong>
                                    <br />
                                    {place.type}
                                </Popup>
                            </CircleMarker>
                        ))}
                    </MapContainer>
                    <p className="map-caption">
                        {plan?.places.length
                            ? `Suggested places near ${preferences?.location || 'your trip'}`
                            : 'Map pins will appear when the planner returns places.'}
                    </p>
                </section>
            </div>
        </main>
        </>
    )
}