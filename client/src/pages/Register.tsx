import '../styles/Register.css'
import { useAuth0 } from '@auth0/auth0-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'

export default function Register() {
    const { error, isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);
    const errorRef = useRef<HTMLParagraphElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (isAuthenticated) {
            navigate('/dashboard', { replace: true });
        }
    }, [isAuthenticated, navigate]);

    useEffect(() => {
        if (error || localError) {
            errorRef.current?.focus();
        }
    }, [error, localError]);

    const handleRegister = async () => {
        setLocalError(null);
        setIsSubmitting(true);
        try {
            await loginWithRedirect({
                authorizationParams: {
                    screen_hint: 'signup',
                },
            });
        } catch (registrationError) {
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
