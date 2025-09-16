Here’s a complete README.md you can drop into the repo.

# SafeLane Vision — Backend

FastAPI + Postgres/PostGIS backend for bicycle hazard detection. Includes HMAC device auth, request auditing, per-endpoint rate limiting, a 5-minute weather cache, and provider toggle between premium (Mapbox + OpenWeather) and free (OSRM + Open-Meteo).

The API binds to localhost by default. Secrets live in `.env` (never commit). Docker Compose runs API and DB.

---

## 1) Quick start

1. Prerequisites  
   - Docker Desktop with Compose  
   - `curl`, `psql`, `openssl` (macOS has `openssl` via brew or system LibreSSL)  
   - Optional: `jq` for output formatting

2. Clone and prepare environment
   ```bash
   cp .env.example .env            # edit values; see section 3
   ```

3. Build and run
    ```bash
    docker compose up -d --build
    ```

4. Apply migrations (schema + audit)
    ```bash
    docker compose exec -T db psql -U postgres -d safelane -f /app/migrations/init.sql
    docker compose exec -T db psql -U postgres -d safelane -f /app/migrations/audit.sql
    ```

5. Verify health
    ```bash
    curl -s http://127.0.0.1:8000/health | jq .
    curl -s http://127.0.0.1:8000/config | jq .
    ```


## 2) Services and ports
    - API: http://127.0.0.1:8000
    - DB host bind: 127.0.0.1:55432 → container 5432
        Example:
        psql -h 127.0.0.1 -p 55432 -U postgres -d safelane
    - Ports are bound to 127.0.0.1 for local security.

## 3) Environment variables

Create .env (do not commit). Use .env.example as a template.

Name	Type	Example	Notes
PROVIDER_MODE	enum	premium | free	premium uses Mapbox + OpenWeather. free uses OSRM + Open-Meteo (no keys).
OPENWEATHER_KEY	string	a1b2c3...	Required in premium. Obtain from OpenWeather dashboard.
MAPBOX_TOKEN	string	pk.eyJ...	Required in premium. Mapbox public token.
HTTP_TIMEOUT_S	number	15	HTTP client timeout.
DEVICE_SECRET	string	hex_64	HMAC secret for device auth. Generate locally.
ALLOW_PUBLIC_READS	bool	true	If false, GETs can be gated behind device auth.
AUTH_CLOCK_SKEW_S	integer	300	Allowed time skew for signed headers.

Generate a strong secret:

openssl rand -hex 32


## 4) Architecture

flowchart LR
  A[React Native App] -->|frames + GPS| B[On-device CV\nOWL-ViT + MiDaS + DeepLabv3]
  B -->|risk events| C[Signer (HMAC) + Uploader]
  C -->|HTTPS| D[FastAPI]
  D -->|insert| E[(Postgres\nPostGIS + pgvector)]
  D -->|audit| J[(request_audit)]
  D -->|tiles/geojson (future)| G[Dashboard]
  D --> I[External APIs\nOverpass, Weather, Directions]
  I --> D
  B -->|HUD overlays| A


## 5) Endpoints
	•	GET /health → { "ok": true }
	•	GET /config → provider mode, timeouts, presence of keys
	•	POST /v1/provision → register/update device, returns class list and limits
	•	GET /v1/weather?lat=&lon= → current weather (cached 5 min; 1 r/s, burst 3)
	•	GET /v1/route?lat1=&lon1=&lat2=&lon2= → cycling route
	•	GET /v1/overpass?lat=&lon=&r=800 → nearby OSM features (dev utility)
	•	POST /v1/ingest/event → insert hazard event (HMAC auth required)

## 6) Usage examples

6.1 Provision

curl -s -X POST http://127.0.0.1:8000/v1/provision \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"ios-abc123","platform":"ios"}' | jq .

6.2 Weather and routing

curl -s 'http://127.0.0.1:8000/v1/weather?lat=43.6532&lon=-79.3832' | jq .
curl -s 'http://127.0.0.1:8000/v1/route?lat1=43.6532&lon1=-79.3832&lat2=43.6629&lon2=-79.3957' | jq .

6.3 Signed ingest (HMAC-SHA256)

Generate the header using your .env values:

export DEVICE_SECRET="$(grep -E '^DEVICE_SECRET=' .env | cut -d= -f2-)"
export DEVICE_ID="ios-abc123"
export TS="$(date +%s)"
export SIG="$(printf "%s.%s" "$DEVICE_ID" "$TS" | \
  openssl dgst -sha256 -hmac "$DEVICE_SECRET" -r | awk '{print $1}')"
export AUTH="Authorization: Device device_id=$DEVICE_ID,ts=$TS,sig=$SIG"
echo "$AUTH"

Send the event:

curl -s -H "$AUTH" -X POST http://127.0.0.1:8000/v1/ingest/event \
  -H 'Content-Type: application/json' -d '{
  "ts":"2025-08-20T15:05:00Z","device_id":"'"$DEVICE_ID"'",
  "geo":{"lat":43.6532,"lon":-79.3832},"class_":"cone","score":0.7,
  "bbox_xyxy":[5,5,15,15],"depth_m":2.2,"lane_offset_m":0.1,"ttc_s":1.5,"risk":0.5
}'

Verify rows:

psql -h 127.0.0.1 -p 55432 -U postgres -d safelane -c \
"SELECT class, risk, ts FROM hazards ORDER BY ts DESC LIMIT 5;"


## 7) Provider toggle

Switch to free providers (no keys needed):

# edit .env
PROVIDER_MODE=free
docker compose up -d --build

Switch back to premium:

# edit .env with real keys
PROVIDER_MODE=premium
docker compose up -d --build


## 8) Database schema and migrations

Files:
	•	backend/migrations/init.sql → core tables and indexes
	•	backend/migrations/audit.sql → request_audit table

Apply:

docker compose exec -T db psql -U postgres -d safelane -f /app/migrations/init.sql
docker compose exec -T db psql -U postgres -d safelane -f /app/migrations/audit.sql

Quick checks:

psql -h 127.0.0.1 -p 55432 -U postgres -d safelane -c "\dt"
psql -h 127.0.0.1 -p 55432 -U postgres -d safelane -c \
"SELECT method,path,status,ms,ts FROM request_audit ORDER BY id DESC LIMIT 5;"


## 9) Rate limiting and caching
	•	Weather: token bucket 1 r/s, burst 3. Change in backend/app/routes.py via limit("weather", rate, burst).
	•	Route: token bucket defaults similarly.
	•	Weather cache: 5 minutes, key rounded by ~110 m. Change TTL_S in backend/app/ext_weather.py.

## 10) Project layout
    ```bash
    backend/
    app/
        main.py              # app wiring and routers
        routes.py            # core endpoints
        routes_status.py     # /health, /config
        routes_provision.py  # /v1/provision
        auth.py              # HMAC device auth
        rl.py                # in-memory rate limiter
        audit.py             # request audit middleware
        http.py              # httpx client + retry
        ext_overpass.py      # OSM Overpass wrapper
        ext_weather.py       # weather provider + cache
        ext_directions.py    # routing provider
        db.py                # SQLAlchemy engine/session
    migrations/
        init.sql
        audit.sql
    docker-compose.yml
    .env.example
    ```

## 11) Security
	•	Do not commit .env. Keep .env.example with placeholders only.
	•	Ports bind to 127.0.0.1 by default in docker-compose.yml.
	•	Rotate DEVICE_SECRET if exposed. Regenerate signatures after rotation.
	•	Mapbox token should be a public token for server use. Keep provider keys server-side.

## 12) Troubleshooting
	•	bind: address already in use 5432
Another Postgres is running. Either stop it or change host bind to 127.0.0.1:55432:5432.
	•	ModuleNotFoundError: psycopg2
Use SQLAlchemy URL with psycopg driver: postgresql+psycopg://....
	•	ValueError: could not convert string to float for HTTP_TIMEOUT_S
Set a numeric value in .env, e.g. HTTP_TIMEOUT_S=15.
	•	HTTP 429 from /v1/weather
Rate limit hit. Wait 1 s or increase rate/burst.
	•	401 Unauthorized on /v1/ingest/event
Missing or invalid HMAC header. Regenerate with current Unix time.

## 13) Roadmap (condensed)
	•	Week 1: foundations (this backend, auth, cache, Overpass/Weather/Route).
	•	Week 2: risk engine, dedupe via pgvector, upload packaging.
	•	Week 3: routing improvements and admin dashboard.
	•	Week 4: evaluation, thresholds, privacy hardening, basic CI.

## 14) License

Add a license file before publishing.

If you want this split into `README.md` and `CONTRIBUTING.md`, say so and I will provide both.