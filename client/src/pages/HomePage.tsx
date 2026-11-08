import { useAuth0 } from '@auth0/auth0-react';
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Link } from 'react-router';
import { sendChatMessage, type ChatMessage } from '../services/chat';
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
    const { logout } = useAuth0();
    const [message, setMessage] = useState('');
    const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const errorRef = useRef<HTMLParagraphElement>(null);
    const [reply, setReply] = useState<string | null>(null);

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

        if (!request) {
            setError('Ask the Gemini assistant a question.');
            textareaRef.current?.focus();
            return;
        }

        setError(null);
        const userMessage: ChatMessage = {
            role: 'user',
            parts: [{ text: request }],
        };
        const updatedHistory = [...chatHistory, userMessage];

        setIsLoading(true);
        setMessage('');
        try {
            const response = await sendChatMessage(request, updatedHistory);
            setChatHistory([
                ...updatedHistory,
                { role: 'model', parts: [{ text: response }] },
            ]);
            setReply(response);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : 'The Gemini assistant could not respond. Please try again.',
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
                            <label htmlFor="outing-request">Describe your ideal outing</label>
                            <div className="ai-input-shell">
                                <textarea
                                    ref={textareaRef}
                                    id="outing-request"
                                    value={message}
                                    onChange={(event) => {
                                        setMessage(event.target.value);
                                        if (error) setError(null);
                                        setReply(null);
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
                                    <span>{isLoading ? 'Thinking…' : 'Ask Gemini'}</span>
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
                                    Gemini chat endpoint
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

                        {reply && (
                            <div className="planner-error" role="status" aria-live="polite">
                                <strong>Gemini assistant</strong>
                                <p>{reply}</p>
                            </div>
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
