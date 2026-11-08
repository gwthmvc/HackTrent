import '../styles/HomePage.css'
import { useState, type FormEvent } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { Link } from 'react-router'

interface ChatPart {
    text: string;
}

interface ChatMessage {
    role: 'user' | 'model';
    parts: ChatPart[];
}

export default function HomePage() {
    const { logout } = useAuth0();
    const [input, setInput] = useState<string>('');
    const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
    const [loading, setLoading] = useState<boolean>(false);

    const handleLogout = () => {
        void logout({
            logoutParams: {
                returnTo: window.location.origin,
            },
        });
    };

    const handleChatSubmit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userMessage: ChatMessage = { role: 'user', parts: [{ text: input }] };
        const updatedHistory = [...chatHistory, userMessage];

        setChatHistory(updatedHistory);
        setInput('');
        setLoading(true);

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: input, chatHistory: updatedHistory }),
            });

            const data = (await res.json()) as { reply?: string };
            const replyText = data.reply || "Error: No response from server.";

            setChatHistory(prev => [...prev, { role: 'model', parts: [{ text: replyText }] }]);
        } catch (err) {
            console.error("Fetch error:", err);
            setChatHistory(prev => [...prev, { role: 'model', parts: [{ text: "Network error connecting to API." }] }]);
        } finally {
            setLoading(false);
        }
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
                            <p className="home-eyebrow">Your personal intelligence view</p>
                            <h1 id="home-heading">Good morning, Zeno.</h1>
                            <p>
                                Ask questions, query your database documents, and
                                interact with your Gemini-powered RAG assistant.
                            </p>
                        </div>
                        <div className="home-date" aria-label="Current location">
                            <span className="home-date-marker" aria-hidden="true">●</span>
                            <span>Oshawa, Ontario</span>
                        </div>
                    </section>

                    <section className="home-dashboard-grid single-chat-grid" aria-label="Home dashboard">
                        <article className="home-card chat-card active-chat-card">
                            <div className="card-heading">
                                <div>
                                    <p className="home-eyebrow">Ask Personal Companion</p>
                                    <h2>Gemini RAG Chat</h2>
                                </div>
                                <span className="chat-spark" aria-hidden="true">✦</span>
                            </div>

                            {/* Chat Messages Display Window */}
                            <div className="chat-messages-container" style={{ minHeight: '300px', maxHeight: '450px', overflowY: 'auto', marginBottom: '1rem', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                {chatHistory.length === 0 ? (
                                    <div className="chat-empty-state" style={{ margin: 'auto', textAlign: 'center', color: '#666' }}>
                                        <div className="chat-icon" aria-hidden="true">✦</div>
                                        <p className="chat-placeholder">
                                            Your personal database assistant is ready.
                                        </p>
                                        <p className="chat-helper">
                                            Ask about your projects, notes, or technical setup.
                                        </p>
                                    </div>
                                ) : (
                                    chatHistory.map((msg, index) => (
                                        <div key={index} className={`chat-bubble ${msg.role}`} style={{ padding: '0.75rem 1rem', borderRadius: '8px', maxWidth: '85%', alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', background: msg.role === 'user' ? '#e0f2fe' : '#f3f4f6', color: '#111' }}>
                                            <span className="font-semibold block text-xs text-gray-500 mb-1" style={{ fontSize: '0.7rem', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '0.2rem', color: '#555' }}>
                                                {msg.role === 'user' ? 'You' : 'Companion'}
                                            </span>
                                            <div style={{ whiteSpace: 'pre-wrap' }}>{msg.parts[0].text}</div>
                                        </div>
                                    ))
                                )}
                                {loading && <p className="text-gray-400 italic" style={{ fontSize: '0.85rem', color: '#888' }}>Thinking and searching Tiger Data...</p>}
                            </div>

                            {/* Functional Input Form */}
                            <form className="chat-form" onSubmit={handleChatSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
                                <label className="sr-only" htmlFor="chat-question">
                                    Ask a question
                                </label>
                                <input
                                    id="chat-question"
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder="Ask about your project notes..."
                                    style={{ flex: 1, padding: '0.75rem', borderRadius: '6px', border: '1px solid #ccc' }}
                                />
                                <button type="submit" aria-label="Send question" style={{ padding: '0.75rem 1.25rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
                                    <span aria-hidden="true">→</span>
                                </button>
                            </form>
                        </article>
                    </section>
                </main>
            </div>
        </>
    )
}