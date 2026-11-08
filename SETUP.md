# SmartMove Ontario local setup

This repository contains a React/TypeScript frontend in `client/` and a Python
FastAPI backend in `backend/`. Each teammate must use their own local environment
files. Never commit real credentials.

## 1. Required software

- Git
- A Node.js release compatible with the checked-in `client/package-lock.json`
- npm
- Python 3.11 or newer
- Access to the project Auth0 tenant and any backend services you are authorized
  to use

`psql` is optional; the backend uses Psycopg directly.

## 2. Frontend setup

From the repository root:

```powershell
Set-Location client
npm install
Copy-Item .env.example .env.local
```

Edit `client/.env.local` with browser-safe configuration only:

| Variable | Required | Purpose |
|---|---:|---|
| `VITE_AUTH0_DOMAIN` | Yes | Public Auth0 tenant domain |
| `VITE_AUTH0_CLIENT_ID` | Yes | Public Auth0 SPA client ID |
| `VITE_SMARTMOVE_GENERATE_URL` | No | Full itinerary-generation endpoint once implemented |

Never put TigerData credentials, Gemini keys, Ticketmaster keys, or other private
secrets in a `VITE_` variable. Vite exposes those variables to the browser.

Run the frontend:

```powershell
npm run dev
```

The public landing page is `/`. Auth0-protected pages are `/home` and
`/dashboard`. When no generation endpoint is configured, submitting a request
opens a clearly labeled integration preview and does not fabricate an itinerary.

## 3. Backend setup

From the repository root:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `backend/.env` with your authorized server-side credentials:

| Variable | Required | Purpose |
|---|---:|---|
| `TIGERDATA_DATABASE_URL` | Yes | TLS-enabled TigerData PostgreSQL service URL |
| `GEMINI_API_KEY` | Future integration | Server-side Gemini credential |
| `TICKETMASTER_API_KEY` | Future integration | Server-side Ticketmaster credential |
| `TIGERDATA_SCHEMA` | Yes | Schema containing `bus_positions` |
| `TIGERDATA_BUS_POSITIONS_TABLE` | Yes | Transit hypertable name |
| `TIGERDATA_AGENCY_VALUES` | Yes | API agency IDs mapped to stored values |
| `TRANSIT_STALE_AFTER_SECONDS` | Yes | Freshness threshold |
| `AUTH_REQUIRED` | Yes | Keeps API authentication enabled |
| `AUTH0_DOMAIN` | Yes for protected API | Auth0 tenant domain |
| `AUTH0_AUDIENCE` | Yes for protected API | Auth0 API identifier |
| `AUTH0_REQUIRED_SCOPE` | Yes for protected API | Required API permission |
| `CORS_ALLOWED_ORIGINS` | Yes | JSON array of exact frontend origins |

Optional `TIGERDATA_*_COLUMN` variables override schema discovery when the live
column names are known.

Start FastAPI:

```powershell
python -m uvicorn app.main:app --reload
```

The read-only transit endpoint is:

```text
GET /api/transit/vehicles?agency_id=kingston
```

It requires an Auth0 Bearer token by default. Do not disable authentication in
shared or production environments.

## 4. Local verification

Frontend checks:

```powershell
Set-Location client
npm run lint
npm run build
```

Backend checks:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall -q app tests
```

These tests use controlled test records and do not require Gemini or transit
ingestion. Live-service checks should be deliberate and minimal.

## 5. Verify secrets are protected

From the repository root, confirm local environment files are ignored:

```powershell
git check-ignore -v backend/.env client/.env.local
```

Review everything proposed for a commit before staging or pushing:

```powershell
git status --short
git diff
git diff --cached
git ls-files | Select-String -Pattern '(^|/)\.env($|\.)'
```

Only `.env.example` templates with placeholders should be tracked. If a real
secret was ever committed, removing the file in a later commit is not enough:
rotate the credential and coordinate repository-history cleanup with the team.
