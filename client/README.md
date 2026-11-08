# React + TypeScript + Vite

## Auth0 configuration

Copy `.env.example` to `.env.local` and replace the placeholder values with the
Auth0 application domain and client ID. Configure the Auth0 application
callback URL, logout URL, and allowed web origins to include the URL used by
Vite (for example, `http://localhost:5173`).

To load protected TigerData observations, configure the same Auth0 API audience
in the frontend and backend, grant the `read:transit` scope, and set
`VITE_SMARTMOVE_API_URL` to the FastAPI base URL. The browser sends only the
Bearer token, starting location, and outing request; TigerData credentials stay
in `backend/.env`.

For GitHub Actions deployments, add repository secrets named
`VITE_AUTH0_DOMAIN` and `VITE_AUTH0_CLIENT_ID`. The deployment workflow passes
these values to the production build.

The chat client uses `/api/chat` by default. Local Vite development proxies
that path to the configured backend. Production hosting must proxy
`/api/chat` to the backend over HTTPS, or provide a public HTTPS endpoint with
`VITE_CHAT_API_URL` at build time; browsers block calls from `https://sloo.ca`
to the backend's HTTP address.

Authentication is handled by Auth0's hosted login page. The login and
registration pages redirect to Auth0 and then return to `/home`. The `/home`
and `/dashboard` routes require an authenticated session. Home collects the
outing request; Dashboard displays a validated plan or a clearly labeled
integration preview when the generation endpoint is unavailable.

## SmartMove planner API

This repository does not currently contain a working trip-generation backend.
The Home page therefore reports that planning is unavailable and does not show
mock itinerary data. Once a compatible backend exists, set the complete
generation endpoint in `VITE_SMARTMOVE_GENERATE_URL`. The frontend sends:

```json
{
  "message": "The user's natural-language outing request",
  "startingLocation": "Durham College, Oshawa, Ontario"
}
```

The Home page defaults to Durham College's Oshawa campus and lets the user edit
the value. A clearly stated departure point in the natural-language request
overrides the field. The backend should return `startingLocation` as a verified
location record when it can resolve coordinates; the map will not guess
coordinates for an unverified address.

Transit vehicle positions come independently from
`POST /api/transit/context`. Current and stale observations use distinct map
markers and timestamps. Vehicle positions are not used to invent route lines,
arrival estimates, or transit availability.

Durham static schedules are available separately through the typed
`POST /api/transit/journeys/search` client in `src/services/journeysApi.ts`.
The contract supports direct scheduled GTFS trips only. It does not combine
TigerData positions with schedules or convert observations into ETAs.

Ticketmaster events and OpenStreetMap places are fetched independently through
the protected FastAPI API. Place discovery supports Durham Region and Kingston,
uses a verified Ticketmaster venue as its proximity anchor when the prompt
matches one, and otherwise clearly identifies the supported-area search centre.
The Dashboard provides linked place cards and map markers with category and
straight-line proximity filters. It displays source links and missing-address
notices, and does not invent ratings, prices, hours, availability, directions,
or travel times.

The response must match the typed and runtime-validated `OutingPlan` contract in
`src/types/outing.ts` and `src/services/api.ts`. Results are rendered only after
that validation succeeds. API keys and database credentials must remain on the
backend and must never be stored in a `VITE_` variable.

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```

You can also install [eslint-plugin-react-x](https://npmx.dev/package/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://npmx.dev/package/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```
