import { Auth0Provider } from '@auth0/auth0-react'
import type { PropsWithChildren } from 'react'
import { useNavigate } from 'react-router'
import { auth0ClientId, auth0Domain } from '../auth/config'

export default function Auth0ProviderWithNavigate({ children }: PropsWithChildren) {
    const navigate = useNavigate();

    return (
        <Auth0Provider
            domain={auth0Domain}
            clientId={auth0ClientId}
            cacheLocation="localstorage"
            authorizationParams={{
                redirect_uri: window.location.origin,
            }}
            onRedirectCallback={(appState) => {
                navigate(appState?.returnTo ?? '/home', { replace: true });
            }}
        >
            {children}
        </Auth0Provider>
    );
}
