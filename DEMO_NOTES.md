# Demo notes

## What the demo shows

- A natural-language request is turned into:
  - sourced events from Ticketmaster;
  - places from OpenStreetMap through Overpass; and
  - scheduled Durham transit from direct GTFS trips.
- Each source has an explicit status. Missing data is reported as unavailable,
  never as an empty successful result.

## Known limitations

Say these plainly if asked:

- Transit observations are historical, not live. The repository does not
  establish that the latest sample is from 2026-11-07 (unverified); the
  freshness label is computed in `backend/app/service.py`.
- Places are unavailable when Overpass times out (`places_upstream_timeout`).
  Failed place lookups are cached for 300 seconds
  (`PLACES_FAILURE_TTL_SECONDS` in `backend/app/places.py`).
- Scheduled transit covers direct trips only: no transfers and no real-time
  arrival predictions (`backend/app/gtfs.py`).
- Scheduled transit only covers dates in the GTFS calendar. Dates outside the
  imported feed return 422 (`schedule_date_outside_feed`) in `gtfs.py`.
- There is no public-safety or police data. `backend/app/outings.py` reports
  it as unavailable.
- Event search results are cached in memory for
  `EVENTS_CACHE_TTL_SECONDS` (default 900 seconds). Restarting the backend
  clears this cache (`backend/app/config.py`).
- Caches and rate limits are per process, not shared.

## Behaviour that can look like a bug

- A departure time also filters events to roughly one hour before through
  three hours after that time, both in the plan and on the Events map. This is
  `_parse_time_range` in `backend/app/events.py`.
- If no date is given, Events searches the next 14 days, and the Events
  heading shows that window (`DEFAULT_WINDOW_DAYS` in `events.py`).
- Event and itinerary markers at the same coordinates merge into one marker.
  The event label is retained because event locations are processed first
  (the requested claim that the itinerary label is retained does not match
  the code). The Events toggle can therefore look inactive while Itinerary is on
  (`client/src/components/SharedDashboardMap.tsx`).
- Turning off both recommendation layers hides markers, not data. The
  sightings legend remains visible.

## Security tradeoffs

- The Auth0 access token is stored in `localStorage` (`cacheLocation:
  "localstorage"` in `client/src/main.tsx`). An XSS bug could expose it.
- The backend verifies JWTs on protected routes. A local demo may run with
  `AUTH_REQUIRED=false`; that is local-only. The default is `true` in
  `backend/app/config.py`.

## Demo script

1. Request: “Have a fun outing in Oshawa on November 21st at 11:00am”.
   Start: Durham College, Oshawa, Ontario. Date: `2026-11-21`. Time:
   `11:00`.
2. Expected result: 2 events, places unavailable, and 5 Route 901 trips.
   These exact live results are unverified against the checked-in code and
   current upstream responses.
3. Show the honesty points: places unavailable, transit historical, and a
   December 24 request returning zero events with the date named. The exact
   upstream result is unverified; the date is included in the event window
   when that search succeeds.

## Verified demo path (2026-11-08)

- Prompt: "Fun day out with friends the weekend of November 21 in oshawa".
  Start: Durham College, Oshawa, Ontario. Date and time: blank.
- Expected: plan summary "5 events found on 2026-11-21"; itinerary lists 5
  events in time order; places unavailable with `places_upstream_timeout`;
  transit labelled historical, not live; scheduled Route 901 trips shown with
  the direct-trips-only caveat.
- Known display limit: map markers are one per venue, so one marker can
  represent several events. The itinerary list shows each event.
- Known limit: a request with a specific departure time filters events to about
  one hour before through three hours after that time.
