import '../styles/Register.css'
import { useEffect, useRef, useState, type SubmitEvent } from 'react'
import { useNavigate } from 'react-router'
import { post } from '../services/api'

export default function Register(){
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const errorRef = useRef<HTMLParagraphElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        if (errorMsg) {
            errorRef.current?.focus();
        }
    }, [errorMsg]);

    const handleRegister = async (e: SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();

        if (!firstName.trim() || !lastName.trim() || !email.trim() || !password) {
            setErrorMsg('Please complete all fields.');
            return;
        }

        if (password !== confirmPassword) {
            setErrorMsg('Passwords do not match.');
            return;
        }

        setErrorMsg(null);
        setSuccessMsg(null);
        setIsSubmitting(true);

        try {
            await post('/register', {
                first_name: firstName.trim(),
                last_name: lastName.trim(),
                email: email.trim(),
                password,
            });
            setSuccessMsg('Registration successful. Redirecting to login...');
            window.setTimeout(() => navigate('/login'), 1000);
        } catch (error) {
            setErrorMsg(error instanceof Error ? error.message : 'Registration failed.');
        } finally {
            setIsSubmitting(false);
        }
    }


    
    return(

        <>
            <title>Register | HackTrent</title>
            <main>
                <h1>Register</h1>

                {successMsg && <p className="success" role="status">{successMsg}</p>}

                {errorMsg && (
                    <div className="error-container" role="alert">
                        <p
                            ref={errorRef}
                            className="error"
                            id="register-error"
                            tabIndex={-1}
                        >
                            {errorMsg}
                        </p>
                    </div>
                )}

                <div className="register-container">
                    <form onSubmit={handleRegister} className="form-component">
                        <label htmlFor="first-name">First name</label>
                        <input
                            type="text"
                            id="first-name"
                            name="first_name"
                            autoComplete="given-name"
                            required
                            value={firstName}
                            onChange={(e) => {
                                setFirstName(e.target.value);
                                setErrorMsg(null);
                            }}
                        />

                        <label htmlFor="last-name">Last name</label>
                        <input
                            type="text"
                            id="last-name"
                            name="last_name"
                            autoComplete="family-name"
                            required
                            value={lastName}
                            onChange={(e) => {
                                setLastName(e.target.value);
                                setErrorMsg(null);
                            }}
                        />

                        <label htmlFor="email">Email</label>
                        <input
                            type="email"
                            id="email"
                            name="email"
                            autoComplete="email"
                            required
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
                            autoComplete="new-password"
                            required
                            value={password}
                            onChange={(e) => {
                                setPassword(e.target.value);
                                setErrorMsg(null);
                            }}
                        />

                        <label htmlFor="confirmPassword">Confirm Password</label>
                        <input
                            type="password"
                            id="confirmPassword"
                            name="confirmPassword"
                            autoComplete="new-password"
                            required
                            aria-invalid={Boolean(errorMsg)}
                            aria-describedby={errorMsg ? 'register-error' : undefined}
                            value={confirmPassword}
                            onChange={(e) => {
                                setConfirmPassword(e.target.value);
                                setErrorMsg(null);
                            }}
                        />

                        <button type="submit" disabled={isSubmitting}>
                            {isSubmitting ? 'Registering...' : 'Register'}
                        </button>

                    </form>
                </div>
            </main>


        </>
    )
}