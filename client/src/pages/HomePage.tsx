import { useAuth0 } from '@auth0/auth0-react';
import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import {
    DEFAULT_STARTING_LOCATION,
    getKnownStartingPoint,
    STARTING_LOCATION_SUGGESTIONS,
} from '../config/startingLocations';
import { auth0ApiScope, auth0Audience, isAuth0ApiConfigured } from '../auth/config';
import { generateOuting, isOutingPlannerConfigured } from '../services/api';
import { searchEvents } from '../services/eventsApi';
import { fetchTransitContext, isTransitApiConfigured } from '../services/transitApi';
import type { DashboardLocationState } from '../types/navigation';
import { extractPromptStartingLocation } from '../utils/startingLocation';
import '../styles/HomePage.css';

const EXAMPLE_REQUEST = "I want to take my daughter somewhere fun in Kingston this Saturday. My budget is $60 and we'd like to use public transit.";

const EXAMPLE_PROMPTS = [
    'A low-cost art day in Toronto for two',
    'An accessible outdoor afternoon near Kingston',
    'A family day trip using public transit',
];

function SparkleIcon() {
    return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 2.5c.5 5.4 3.1 8 8.5 8.5-5.4.5-8 3.1-8.5 8.5-.5-5.4-3.1-8-8.5-8.5 5.4-.5 8-3.1 8.5-8.5Z" />
            <path d="M19 2c.2 2 1.2 3 3 3-1.8.2-2.8 1.2-3 3-.2-1.8-1.2-2.8-3-3 1.8-.2 2.8-1.2 3-3Z" />
        </svg>
    );
}

export default function HomePage() {
    const { getAccessTokenSilently, logout } = useAuth0();
    const navigate = useNavigate();
    const [message, setMessage] = useState('');
    const [startingLocation, setStartingLocation] = useState(DEFAULT_STARTING_LOCATION);
    const [departureDate, setDepartureDate] = useState('');
    const [departureTime, setDepartureTime] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const errorRef = useRef<HTMLParagraphElement>(null);
    const startingLocationRef = useRef<HTMLInputElement>(null);
    const promptStartingLocation = useMemo(
        () => extractPromptStartingLocation(message),
        [message],
    );

    useEffect(() => {
        if (error) {
            errorRef.current?.focus();
        }
    }, [error]);

    const handleLogout = () => {
        void logout({
            logoutParams: { returnTo: window.location.origin },
        });
    };

    const submitRequest = async () => {
        const request = message.trim();
        const fieldStartingLocation = startingLocation.trim();
        const effectiveStartingLocation = promptStartingLocation ?? fieldStartingLocation;

        if (!request) {
            setError('Tell us what kind of outing you would like to plan.');
            textareaRef.current?.focus();
            return;
        }

        if (!effectiveStartingLocation) {
            setError('Enter a starting location or specify one clearly in your outing request.');
            startingLocationRef.current?.focus();
            return;
        }

        setError(null);
        const startingLocationSource = promptStartingLocation ? 'prompt' : 'field';
        const startingPoint = getKnownStartingPoint(effectiveStartingLocation);

        setIsLoading(true);
        try {
            let accessToken: string | undefined;
            let transitContext: DashboardLocationState['transitContext'];
            let transitError: string | undefined;
            let eventsContext: DashboardLocationState['eventsContext'];
            let eventsError: string | undefined;
            let placesError: string | undefined;

            if (!isTransitApiConfigured) {
                transitError = 'Transit API URL is not configured.';
                eventsError = 'SmartMove API URL is not configured.';
            } else if (!isAuth0ApiConfigured || !auth0Audience) {
                transitError = 'Auth0 API audience is not configured for secure transit access.';
                eventsError = 'Auth0 API audience is not configured for secure event search.';
            } else {
                try {
                    accessToken = await getAccessTokenSilently({
                        authorizationParams: {
                            audience: auth0Audience,
                            scope: auth0ApiScope,
                        },
                    });
                    if (!accessToken) {
                        throw new Error('Auth0 did not return an API access token.');
                    }
                } catch (tokenError) {
                    transitError = tokenError instanceof Error
                        ? tokenError.message
                        : 'Verified transit observations are unavailable.';
                    eventsError = transitError;
                }

                if (accessToken) {
                    const searchRequest = {
                        startingLocation: effectiveStartingLocation,
                        outingRequest: request,
                    };
                    const [transitResult, eventsResult] = await Promise.allSettled([
                        fetchTransitContext(searchRequest, accessToken),
                        searchEvents(searchRequest, accessToken),
                    ]);
                    if (transitResult.status === 'fulfilled') {
                        transitContext = transitResult.value;
                    } else {
                        transitError = transitResult.reason instanceof Error
                            ? transitResult.reason.message
                            : 'Verified transit observations are unavailable.';
                    }
                    if (eventsResult.status === 'fulfilled') {
                        eventsContext = eventsResult.value;
                    } else {
                        eventsError = eventsResult.reason instanceof Error
                            ? eventsResult.reason.message
                            : 'Ticketmaster events are unavailable.';
                    }

                }
            }

            if (!isOutingPlannerConfigured) {
                throw new Error(
                    'Trip planning is unavailable because the backend generation endpoint is not configured.',
                );
            }

            if (!accessToken) {
                throw new Error('Auth0 API audience is not configured for secure trip planning.');
            }

            const plan = await generateOuting({
                outingRequest: request,
                startingLocation: effectiveStartingLocation,
                ...(departureDate && departureTime
                    ? { date: departureDate, time: departureTime }
                    : {}),
            }, accessToken);
            const placesContext = plan.places ?? undefined;
            if (plan.places === null) {
                const placeStatus = plan.sourceStatus.places;
                placesError = [placeStatus.code, placeStatus.reason]
                    .filter((value): value is string => Boolean(value))
                    .join(': ') || 'OpenStreetMap places are unavailable.';
            }
            const state: DashboardLocationState = {
                request,
                startingLocation: effectiveStartingLocation,
                startingLocationSource,
                startingPoint,
                transitContext,
                transitError,
                eventsContext,
                eventsError,
                placesContext,
                placesError,
                plan,
            };
            navigate('/dashboard', { state });
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : 'We could not generate your outing. Please try again.',
            );
        } finally {
            setIsLoading(false);
        }
    };

    const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        void submitRequest();
    };

    const handleTextareaKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
            event.preventDefault();
            void submitRequest();
        }
    };

    return (
        <>
            <title>Plan an outing | SmartMove Ontario</title>
            <div className="home-page">
                <a className="home-skip-link" href="#planner">Skip to trip planner</a>
                <header className="home-header">
                    <Link className="home-brand" to="/home" aria-label="SmartMove Ontario home">
                        <span className="brand-mark" aria-hidden="true"><span /><span /></span>
                        <span>SmartMove <small>Ontario</small></span>
                    </Link>
                    <nav aria-label="Account navigation">
                        <Link to="/dashboard" className="home-nav-link">Dashboard</Link>
                        <button type="button" onClick={handleLogout}>Log out</button>
                    </nav>
                </header>

                <main className="home-content" id="planner">
                    <section className="planner-hero" aria-labelledby="home-heading">
                        <div className="hero-orbit hero-orbit-one" aria-hidden="true" />
                        <div className="hero-orbit hero-orbit-two" aria-hidden="true" />
                        <p className="home-eyebrow">One request. A whole day out.</p>
                        <h1 id="home-heading">Where will you <em>wander?</em></h1>
                        <p className="home-subtitle">
                            Tell us what you&apos;d like to do. We&apos;ll prepare your request for a grounded Ontario outing plan.
                        </p>

                        <form className="ai-planner" onSubmit={handleSubmit} noValidate aria-busy={isLoading}>
                            <div className="starting-location-field">
                                <label htmlFor="starting-location">Starting location</label>
                                <div className="starting-location-input">
                                    <span aria-hidden="true">●</span>
                                    <input
                                        ref={startingLocationRef}
                                        id="starting-location"
                                        list="starting-location-options"
                                        value={startingLocation}
                                        onChange={(event) => {
                                            setStartingLocation(event.target.value);
                                            if (error) setError(null);
                                        }}
                                        disabled={isLoading}
                                        autoComplete="street-address"
                                        aria-describedby="starting-location-help"
                                    />
                                    <datalist id="starting-location-options">
                                        {STARTING_LOCATION_SUGGESTIONS.map((location) => (
                                            <option key={location} value={location} />
                                        ))}
                                    </datalist>
                                </div>
                                <p id="starting-location-help">
                                    {promptStartingLocation
                                        ? <>Prompt departure detected: <strong>{promptStartingLocation}</strong>. This will override the field.</>
                                        : 'Change this address, or state a departure point clearly in your prompt.'}
                                    <span> Initial transit-data focus: Durham Region and Kingston. Availability is confirmed only from returned observations.</span>
                                </p>
                            </div>
                            <div className="planner-departure-fields">
                                <div>
                                    <label htmlFor="departure-date">Departure date <span>(optional)</span></label>
                                    <input
                                        id="departure-date"
                                        type="date"
                                        value={departureDate}
                                        onChange={(event) => setDepartureDate(event.target.value)}
                                        disabled={isLoading}
                                    />
                                </div>
                                <div>
                                    <label htmlFor="departure-time">Departure time <span>(optional)</span></label>
                                    <input
                                        id="departure-time"
                                        type="time"
                                        value={departureTime}
                                        onChange={(event) => setDepartureTime(event.target.value)}
                                        disabled={isLoading}
                                    />
                                </div>
                            </div>
                            <label htmlFor="outing-request">Describe your ideal outing</label>
                            <div className="ai-input-shell">
                                <textarea
                                    ref={textareaRef}
                                    id="outing-request"
                                    value={message}
                                    onChange={(event) => {
                                        setMessage(event.target.value);
                                        if (error) setError(null);
                                    }}
                                    onKeyDown={handleTextareaKeyDown}
                                    placeholder={EXAMPLE_REQUEST}
                                    rows={4}
                                    aria-describedby="planner-hint planner-status"
                                    aria-invalid={Boolean(error)}
                                    disabled={isLoading}
                                />
                                <button className="planner-submit" type="submit" disabled={isLoading}>
                                    <SparkleIcon />
                                    <span>{isLoading ? 'Planning…' : 'Plan my day'}</span>
                                </button>
                            </div>
                            <div className="planner-support-row">
                                <p id="planner-hint">Press Ctrl + Enter to plan</p>
                                <p
                                    id="planner-status"
                                    className={isOutingPlannerConfigured || (isTransitApiConfigured && isAuth0ApiConfigured)
                                        ? 'integration-status configured'
                                        : 'integration-status'}
                                >
                                    <span aria-hidden="true" />
                                    {isTransitApiConfigured && isAuth0ApiConfigured
                                        ? 'Secure transit endpoint configured'
                                        : isTransitApiConfigured
                                            ? 'Transit Auth0 audience required'
                                        : isOutingPlannerConfigured
                                            ? 'Planner endpoint configured'
                                            : 'Integration preview mode'}
                                </p>
                            </div>
                        </form>

                        <div className="prompt-examples" aria-label="Example outing prompts">
                            <p>Try an example</p>
                            <div>
                                {EXAMPLE_PROMPTS.map((prompt) => (
                                    <button key={prompt} type="button" onClick={() => setMessage(prompt)} disabled={isLoading}>
                                        {prompt}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {error && (
                            <p className="planner-error" role="alert" tabIndex={-1} ref={errorRef}>
                                <strong>We couldn&apos;t start that plan.</strong> {error}
                            </p>
                        )}

                        {isLoading && (
                            <div className="planner-loading" role="status" aria-live="polite">
                                <span className="loading-spark"><SparkleIcon /></span>
                                <div>
                                    <strong>Building your Ontario outing</strong>
                                    <p>Waiting for verified planning data…</p>
                                </div>
                            </div>
                        )}
                    </section>
                </main>

                <footer className="home-footer">
                    <p>SmartMove Ontario</p>
                    <p>Plan thoughtfully. Verify details before you go.</p>
                </footer>
            </div>
        </>
    );
}
