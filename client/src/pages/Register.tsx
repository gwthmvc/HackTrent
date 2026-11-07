import '../styles/Register.css'
import { useAuth0 } from '@auth0/auth0-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { isAuth0Configured } from '../auth/config'

const SIGNUP_COMPLETED_KEY = 'hacktrent_signup_completed';

export default function Register() {
    const { error, isAuthenticated, isLoading, loginWithRedirect, logout } = useAuth0();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);
    const errorRef = useRef<HTMLParagraphElement>(null);
    const handledSignupRef = useRef(false);
    const navigate = useNavigate();

    useEffect(() => {
        if (isAuthenticated) {
            const signupCompleted = sessionStorage.getItem(SIGNUP_COMPLETED_KEY) === 'true';

            if (signupCompleted && !handledSignupRef.current) {
                handledSignupRef.current = true;
                sessionStorage.removeItem(SIGNUP_COMPLETED_KEY);
                sessionStorage.setItem(
                    'hacktrent_signup_message',
                    'Your account was created. Please log in with your new details.',
                );
                sessionStorage.setItem('hacktrent_logout_redirect', 'login');
                void logout({
                    logoutParams: {
                        returnTo: window.location.origin,
                    },
                }).catch((logoutError: unknown) => {
                    setLocalError(
                        logoutError instanceof Error
                            ? logoutError.message
                            : 'Unable to finish registration. Please try logging in again.',
                    );
                });
                return;
            }

            navigate('/dashboard', { replace: true });
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
            <title>Register | HackTrent</title>
            <main>
                <h1>Register</h1>

                {displayError && (
                    <div className="error-container" role="alert" aria-atomic="true">
                        <p ref={errorRef} className="error" tabIndex={-1}>
                            {displayError}
                        </p>
                    </div>
                )}

                <div className="register-container">
                    <div className="form-component">
                        <p>Create your HackTrent account securely with Auth0.</p>
                        <button
                            type="button"
                            onClick={handleRegister}
                            disabled={isLoading || isSubmitting}
                        >
                            {isSubmitting ? 'Redirecting...' : 'Sign up with Auth0'}
                        </button>
                    </div>
                </div>
            </main>
        </>
    );
}
