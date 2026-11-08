# SmartMove Ontario backend

FastAPI service for read-only transit observations stored in TigerData Cloud.

## Local setup

1. Create and activate a Python virtual environment.
2. Install the package with development dependencies:

   ```powershell
   python -m pip install -e ".[dev]"
   ```

3. Copy `.env.example` to `.env` and set the server-side values. Never place the
   TigerData URL in the React client or in a `VITE_` variable.
4. Start the API from `backend/`:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

5. Run tests with `python -m pytest`.

## Endpoint

`GET /api/transit/vehicles?agency_id=kingston`

The Home/Dashboard integration uses `POST /api/transit/context` with:

```json
{
  "startingLocation": "Durham College, Oshawa, Ontario",
  "outingRequest": "A family day out in Kingston using transit."
}
```

The context endpoint selects a supported area from the outing request first,
then the starting location. Durham Region municipality names map to `durham`;
Kingston maps to `kingston`. Requests with no supported area return a structured
`unsupported_area` error without querying TigerData.

Supported canonical agency IDs default to `kingston` and `durham`. Use
`TIGERDATA_AGENCY_VALUES` to map those IDs to the exact values stored in the
database after inspecting real records.

Successful response:

```json
{
  "agencyId": "kingston",
  "status": "current",
  "retrievedAt": "2026-11-07T23:00:00Z",
  "latestObservationAt": "2026-11-07T22:59:42Z",
  "staleAfterSeconds": 300,
  "vehicles": [
    {
      "vehicleId": "vehicle-17",
      "agencyId": "kingston",
      "routeId": "7",
      "latitude": 44.2312,
      "longitude": -76.486,
      "observedAt": "2026-11-07T22:59:42Z",
      "freshness": {
        "status": "current",
        "ageSeconds": 18,
        "staleAfterSeconds": 300
      }
    }
  ]
}
```

The API returns structured errors for unsupported agencies or areas, missing records,
unverified schemas, unavailable databases, and authentication failures. Old
records are returned as `stale`; they are never presented as live data.

## Durham GTFS scheduled journeys

Static Durham Region Transit schedules are deliberately stored separately from
TigerData vehicle observations. Refresh the local validated cache explicitly:

```powershell
python -m app.gtfs_ingest
```

The importer conditionally downloads the official Durham ZIP with ETag and
Last-Modified headers, validates routes, stops, trips, stop times, calendars,
calendar exceptions, and trip-referenced shapes, then atomically replaces
`data/gtfs/durham.sqlite3`. Matching archive hashes are not re-imported. The
cache directory is excluded from Git, and the API opens it read-only.

`POST /api/transit/journeys/search` requires the existing Auth0 `read:transit`
permission:

```json
{
  "agencyId": "durham",
  "origin": {"name": "Durham College, Oshawa, Ontario"},
  "destination": {"latitude": 43.897, "longitude": -78.86},
  "serviceDate": "2026-11-09",
  "departureTime": "17:30",
  "maxWalkingDistanceMeters": 800,
  "maxResults": 5
}
```

Origin and destination selectors may use a GTFS stop ID, a stop-name query, or
coordinates. Coordinate matching identifies nearby published stops; it does
not claim a walking route or walking time. Results contain only direct trips
where one scheduled GTFS trip serves the boarding stop before the alighting
stop. Route number, stops, timezone-aware scheduled departure/arrival, duration,
shape ID, feed coverage, source modification time, import time, and feed
freshness are returned. Times above 24:00 correctly roll into the next calendar
day while retaining the original GTFS service date.

Transfers, frequency-based routing, accessibility routing, walking directions,
fares, and real-time arrival prediction are not implemented. If no direct trip
exists, the endpoint returns `unsupported_journey` instead of inventing a route.
The importer is never run automatically by API startup or a polling worker.

## Ticketmaster events

`POST /api/events/search` (requires the same Auth0 `read:transit` access token)

```json
{
  "startingLocation": "Durham College, Oshawa, Ontario",
  "outingRequest": "A family day out in Kingston this Saturday evening",
  "date": "2026-11-14",
  "time": "18:00",
  "interests": ["hockey"]
}
```

`date`, `time` and `interests` are optional; otherwise they are read from the
request text (today, tonight, tomorrow, this weekend, weekday names, ISO or
"December 5" dates, morning/afternoon/evening, "after 7pm"). The default window
is the next 14 days. Areas: Durham Region (35 km around Oshawa/Whitby) and
Kingston (25 km). Other areas return `unsupported_event_area` without calling
Ticketmaster.

- `TICKETMASTER_API_KEY` is read only from `backend/.env`. It is sent only to
  Ticketmaster; httpx request logging is suppressed so it never reaches logs,
  and errors never echo upstream URLs.
- Venue coordinates are returned only when Ticketmaster supplies them and they
  fall within the search area (`coordinateStatus`: `verified`, `missing`,
  `outside_search_area`). Prices and links are `null` when not provided;
  links are limited to official Ticketmaster/Live Nation hosts. Cancelled
  events are excluded. Nothing is invented.
- Successful results are cached in memory for `EVENTS_CACHE_TTL_SECONDS`
  (default 900). Upstream calls are capped by
  `TICKETMASTER_MAX_REQUESTS_PER_MINUTE` (20) and
  `TICKETMASTER_MAX_REQUESTS_PER_DAY` (1000), and each user is limited to
  `EVENTS_MAX_SEARCHES_PER_USER_PER_MINUTE` (10). The cache and limits are
  per-process.
- Errors: `events_not_configured` (503), `events_rate_limited` (429),
  `events_upstream_timeout` (504), `events_upstream_error` /
  `events_upstream_auth` (502), `invalid_event_date` (422).

## OpenStreetMap places

`POST /api/places/search` requires the same Auth0 `read:transit` access token:

```json
{
  "startingLocation": "Durham College, Oshawa, Ontario",
  "outingRequest": "Find somewhere to eat near an Oshawa Generals game",
  "destinationName": "Verified Ticketmaster venue",
  "destinationLatitude": 43.9,
  "destinationLongitude": -78.9
}
```

The destination fields are optional, but the latitude and longitude must be
provided together. SmartMove supplies them only when a Ticketmaster event or
venue in the prompt has verified coordinates. Otherwise the service uses the
supported Durham Region or Kingston search centre and labels that fallback in
the response.

One bounded Overpass query discovers named restaurants/cafes, parks and outdoor
attractions, museums and cultural attractions, and entertainment/family
activities. Explicit request intent selects only the relevant category tags;
broad requests combine each OpenStreetMap tag family into one selector. Durham
and Kingston area searches use a 3.5 km radius, and verified destinations use
at most 2 km. Responses contain only returned
OpenStreetMap names, tags, addresses, coordinates, straight-line distances, and
source object links. Missing addresses remain explicitly unavailable; ratings,
prices, hours, availability, routes, and travel times are never inferred.

Successful results are cached in memory for `PLACES_CACHE_TTL_SECONDS`
(default 3600). Requests are serialized per process to prevent parallel public
Overpass calls and limited by `OVERPASS_MAX_REQUESTS_PER_MINUTE` (default 4)
and `PLACES_MAX_SEARCHES_PER_USER_PER_MINUTE` (default 10). The query itself
sets a server-side timeout, an 8 MB memory bound, and a 60-element output cap,
while the client also caps download size. Configure a descriptive
`OVERPASS_USER_AGENT` before shared or production use. There are no automatic
retries. The default endpoint is the global public Private.coffee instance
listed by OpenStreetMap; `OVERPASS_BASE_URL` remains configurable so a managed
or self-hosted endpoint can be used without a code change.

Errors are sanitized as `unsupported_place_area` (422),
`places_rate_limited` (429), `places_upstream_timeout` (504), or
`places_upstream_error` (502). Public Overpass is suitable only for light,
cached traffic; production scale requires a dedicated or managed provider.

## Schema verification

Before reading vehicle data, the repository queries `information_schema.columns`
and `timescaledb_information.hypertables`. It requires verified columns for:

- agency ID
- vehicle ID
- route ID
- latitude and longitude using numeric types
- observation time using `timestamp with time zone`

The verified development hypertable currently contains `agency_id`,
`vehicle_id`, `route_id`, `trip_id`, `observed_at`, `latitude`, and `longitude`.
Known column names are still discovered from the live schema. Exact names can instead
be supplied through the optional `TIGERDATA_*_COLUMN` variables. SQL identifiers
are composed with Psycopg identifier objects, and agency values remain bound
parameters. Vehicle reads are limited to the configured 24-hour lookback and
maximum result count.

## Security

- `AUTH_REQUIRED=true` by default.
- Access tokens are verified using the Auth0 tenant JWKS, issuer, API audience,
  expiration, and the `read:transit` scope.
- CORS allows only explicitly configured origins and the `GET`, `POST`, and
  `OPTIONS` methods required by the protected APIs.
- TigerData connections force TLS and use read-only transactions.
- Pool failures are logged server-side without returning credentials or raw
  database errors to clients.

The React app requests the configured Auth0 API audience and `read:transit`
scope. The Auth0 API must grant that permission to the signed-in user.
