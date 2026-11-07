import { Link } from 'react-router'
import '../styles/LandingPage.css'


export default function LandingPage() {


    return (

        <>
            <title>LandingPage</title>

            <div className="landing-page">
                <a className="skip-link" href="#main-content">Skip to main content</a>

                <header className="landing-header">
                    <nav aria-label="Main navigation">
                        <Link to="/home" aria-label="Home">Home</Link>
                        <Link to="/dashboard" aria-label="Dashboard">Dashboard</Link>
                        <a href="#features">Features</a>
                        <a href="#about">About</a>
                        <Link to="/login" aria-label="Login">Login</Link>
                        <Link className="nav-signup" to="/register" aria-label="Sign up">
                            Sign up
                        </Link>
                    </nav>
                </header>


                <main id="main-content">
                    <section className="hero" aria-labelledby="hero-heading">
                        <div className="hero-content">
                            <p className="eyebrow">Welcome to Our Application</p>
                            <h1 id="hero-heading">Get where you need to go</h1>

                            <p className="hero-description">
                                Discover the features and benefits of our platform.
                            </p>

                            <div className="hero-actions">
                                {/* Register */}
                                <Link className="primary-button" to="/register" aria-label="Sign up">
                                    Get Started <span aria-hidden="true">→</span>
                                </Link>
                                {/* Login */}
                                <Link className="secondary-button" to="/login" aria-label="Login">
                                    Login <span aria-hidden="true">→</span>
                                </Link>
                            </div>
                        </div>

                        <div className="hero-art" aria-hidden="true">
                            <div className="art-shape art-shape-one" />
                            <div className="art-shape art-shape-two" />
                        </div>
                    </section>

                    <section
                        id="features"
                        className="features"
                        aria-labelledby="features-heading"
                    >
                        <p className="eyebrow">What we offer</p>
                        <h2 id="features-heading">Everything you need to get started.</h2>

                        <div className="feature-grid">
                            <article>
                                <span aria-hidden="true">01</span>
                                <h3>Simple to use</h3>
                                <p>
                                    Get started quickly with an easy-to-understand
                                    experience built around your goals.
                                </p>
                            </article>
                            <article>
                                <span aria-hidden="true">02</span>
                                <h3>Built for progress</h3>
                                <p>
                                    Keep your ideas organized and move from planning
                                    to action with confidence.
                                </p>
                            </article>
                            <article>
                                <span aria-hidden="true">03</span>
                                <h3>Made for everyone</h3>
                                <p>
                                    A welcoming space where people can connect,
                                    collaborate, and grow together.
                                </p>
                            </article>
                        </div>
                    </section>

                    <section
                        id="about"
                        className="about"
                        aria-labelledby="about-heading"
                    >
                        <p className="eyebrow">About HackTrent</p>
                        <h2 id="about-heading">A better way to move ideas forward.</h2>
                        <p>
                            This is placeholder text for the about section.
                            This will later be replaced with actual content.
                        </p>
                    </section>
                </main>
            </div>

        </>
    )
}