import { useAuth0 } from '@auth0/auth0-react';
import { Link, useLocation } from 'react-router';
import EventsExplorer from '../components/EventsExplorer';
import OutingResults from '../components/OutingResults';
import PlacesExplorer from '../components/PlacesExplorer';
import { DashboardMapProvider, SharedDashboardLayout } from '../components/SharedDashboardMap';
import type { DashboardLocationState } from '../types/navigation';
import type { TransitContextResponse } from '../types/transit';
import '../styles/Dashboard.css';

const PREVIEW_SECTIONS = [
    {
        number: '01',
        title: 'Suggested itinerary',
        description: 'Timed stops and verified costs will appear after the planning endpoint returns a valid itinerary.',
    },
    {
        number: '02',
        title: 'Transit recommendations',
        description: 'Available routes, observation timestamps, and freshness details will be shown from returned transit records.',
    },
    {
        number: '03',
        title: 'Events & attractions',
        description: 'Only sourced events and activity records will be displayed here—never invented listings.',
    },
    {
        number: '04',
        title: 'Safety context',
        description: 'Relevant public incident records will include dates, coverage, and geographic limitations when available.',
    },
];

function formatTransitTime(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('en-CA');
}

function TransitDataStatus({
    context,
    error,
}: {
    context?: TransitContextResponse;
    error?: string;
}) {
    if (!context) {
        return (
            <aside className="transit-data-status unavailable" role="status">
                <div>
                    <p className="dashboard-eyebrow">TigerData transit observations</p>
                    <strong>Verified transit data unavailable</strong>
                </div>
                <p>{error ?? 'No supported transit observations were returned.'}</p>
            </aside>
        );
    }

    const currentCount = context.vehicles.filter(
        (vehicle) => vehicle.freshness.status === 'current',
    ).length;
    const staleCount = context.vehicles.length - currentCount;
    const agencyName = context.agencyId === 'durham'
        ? 'Durham Region Transit'
        : 'Kingston Transit';

    return (
        <aside className={`transit-data-status ${context.status}`} role="status">
            <div>
                <p className="dashboard-eyebrow">TigerData transit observations</p>
                <strong>
                    {context.status === 'stale'
                        ? 'Historical observations — not live'
                        : context.status === 'mixed'
                            ? 'Mixed observation freshness'
                            : 'Current vehicle observations'}
                </strong>
            </div>
            <p>
                {agencyName}: {context.vehicles.length} verified position{context.vehicles.length === 1 ? '' : 's'}.
                {' '}{currentCount} current, {staleCount} stale. Latest observation{' '}
                {formatTransitTime(context.latestObservationAt)}. These are vehicle observations only;
                no route directions or arrival estimates are inferred.
            </p>
        </aside>
    );
}

export default function Dashboard() {
    const { logout } = useAuth0();
    const location = useLocation();
    const state = location.state as DashboardLocationState | null;
    const startingPoint = state?.startingPoint;

    const handleLogout = () => {
        void logout({
            logoutParams: { returnTo: `${window.location.origin}/login` },
        });
    };

    return (
        <>
            <title>Your outing | SmartMove Ontario</title>
            <div className="dashboard-page">
                <a className="dashboard-skip-link" href="#dashboard-content">Skip to outing details</a>
                <header className="dashboard-header">
                    <Link className="dashboard-brand" to="/home" aria-label="SmartMove Ontario home">
                        <span className="dashboard-brand-mark" aria-hidden="true"><span /><span /></span>
                        <span>SmartMove <small>Ontario</small></span>
                    </Link>
                    <nav aria-label="Dashboard navigation">
                        <Link to="/home">New outing</Link>
                        <button type="button" onClick={handleLogout}>Log out</button>
                    </nav>
                </header>

                <DashboardMapProvider>
                    <main id="dashboard-content" className="dashboard-content">
                        {!state?.request ? (
                            <SharedDashboardLayout>
                                <div className="dashboard-empty">
                                    <p className="dashboard-eyebrow">Your outing dashboard</p>
                                    <h1 id="dashboard-empty-heading">Start with one good question.</h1>
                                    <p>Describe the day you want, and SmartMove will bring verified places into this live Ontario map.</p>
                                    <Link to="/home">Plan an outing <span aria-hidden="true">→</span></Link>
                                </div>
                            </SharedDashboardLayout>
                        ) : state.plan ? (
                            <>
                                <div className="dashboard-request">
                                    <div>
                                        <p className="dashboard-eyebrow">Your original request</p>
                                        <p>&ldquo;{state.request}&rdquo;</p>
                                        <p className="dashboard-starting-location">
                                            <span aria-hidden="true">●</span>
                                            Starting at {state.startingLocation}
                                            {state.startingLocationSource === 'prompt' && <small>From prompt</small>}
                                        </p>
                                    </div>
                                    <Link to="/home">Edit request</Link>
                                </div>
                                <TransitDataStatus context={state.transitContext} error={state.transitError} />
                                <SharedDashboardLayout
                                    startingPoint={startingPoint}
                                    transitVehicles={state.transitContext?.vehicles}
                                >
                                    <OutingResults
                                        plan={state.plan}
                                    />
                                    <EventsExplorer
                                        context={state.eventsContext}
                                        error={state.eventsError}
                                    />
                                    <PlacesExplorer
                                        context={state.placesContext}
                                        error={state.placesError}
                                    />
                                </SharedDashboardLayout>
                            </>
                        ) : (
                            <section className="dashboard-preview" aria-labelledby="preview-heading">
                                <div className="preview-heading">
                                    <div>
                                        <p className="dashboard-eyebrow">Integration preview</p>
                                        <h1 id="preview-heading">Your outing workspace is ready.</h1>
                                        <p>
                                            The planning endpoint has not returned a verified itinerary, so no live recommendations are shown.
                                        </p>
                                    </div>
                                    <span>Preview — not live data</span>
                                </div>

                                <div className="dashboard-request">
                                    <div>
                                        <p className="dashboard-eyebrow">Request prepared for planning</p>
                                        <p>&ldquo;{state.request}&rdquo;</p>
                                        <p className="dashboard-starting-location">
                                            <span aria-hidden="true">●</span>
                                            Starting at {state.startingLocation}
                                            {state.startingLocationSource === 'prompt' && <small>From prompt</small>}
                                        </p>
                                    </div>
                                    <Link to="/home">Edit request</Link>
                                </div>

                                <TransitDataStatus context={state.transitContext} error={state.transitError} />

                                <SharedDashboardLayout
                                    startingPoint={startingPoint}
                                    transitVehicles={state.transitContext?.vehicles}
                                >
                                    <EventsExplorer
                                        context={state.eventsContext}
                                        error={state.eventsError}
                                    />

                                    <PlacesExplorer
                                        context={state.placesContext}
                                        error={state.placesError}
                                    />

                                    <div className="preview-grid">
                                        {PREVIEW_SECTIONS.map((section) => (
                                            <article key={section.number}>
                                                <span>{section.number}</span>
                                                <div>
                                                    <h2>{section.title}</h2>
                                                    <p>{section.description}</p>
                                                    <strong>Awaiting verified backend data</strong>
                                                </div>
                                            </article>
                                        ))}
                                    </div>
                                </SharedDashboardLayout>
                            </section>
                        )}
                    </main>
                </DashboardMapProvider>
            </div>
        </>
    );
}
