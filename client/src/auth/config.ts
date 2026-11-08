const configuredDomain = import.meta.env.VITE_AUTH0_DOMAIN;
const configuredClientId = import.meta.env.VITE_AUTH0_CLIENT_ID;
const configuredAudience = import.meta.env.VITE_AUTH0_AUDIENCE?.trim();

export const isAuth0Configured = Boolean(configuredDomain && configuredClientId);
export const auth0Domain = configuredDomain || 'missing-auth0-configuration.invalid';
export const auth0ClientId = configuredClientId || 'missing-auth0-client-id';
export const auth0Audience = configuredAudience;
export const auth0ApiScope = import.meta.env.VITE_AUTH0_API_SCOPE?.trim()
    || 'openid profile email read:transit';
export const isAuth0ApiConfigured = Boolean(configuredAudience);
