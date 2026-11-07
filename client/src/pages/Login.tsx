import '../styles/Login.css'
import { useAuth0 } from '@auth0/auth0-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'

export default function Login() {
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

    const handleLogin = async () => {
        setLocalError(null);
        setIsSubmitting(true);
        try {
            await loginWithRedirect();
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
