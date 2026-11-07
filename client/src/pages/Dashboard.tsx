import '../styles/Dashboard.css'
import { useAuth0 } from '@auth0/auth0-react'
import { Link, useLocation } from 'react-router'
import type { TripPreferences } from '../types/trip'

interface DashboardLocationState {
    preferences?: TripPreferences;
}

export default function Dashboard() {
    const { logout } = useAuth0();
    const location = useLocation();
    const preferences = (location.state as DashboardLocationState | null)?.preferences;

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
            <h1>Dashboard</h1>
            {preferences ? (
                <section className="trip-summary" aria-labelledby="trip-summary-heading">
                    <p className="dashboard-eyebrow">Your trip request</p>
                    <h2 id="trip-summary-heading">{preferences.location}</h2>
                    {preferences.prompt && <p className="trip-prompt">&ldquo;{preferences.prompt}&rdquo;</p>}
                    <dl className="trip-details">
                        <div>
                            <dt>Date</dt>
                            <dd>{preferences.date}</dd>
                        </div>
                        <div>
                            <dt>Time</dt>
                            <dd>{preferences.departureTime} to {preferences.returnTime}</dd>
                        </div>
                        <div>
                            <dt>Interests</dt>
                            <dd>{preferences.interests}</dd>
                        </div>
                        <div>
                            <dt>Budget</dt>
                            <dd>${preferences.budget} CAD</dd>
                        </div>
                    </dl>
                    <p className="dashboard-placeholder">
                        Your itinerary, events, and transit options will appear here.
                    </p>
                </section>
            ) : (
                <section className="trip-summary" aria-labelledby="empty-dashboard-heading">
                    <p className="dashboard-eyebrow">No trip selected</p>
                    <h2 id="empty-dashboard-heading">Start planning an outing</h2>
                    <p className="dashboard-placeholder">
                        Submit your trip preferences to see them here.
                    </p>
                    <Link className="dashboard-link" to="/home">Plan a trip</Link>
                </section>
            )}
            <button type="button" onClick={handleLogout}>Log out</button>
        </main>
        </>
    )
}