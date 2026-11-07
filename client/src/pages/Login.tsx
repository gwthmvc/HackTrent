import '../styles/Login.css'
import { useEffect, useRef, useState, type SubmitEvent } from 'react'


export default function Login(){
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const errorRef = useRef<HTMLParagraphElement>(null);

    useEffect(() => {
        if (errorMsg) {
            errorRef.current?.focus();
        }
    }, [errorMsg]);

    const handleLogin = async (e: SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();

        if (!username.trim() || !password) {
            setErrorMsg('Please enter both username and password.');
            return;
        }

        setErrorMsg(null);
        // TODO: Implement login logic here (e.g., API call to authenticate the user)
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
                        <label htmlFor="username">Username</label>
                        <input
                            type="text"
                            id="username"
                            name="username"
                            autoComplete="username"
                            required
                            aria-required="true"
                            aria-invalid={Boolean(errorMsg && !username.trim())}
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

                        <button type="submit">Login</button>
                    </form>
                </div>
            </main>
        </>
    )
}