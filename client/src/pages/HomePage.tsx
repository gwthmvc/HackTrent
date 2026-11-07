import '../styles/HomePage.css'
import { useAuth0 } from '@auth0/auth0-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

export default function HomePage() {
    const { logout } = useAuth0();
    const navigate = useNavigate();
    const [budget, setBudget] = useState(40);

    const handleLogout = () => {
        void logout({
            logoutParams: {
                returnTo: window.location.origin,
            },
        });
    };

    const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        navigate('/dashboard');
    };

    return (
        <>
            <title>Plan a trip | HackTrent</title>

            <div className="home-page">
                <header className="home-header">
                    <Link className="home-brand" to="/home" aria-label="HackTrent home">
                        HackTrent
                    </Link>
                    <nav aria-label="Main navigation">
                        <Link to="/home" aria-current="page">Plan a trip</Link>
                        <Link to="/dashboard">Dashboard</Link>
                        <button type="button" onClick={handleLogout}>Log out</button>
                    </nav>
                </header>

                <main className="home-content">
                    <section className="planner-card" aria-labelledby="planner-heading">
                        <div className="planner-heading">
                            <div>
                                <p className="home-eyebrow">SmartMove</p>
                                <h1 id="planner-heading">Plan your next outing</h1>
                                <p className="planner-intro">
                                    Tell us what you have in mind and we&apos;ll help you find
                                    something worth exploring.
                                </p>
                            </div>
                            <span className="planner-badge">Demo</span>
                        </div>

                        <form className="planner-form" onSubmit={handleSubmit}>
                            <div className="prompt-field">
                                <label htmlFor="trip-prompt">What would you like to do?</label>
                                <textarea
                                    id="trip-prompt"
                                    name="tripPrompt"
                                    placeholder="I'd like to take my daughter somewhere fun this Saturday."
                                    rows={3}
                                />
                            </div>

                            <fieldset>
                                <legend>Trip preferences</legend>
                                <div className="planner-fields">
                                    <div className="planner-field planner-field-wide">
                                        <label htmlFor="trip-location">Trip location</label>
                                        <input
                                            id="trip-location"
                                            name="tripLocation"
                                            type="text"
                                            placeholder="Kingston, Ontario"
                                            required
                                        />
                                    </div>

                                    <div className="planner-field">
                                        <label htmlFor="trip-date">Date</label>
                                        <input id="trip-date" name="date" type="date" required />
                                    </div>

                                    <div className="planner-field">
                                        <label htmlFor="departure-time">Departure time</label>
                                        <input
                                            id="departure-time"
                                            name="departureTime"
                                            type="time"
                                            required
                                        />
                                    </div>

                                    <div className="planner-field">
                                        <label htmlFor="return-time">Home by</label>
                                        <input
                                            id="return-time"
                                            name="returnTime"
                                            type="time"
                                            required
                                        />
                                    </div>

                                    <div className="planner-field planner-field-wide">
                                        <label htmlFor="interests">Interests</label>
                                        <select id="interests" name="interests" defaultValue="family">
                                            <option value="family">Anything family-friendly</option>
                                            <option value="arts">Arts and culture</option>
                                            <option value="outdoors">Outdoors and nature</option>
                                            <option value="food">Food and local experiences</option>
                                            <option value="sports">Sports and recreation</option>
                                        </select>
                                    </div>
                                </div>
                            </fieldset>

                            <div className="budget-field">
                                <div className="budget-label">
                                    <label htmlFor="budget">Maximum budget (CAD, including transportation)</label>
                                    <output htmlFor="budget">${budget}</output>
                                </div>
                                <input
                                    id="budget"
                                    name="budget"
                                    type="range"
                                    min="0"
                                    max="200"
                                    step="5"
                                    value={budget}
                                    onChange={(event) => setBudget(Number(event.target.value))}
                                />
                            </div>

                            <button className="planner-submit" type="submit">
                                Find outings <span aria-hidden="true">→</span>
                            </button>
                        </form>

                        <p className="planner-note">
                            Your preferences will be used to build a personalized itinerary.
                        </p>
                    </section>
                </main>
            </div>
        </>
    )
}
