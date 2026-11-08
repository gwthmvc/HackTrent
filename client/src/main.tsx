import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { Auth0Provider } from '@auth0/auth0-react'
import { createBrowserRouter, RouterProvider } from 'react-router';
import routes from './routes';
import { auth0ApiScope, auth0Audience, auth0ClientId, auth0Domain } from './auth/config';

const router = createBrowserRouter(routes);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Auth0Provider
      domain={auth0Domain}
      clientId={auth0ClientId}
      authorizationParams={{
        redirect_uri: window.location.origin,
        ...(auth0Audience ? { audience: auth0Audience, scope: auth0ApiScope } : {}),
      }}
    >
      <RouterProvider router={router} />
    </Auth0Provider>
  </StrictMode>,
)
