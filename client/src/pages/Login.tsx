import '../styles/Login.css'
import { useAuth0 } from '@auth0/auth0-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { isAuth0Configured } from '../auth/config'

export default function Login() {
    const { error, isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);
    const [successMessage] = useState<string | null>(
        () => sessionStorage.getItem('hacktrent_signup_message'),
    );
    const errorRef = useRef<HTMLParagraphElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (isAuthenticated) {
            navigate('/home', { replace: true });
        }
    }, [isAuthenticated, navigate]);

    useEffect(() => {
        if (successMessage) {
            sessionStorage.removeItem('hacktrent_signup_message');
        }
    }, [successMessage]);

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
                appState: {
                    returnTo: '/home',
                },
                authorizationParams: {
                    prompt: 'login',
                },
            });
        } catch (loginError) {
            setLocalError(loginError instanceof Error ? loginError.message : 'Login failed.');
            setIsSubmitting(false);
        }
    };
    const displayError = error?.message ?? localError;

    return (
        <>
            <title>Login | HackTrent</title>
            <main aria-labelledby="login-heading">
                <h1 id="login-heading">Login</h1>

                {displayError && (
                    <div className="error-container" role="alert" aria-atomic="true">
                        <p ref={errorRef} className="error" tabIndex={-1}>
                            {displayError}
                        </p>
                    </div>
                )}

                {successMessage && (
                    <p className="success" role="status">{successMessage}</p>
                )}

                <div className="login-container">
                    <div className="form-component">
                        <p>Continue securely with your HackTrent account.</p>
                        <button
                            type="button"
                            onClick={handleLogin}
                            disabled={isLoading || isSubmitting}
                        >
                            {isSubmitting ? 'Redirecting...' : 'Continue with Auth0'}
                        </button>
                    </div>
                </div>
            </main>
        </>
    );
}
