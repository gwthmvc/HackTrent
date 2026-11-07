import '../styles/Register.css'
import { useEffect, useRef, useState, type SubmitEvent } from 'react'


export default function Register(){
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');

    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const errorRef = useRef<HTMLParagraphElement>(null);

    useEffect(() => {
        if (errorMsg) {
            errorRef.current?.focus();
        }
    }, [errorMsg]);

    const handleRegister = async (e: SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();

        // Check if passwords match
        if (password !== confirmPassword) {
            setErrorMsg("Passwords do not match");
            return;
        }

        // TODO: Implement registration logic here (e.g., API call to register the user)
    }


    
    return(

        <>
            <title>Register | HackTrent</title>
            <main>
                <h1>Register</h1>

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
                        <label htmlFor="username">Username</label>
                        <input
                            type="text"
                            id="username"
                            name="username"
                            autoComplete="username"
                            required
                            value={username}
                            onChange={(e) => {
                                setUsername(e.target.value);
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
                            aria-invalid={errorMsg === "Passwords do not match"}
                            aria-describedby={errorMsg ? "register-error" : undefined}
                            value={confirmPassword}
                            onChange={(e) => {
                                setConfirmPassword(e.target.value);
                                setErrorMsg(null);
                            }}
                        />

                        <button type="submit">Register</button>

                    </form>
                </div>
            </main>


        </>
    )
}