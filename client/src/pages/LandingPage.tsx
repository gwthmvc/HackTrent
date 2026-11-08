import { Link } from 'react-router';
import '../styles/LandingPage.css';

export default function LandingPage() {
    return (
        <>
            <title>SmartMove Ontario | A better day out starts here</title>
            <div className="landing-page">
                <a className="landing-skip-link" href="#landing-main">Skip to main content</a>

                <header className="landing-header">
                    <Link className="landing-brand" to="/" aria-label="SmartMove Ontario home">
                        <span className="landing-brand-mark" aria-hidden="true"><span /><span /></span>
                        <span>SmartMove <small>Ontario</small></span>
                    </Link>
                    <nav aria-label="Main navigation">
                        <a href="#how-it-works">How it works</a>
                        <a href="#data">Our approach</a>
                        <Link to="/login">Log in</Link>
                        <Link className="landing-nav-cta" to="/register">Get started</Link>
                    </nav>
                </header>

                <main id="landing-main">
                    <section className="landing-hero" aria-labelledby="landing-hero-heading">
                        <div className="landing-hero-copy">
                            <p className="landing-eyebrow">Explore Ontario, your way</p>
                            <h1 id="landing-hero-heading">A better day out starts with <em>one idea.</em></h1>
                            <p className="landing-hero-description">
                                Describe the experience you want in your own words. SmartMove is designed to turn that request into a practical, source-aware outing plan.
                            </p>
                            <div className="landing-actions">
                                <Link className="landing-primary-action" to="/register">
                                    Start planning <span aria-hidden="true">→</span>
                                </Link>
                                <Link className="landing-secondary-action" to="/login">I already have an account</Link>
                            </div>
                            <p className="landing-trust-note"><span aria-hidden="true">●</span> Missing or unverified details stay clearly marked as unavailable.</p>
                        </div>

                        <div className="landing-planner-preview" aria-label="Illustration of the SmartMove planning flow">
                            <div className="preview-window-bar"><span /><span /><span /><strong>SmartMove planner</strong></div>
                            <div className="preview-prompt">
                                <span aria-hidden="true">✦</span>
                                <p>I&apos;d like an affordable family day in Kingston using public transit.</p>
                            </div>
                            <div className="preview-flow">
                                <div><span>01</span><p><strong>Your request</strong><small>One natural-language prompt</small></p></div>
                                <div><span>02</span><p><strong>Verified options</strong><small>Sources and freshness attached</small></p></div>
                                <div><span>03</span><p><strong>Your day plan</strong><small>Itinerary, context, and map</small></p></div>
                            </div>
                            <div className="preview-corner" aria-hidden="true" />
                        </div>
                    </section>

                    <section id="how-it-works" className="landing-steps" aria-labelledby="steps-heading">
                        <div className="landing-section-heading">
                            <p className="landing-eyebrow">From thought to day trip</p>
                            <h2 id="steps-heading">Less form-filling. More possibility.</h2>
                            <p>SmartMove keeps the planning experience focused on the outcome you want.</p>
                        </div>
                        <div className="landing-step-grid">
                            <article>
                                <span>01</span>
                                <h3>Describe your day</h3>
                                <p>Share the place, people, budget, timing, transport, or mood that matters to you.</p>
                            </article>
                            <article>
                                <span>02</span>
                                <h3>Ground the options</h3>
                                <p>The planned backend combines returned events and transit observations without hiding missing coverage.</p>
                            </article>
                            <article>
                                <span>03</span>
                                <h3>Review one clear plan</h3>
                                <p>See the returned itinerary, costs, freshness, safety context, and verified locations together.</p>
                            </article>
                        </div>
                    </section>

                    <section id="data" className="landing-data" aria-labelledby="data-heading">
                        <div>
                            <p className="landing-eyebrow">Designed for transparency</p>
                            <h2 id="data-heading">Useful when verified. Honest when unavailable.</h2>
                            <p>
                                SmartMove&apos;s interface is built to show where each returned detail came from, how fresh it is, and where coverage ends.
                            </p>
                            <Link to="/register">Create your account <span aria-hidden="true">→</span></Link>
                        </div>
                        <div className="landing-data-cards">
                            <article><span aria-hidden="true">↔</span><div><h3>Transit observations</h3><p>Vehicle timestamps and freshness when returned by the backend.</p></div></article>
                            <article><span aria-hidden="true">★</span><div><h3>Events & attractions</h3><p>Sourced listings and prices only when records are available.</p></div></article>
                            <article><span aria-hidden="true">◎</span><div><h3>Public context</h3><p>Dated incident information with geographic limitations.</p></div></article>
                        </div>
                    </section>

                    <section className="landing-final-cta" aria-labelledby="final-cta-heading">
                        <p className="landing-eyebrow">Your next Ontario day out</p>
                        <h2 id="final-cta-heading">Start with what sounds fun.</h2>
                        <p>SmartMove will handle the structure when the connected planning data is ready.</p>
                        <Link to="/register">Get started <span aria-hidden="true">→</span></Link>
                    </section>
                </main>

                <footer className="landing-footer">
                    <Link className="landing-brand" to="/" aria-label="SmartMove Ontario home">
                        <span className="landing-brand-mark" aria-hidden="true"><span /><span /></span>
                        <span>SmartMove <small>Ontario</small></span>
                    </Link>
                    <p>Built for thoughtful Ontario exploration.</p>
                    <div><Link to="/login">Log in</Link><Link to="/register">Get started</Link></div>
                </footer>
            </div>
        </>
    );
}
