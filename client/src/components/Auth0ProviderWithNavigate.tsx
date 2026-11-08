import { Auth0Provider, useAuth0 } from '@auth0/auth0-react'
import type { PropsWithChildren } from 'react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import {
    auth0ApiScope,
    auth0Audience,
    auth0ClientId,
    auth0Domain,
} from '../auth/config'

export default function Auth0ProviderWithNavigate({ children }: PropsWithChildren) {
    const [redirectPending, setRedirectPending] = useState(false);

    return (
        <Auth0Provider
            domain={auth0Domain}
            clientId={auth0ClientId}
            cacheLocation="localstorage"
            useRefreshTokens={true}
            authorizationParams={{
                redirect_uri: window.location.origin,
                ...(auth0Audience
                    ? {
                        audience: auth0Audience,
                        scope: ['openid', 'profile', 'email', 'offline_access', auth0ApiScope]
                            .filter(Boolean)
                            .join(' '),
                    }
                    : {}),
            }}
            onRedirectCallback={() => {
                setRedirectPending(true);
            }}
        >
            <AuthRedirectGate
                redirectPending={redirectPending}
                onRedirectComplete={() => setRedirectPending(false)}
            >
                {children}
            </AuthRedirectGate>
        </Auth0Provider>
    );
}

function AuthRedirectGate({
    children,
    redirectPending,
    onRedirectComplete,
}: PropsWithChildren<{
    redirectPending: boolean;
    onRedirectComplete: () => void;
}>) {
    const { isAuthenticated, isLoading } = useAuth0();
    const navigate = useNavigate();

    useEffect(() => {
        if (redirectPending && !isLoading && isAuthenticated) {
            navigate('/home', { replace: true });
            onRedirectComplete();
        }
    }, [isAuthenticated, isLoading, navigate, onRedirectComplete, redirectPending]);

    if (redirectPending) {
        return <p role="status" aria-live="polite">Loading your home page...</p>;
    }

    return children;
}
