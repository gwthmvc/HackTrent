import '../styles/Register.css'
import { useAuth0 } from '@auth0/auth0-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { isAuth0Configured } from '../auth/config'

const SIGNUP_COMPLETED_KEY = 'hacktrent_signup_completed';

export default function Register() {
    const { error, isAuthenticated, isLoading, loginWithRedirect, logout } = useAuth0();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);
    const errorRef = useRef<HTMLParagraphElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (isAuthenticated) {
            navigate('/home', { replace: true });
        }
    }, [isAuthenticated, logout, navigate]);

    useEffect(() => {
        if (error || localError) {
            errorRef.current?.focus();
        }
    }, [error, localError]);

    const handleRegister = async () => {
        if (!isAuth0Configured) {
            setLocalError('Auth0 is not configured for this deployment.');
            return;
        }

        setLocalError(null);
        setIsSubmitting(true);
        sessionStorage.setItem(SIGNUP_COMPLETED_KEY, 'true');
        try {
            await loginWithRedirect({
                appState: { returnTo: '/home' },
                authorizationParams: {
                    screen_hint: 'signup',
                },
            });
        } catch (registrationError) {
            sessionStorage.removeItem(SIGNUP_COMPLETED_KEY);
            setLocalError(
                registrationError instanceof Error
                    ? registrationError.message
                    : 'Registration failed.',
            );
            setIsSubmitting(false);
        }
    };
    const displayError = error?.message ?? localError;

    return (
        <>
            <title>Register | SmartMove Ontario</title>
            <main>
                <header className="landing-header">
                    <Link className="landing-brand" to="/" aria-label="SmartMove Ontario home">
                        <span className="landing-brand-mark" aria-hidden="true"><span /><span /></span>
                        <span>SmartMove <small>Ontario</small></span>
                    </Link>
                </header>

                <div className="auth-content">
                    <h1>Register</h1>
                    <p className="auth-subtitle">You&apos;ll create your account on Auth0&apos;s secure page, then return here to plan your outing.</p>

                    {displayError && (
                        <div className="error-container" role="alert" aria-atomic="true">
                            <p ref={errorRef} className="error" tabIndex={-1}>
                                {displayError}
                            </p>
                        </div>
                    )}

                    <div className="register-container">
                        <div className="form-component">
                            <p>Create your SmartMove Ontario account securely with Auth0.</p>
                            <button
                                type="button"
                                onClick={handleRegister}
                                disabled={isLoading || isSubmitting}
                            >
                                {isSubmitting ? 'Redirecting...' : 'Sign up with Auth0'}
                            </button>
                        </div>
                    </div>

                    <nav className="auth-links" aria-label="Registration navigation">
                        <Link to="/">Back to home</Link>
                        <Link to="/login">Already have an account? Log in</Link>
                    </nav>
                </div>
            </main>
        </>
    );
}