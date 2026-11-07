import '../styles/Login.css'
import { useEffect, useRef, useState, type SubmitEvent } from 'react'
import { useNavigate } from 'react-router'
import { post } from '../services/api'

type LoginResponse = {
    api_key?: string;
    apiKey?: string;
    key?: string;
    token?: string;
    access_token?: string;
    user?: Record<string, unknown>;
    data?: LoginPayload;
    result?: LoginPayload;
    account?: Record<string, unknown>;
};

type LoginPayload = {
    api_key?: string;
    apiKey?: string;
    key?: string;
    token?: string;
    access_token?: string;
    user?: Record<string, unknown>;
    account?: Record<string, unknown>;
};

function getLoginDetails(response: LoginResponse) {
    const payload = response.data ?? response.result;
    const apiKey = response.api_key
        ?? response.apiKey
        ?? response.key
        ?? response.token
        ?? response.access_token
        ?? payload?.api_key
        ?? payload?.apiKey
        ?? payload?.key
        ?? payload?.token
        ?? payload?.access_token;
    const user = response.user
        ?? response.account
        ?? payload?.user
        ?? payload?.account;

    return { apiKey, user };
}

export default function Login(){
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const errorRef = useRef<HTMLParagraphElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (errorMsg) {
            errorRef.current?.focus();
        }
    }, [errorMsg]);

    const handleLogin = async (e: SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();

        if (!email.trim() || !password) {
            setErrorMsg('Please enter both email and password.');
            return;
        }

        setErrorMsg(null);
        setIsSubmitting(true);

        try {
            const response = await post<LoginResponse>('/login', {
                email: email.trim(),
                password,
            });
            const { apiKey, user } = getLoginDetails(response);

            if (!apiKey || !user) {
                throw new Error('Login response did not include account details.');
            }

            localStorage.setItem('api_key', apiKey);
            localStorage.setItem('user', JSON.stringify(user));
            navigate('/dashboard', { replace: true });
        } catch (error) {
            setErrorMsg(error instanceof Error ? error.message : 'Login failed.');
        } finally {
            setIsSubmitting(false);
        }
    }

    return(
        <>
            <title>Login | HackTrent</title>
            <main aria-labelledby="login-heading">
                <h1 id="login-heading">Login</h1>

                {errorMsg && (
                    <div className="error-container" role="alert" aria-atomic="true">
                        <p
                            ref={errorRef}
                            className="error"
                            id="login-error"
                            tabIndex={-1}
                        >
                            {errorMsg}
                        </p>
                    </div>
                )}

                <div className="login-container">
                    <form
                        onSubmit={handleLogin}
                        className="form-component"
                        noValidate
                        aria-describedby={errorMsg ? 'login-error' : undefined}
                    >
                        <label htmlFor="email">Email</label>
                        <input
                            type="email"
                            id="email"
                            name="email"
                            autoComplete="email"
                            required
                            aria-required="true"
                            aria-invalid={Boolean(errorMsg && !email.trim())}
                            value={email}
                            onChange={(e) => {
                                setEmail(e.target.value);
                                setErrorMsg(null);
                            }}
                        />

                        <label htmlFor="password">Password</label>
                        <input
                            type="password"
                            id="password"
                            name="password"
                            autoComplete="current-password"
                            required
                            aria-required="true"
                            aria-invalid={Boolean(errorMsg && !password)}
                            value={password}
                            onChange={(e) => {
                                setPassword(e.target.value);
                                setErrorMsg(null);
                            }}
                        />

                        <button type="submit" disabled={isSubmitting}>
                            {isSubmitting ? 'Logging in...' : 'Login'}
                        </button>
                    </form>
                </div>
            </main>
        </>
    )
}