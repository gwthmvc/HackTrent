import '../styles/Login.css'
import { useAuth0 } from '@auth0/auth0-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { isAuth0Configured } from '../auth/config'

export default function Login() {
    const { error, isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);
    const errorRef = useRef<HTMLParagraphElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (isAuthenticated) {
            navigate('/home', { replace: true });
        }
    }, [isAuthenticated, navigate]);

    useEffect(() => {
        if (error || localError) {
            errorRef.current?.focus();
        }
    }, [error, localError]);

    const handleLogin = async () => {
        if (!isAuth0Configured) {
            setLocalError('Auth0 is not configured for this deployment.');
            return;
        }

        setLocalError(null);
        setIsSubmitting(true);
        try {
            await loginWithRedirect({
                appState: { returnTo: '/home' },
            });
        } catch (loginError) {
            setLocalError(loginError instanceof Error ? loginError.message : 'Login failed.');
            setIsSubmitting(false);
        }
    };
    const displayError = error?.message ?? localError;

    return (
        <>
            <title>Login | SmartMove Ontario</title>
            <main aria-labelledby="login-heading">
                <header className="landing-header">
                    <Link className="landing-brand" to="/" aria-label="SmartMove Ontario home">
                        <span className="landing-brand-mark" aria-hidden="true"><span /><span /></span>
                        <span>SmartMove <small>Ontario</small></span>
                    </Link>
                </header>

                <div className="auth-content">
                    <h1 id="login-heading">Login</h1>
                    <p className="auth-subtitle">You&apos;ll sign in on Auth0&apos;s secure page, then return here to plan your outing.</p>

                    {displayError && (
                        <div className="error-container" role="alert" aria-atomic="true">
                            <p ref={errorRef} className="error" tabIndex={-1}>
                                {displayError}
                            </p>
                        </div>
                    )}

                    <div className="login-container">
                        <div className="form-component">
                            <p>Continue securely with your SmartMove Ontario account.</p>
                            <button
                                type="button"
                                onClick={handleLogin}
                                disabled={isLoading || isSubmitting}
                            >
                                {isSubmitting ? 'Redirecting...' : 'Continue with Auth0'}
                            </button>
                        </div>
                    </div>

                    <nav className="auth-links" aria-label="Login navigation">
                        <Link to="/">Back to home</Link>
                        <Link to="/register">New to SmartMove? Create an account</Link>
                    </nav>
                </div>
            </main>
        </>
    );
}
