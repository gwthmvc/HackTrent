const configuredDomain = import.meta.env.VITE_AUTH0_DOMAIN;
const configuredClientId = import.meta.env.VITE_AUTH0_CLIENT_ID;

export const isAuth0Configured = Boolean(configuredDomain && configuredClientId);
export const auth0Domain = configuredDomain || 'missing-auth0-configuration.invalid';
export const auth0ClientId = configuredClientId || 'missing-auth0-client-id';
