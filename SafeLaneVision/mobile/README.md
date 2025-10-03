# SafeLane Vision — Mobile MVP Skeleton

This directory contains the initial React Native scaffold for the SafeLane Vision rider app.

## What’s included
- React Native 0.74 TypeScript setup with Metro/Babel configs.
- `CameraHUD` component stub using `react-native-vision-camera` and SVG overlays.
- Pipeline scaffolding with `frameScheduler`, `useHazardPipeline`, and a zustand store delivering demo hazard boxes (set `USE_DEMO_PIPELINE=true` in `src/config.ts`).
- Risk scoring helper that mirrors the backend formula for on-device evaluation.
- Design doc for the on-device inference stack in [`docs/InferencePipeline.md`](docs/InferencePipeline.md).

## Quick start
```bash
conda deactivate              # switch to system node environment
cd mobile
npm install                   # or yarn install
npx react-native start
# in a second shell:
npx react-native run-ios      # or run-android
```

### Configure API access
Edit `src/config.ts` with your backend URL, device id, and device secret (or load them from secure storage before building production binaries). Leaving `API_BASE_URL` blank keeps the uploader in dry-run mode.

### Register model paths
Populate `MODEL_PATHS` in `src/config.ts` with the filesystem URIs of your ONNX exports on device (e.g., files copied into `DocumentDirectory`). During startup `App.tsx` calls `registerModelPath` so the pipeline engine can create ONNX Runtime sessions. If the paths are left empty, the HUD falls back to the demo loop.
You can stage the models with `./scripts/sync-models.sh`, which copies the INT8 ONNX files into `mobile/assets/models/`.

### Additional native setup
- `react-native-reanimated` requires the Babel plugin already configured in `babel.config.js`. Remember to add the Reanimated plugin to the end of the plugin list if you customize the file.
- Install pods after adding native dependencies: `cd ios && pod install && cd ..`.
- Persistent secrets default to AsyncStorage. For production, swap to Keychain/Android Keystore within `services/credentials.ts`.
- Generate prompt token tensors for the detector by running `python ../models/export/export_prompt_tokens.py`. This populates `src/pipeline/promptTokens.json` with real token IDs using the OWL-ViT tokenizer.
- To exercise the Week 2 flow without native ONNX binaries, keep `USE_DEMO_PIPELINE=true`. The HUD renders synthetic detections while the uploader, risk scoring, and backend ingestion continue to operate.

### Permissions
The HUD requests camera permission on launch. For Android, ensure the `android/app/src/main/AndroidManifest.xml` includes:
```xml
<uses-permission android:name="android.permission.CAMERA" />
```
For iOS add to `Info.plist`:
```xml
<key>NSCameraUsageDescription</key>
<string>SafeLane Vision needs camera access to detect hazards.</string>
```

## Next steps
1. Wire `frameScheduler.handleFrame` to ONNX Runtime Mobile (OWL-ViT, DeepLab, MiDaS exports).
2. Replace `startDemoLoop` with real scheduler cadence + shared state (Zustand/Recoil).
3. Connect the ingest client to `/v1/ingest/frame` and `/v1/ingest/event` with the HMAC helper.
4. Add state management (Zustand/Recoil) for ride session data, risk history, and settings.
