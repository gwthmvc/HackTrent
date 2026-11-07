import '../styles/HomePage.css'
import { useAuth0 } from '@auth0/auth0-react'
import { Link } from 'react-router'


export default function HomePage() {
    const { logout } = useAuth0();

    const handleLogout = () => {
        void logout({
            logoutParams: {
                returnTo: window.location.origin,
            },
        });
    };

    return (
        <>
            <title>Home | HackTrent</title>

            <div className="home-page">
                <header className="home-header">
                    <Link className="home-brand" to="/home" aria-label="HackTrent home">
                        HackTrent
                    </Link>
                    <nav aria-label="Dashboard navigation">
                        <Link to="/home" aria-current="page">Home</Link>
                        <Link to="/dashboard">Dashboard</Link>
                        <button type="button" onClick={handleLogout}>Log out</button>
                    </nav>
                </header>

                <main className="home-content">
                    <section className="home-intro" aria-labelledby="home-heading">
                        <div>
                            <p className="home-eyebrow">Your community view</p>
                            <h1 id="home-heading">Good morning, explorer.</h1>
                            <p>
                                Ask questions, discover what is happening nearby, and
                                find your next place to explore.
                            </p>
                        </div>
                        <div className="home-date" aria-label="Current location">
                            <span className="home-date-marker" aria-hidden="true">●</span>
                            <span>Peterborough, Ontario</span>
                        </div>
                    </section>

                    <section className="home-dashboard-grid" aria-label="Home dashboard">
                        <article className="home-card map-card">
                            <div className="card-heading">
                                <div>
                                    <p className="home-eyebrow">Explore the area</p>
                                    <h2>Peterborough map</h2>
                                </div>
                                <span className="card-status">Live view</span>
                            </div>
                            <div className="map-frame">
                                <iframe
                                    title="Map of Peterborough, Ontario"
                                    src="https://www.openstreetmap.org/export/embed.html?bbox=-78.40%2C44.27%2C-78.25%2C44.35&layer=mapnik&marker=44.3091%2C-78.3197"
                                    loading="lazy"
                                />
                            </div>
                            <div className="map-footer">
                                <span>Centered on Peterborough</span>
                                <a
                                    href="https://www.openstreetmap.org/?mlat=44.3091&mlon=-78.3197#map=13/44.3091/-78.3197"
                                    target="_blank"
                                    rel="noreferrer"
                                >
                                    Open larger map <span aria-hidden="true">↗</span>
                                </a>
                            </div>
                        </article>

                        <article className="home-card chat-card">
                            <div className="card-heading">
                                <div>
                                    <p className="home-eyebrow">Ask HackTrent</p>
                                    <h2>How can we help?</h2>
                                </div>
                                <span className="chat-spark" aria-hidden="true">✦</span>
                            </div>
                            <div className="chat-empty-state">
                                <div className="chat-icon" aria-hidden="true">✦</div>
                                <p className="chat-placeholder">
                                    Your local guide is almost ready.
                                </p>
                                <p className="chat-helper">
                                    Gemini-powered answers and recommendations will
                                    appear here soon.
                                </p>
                            </div>
                            <form className="chat-form" onSubmit={(event) => event.preventDefault()}>
                                <label className="sr-only" htmlFor="chat-question">
                                    Ask a question
                                </label>
                                <input
                                    id="chat-question"
                                    type="text"
                                    placeholder="Ask about Peterborough..."
                                    disabled
                                />
                                <button type="submit" disabled aria-label="Send question">
                                    <span aria-hidden="true">→</span>
                                </button>
                            </form>
                            <p className="chat-coming-soon">Chat functionality coming soon</p>
                        </article>
                    </section>
                </main>
            </div>
        </>
    )
}
