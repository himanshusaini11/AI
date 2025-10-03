# SafeLane Vision

FastAPI + Postgres/PostGIS backend and a React Native mobile client for bicycle hazard detection. The backend is stable; the mobile app now builds under React Native 0.78 but still runs in demo-mode inference until the ONNX runtime pipeline is fully linked.

_Last validated: 2025-09-23 (UTC)_

## Project status snapshot
- ✅ Backend: FastAPI service with HMAC auth, rate limiting, request audit, Overpass/weather/directions integrations, hazard clustering job, and `/v1/hazards/clustered`+/`/v1/routes/safe` endpoints.
- ✅ Models: OWL-ViT, DeepLabv3, and MiDaS ONNX exports (INT8 + FP32) staged in `models/export/` with quantization/benchmark scripts.
- 🚧 Mobile: RN 0.78 build succeeds after pod fixes, but Metro must be running and the JS bundle still needs to register `SafeLaneVisionMobile`; ONNX runtime headers (`rnworklets/rnworklets.h`) remain the blocker for switching off `USE_DEMO_PIPELINE`.
- 🧭 Next focus: finish RNWorklets include fix, copy INT8 models into the simulator’s documents directory, flip `USE_DEMO_PIPELINE=false`, and hook `/v1/routes/safe` data into the dashboard tiles.

---

## 1. Backend quick start

1. Prerequisites
   - Docker Desktop with Compose
   - `curl`, `psql`, `openssl` (macOS bundles LibreSSL; Homebrew `openssl` works too)
   - Optional: `jq` for pretty output

2. Setup
   ```bash
   cd SafeLaneVision
   cp .env.example .env   # never commit .env
   # edit .env with provider keys / secrets
   ```

3. Run services
   ```bash
   docker compose up -d --build
   ```

4. Apply migrations
   ```bash
   docker compose exec -T db psql -U postgres -d safelane -f /app/migrations/init.sql
   docker compose exec -T db psql -U postgres -d safelane -f /app/migrations/audit.sql
   ```

5. Smoke check
   ```bash
   curl -s http://127.0.0.1:8000/health | jq .
   curl -s http://127.0.0.1:8000/config | jq .
   ```

Key ports: API on `127.0.0.1:8000`, Postgres on `127.0.0.1:55432` (mapped to container `5432`).

---

## 2. Mobile app (React Native 0.78)

All commands assume you’re in the DS Conda environment (`conda activate DS`). Active source lives in `SafeLaneVision/mobile-native`.

1. Install JS deps
   ```bash
   cd SafeLaneVision/mobile-native
   npm install
   ```

2. Install iOS pods
   ```bash
   cd ios
   pod install
   cd ..
   ```

3. Start Metro **before** launching the app (otherwise the simulator shows a blank screen):
   ```bash
   npm run start
   # If you get stale cache errors, use: npx react-native start --reset-cache
   ```

4. In a separate terminal, build and run on the simulator:
   ```bash
   npx react-native run-ios
   ```

If Metro fails to start automatically, open `/SafeLaneVision/mobile-native/node_modules/.generated/launchPackager.command` manually or run the `start` script above. Ensure `AppRegistry.registerComponent('SafeLaneVisionMobile', ...)` is present in `mobile-native/index.js` so the bundle registers correctly.

---

## 3. Model staging for the simulator

The INT8 ONNX artifacts live under `SafeLaneVision/models/export/`. To copy them into the iOS simulator:

```bash
# Stage latest models into mobile assets (keeps naming consistent)
./mobile/scripts/sync-models.sh

# Launch the app at least once so the data container is created
npx react-native run-ios

# Locate the sandbox directory for the app
bundle_id=org.reactjs.native.example.SafeLaneVisionMobile
container=$(xcrun simctl get_app_container booted "$bundle_id" data)

# Copy models into a documents subfolder the runtime can read
mkdir -p "$container/Documents/models"
cp mobile/assets/models/*.onnx "$container/Documents/models/"
```

Update `MODEL_PATHS` in `mobile-native/src/config.ts` to point at the copied files (or the relative asset paths if you keep them bundled). When the ONNX runtime spins up you’ll see `[PipelineEngine] ONNX Runtime sessions ready` in Metro and the HUD will stop relying on the demo loop.

---

## 4. Configuration highlights

- Backend secrets live in `.env`. Sample values are in `.env.example`.
- Mobile configuration: `mobile-native/src/config.ts` controls `API_BASE_URL`, `MODEL_PATHS`, the default routing destination, and the alert-gating thresholds for speed/visibility/precipitation.
- The dashboard overlay polls `/v1/hazards/clustered` and `/v1/routes/safe` once the API base URL is set, and registers real ONNX model paths during app bootstrap.

---

## 5. Known issues & troubleshooting

| Issue | Symptoms | Mitigation |
|-------|----------|------------|
| Metro not running | Simulator shows blank screen, Xcode logs `SafeLaneVisionMobile has not been registered` | Run `npm run start` in `mobile-native`. Ensure Metro is running from the project root before `run-ios`. |
| `rnworklets/rnworklets.h` not found | Xcode build fails when linking ONNX runtime modules | Podfile already sets module flags; remaining fix is to adjust header search/modulemap so RNWorklets exposes `rnworklets.h`. Investigate `node_modules/react-native-worklets-core` include path. |
| `xcrun simctl addmedia` errors | Attempting to add `.onnx` via `addmedia` fails (`File type unsupported`) | Use `xcrun simctl get_app_container` + `cp` to move models into `Documents/` instead of `addmedia`. |
| `/status` connection refused | Xcode logs show HTTP -1004 when app starts | Metro/dev server isn’t running on `localhost:8081`. Start Metro or embed a JS bundle before launching. |

---

## 6. Repository layout (high level)

```
SafeLaneVision/
├── backend/                  # FastAPI service
├── mobile-native/            # React Native 0.78 app (New Architecture)
├── mobile/                   # Legacy RN scaffolding (kept for reference)
├── models/export/            # ONNX models, quantization scripts, tests
├── scripts/, tests/          # Backend jobs and coverage
├── Roadmap.md                # Milestone breakdown
├── Progress_Tracker.md       # ASCII progress dashboard
└── Timeline.md               # Delivery plan
```

---

## 7. Security reminders
- Do **not** commit `.env` or mobile secrets. `.env.example` contains placeholders only.
- Rotate `DEVICE_SECRET` if exposed; regenerate HMAC headers immediately after rotation.
- Treat model artifacts as large binaries—keep them out of Git by using `.gitignore` and download scripts.

---

## 8. Next steps checklist
1. Fix RNWorklets include path so ONNX runtime loads (unblocks disabling `USE_DEMO_PIPELINE`).
2. Stage INT8 models on simulator/device and verify inference through OWL-ViT, DeepLab, and MiDaS via the frame processor.
3. Hook `/v1/routes/safe` into planner UI and expose hazard clusters on the dashboard heatmap.
4. Begin alert gating logic (weather/speed) and expand automated test coverage.

---

Questions or follow-ups? Open an issue or ping the team on the project channel.
