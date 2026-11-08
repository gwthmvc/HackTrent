import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { createBrowserRouter, RouterProvider } from 'react-router';
import routes from './routes';
import { auth0ApiScope, auth0Audience, auth0ClientId, auth0Domain } from './auth/config';

const router = createBrowserRouter(routes);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
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
    >
      <RouterProvider router={router} />
    </Auth0Provider>
  </StrictMode>,
)
