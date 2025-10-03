export const API_BASE_URL = ''; // e.g., 'http://127.0.0.1:8000'
export const DEVICE_ID = 'ios-demo';
export const DEVICE_SECRET = ''; // populate from secure storage in production

export const EVENT_RISK_THRESHOLD = 0.6;
export const FRAME_UPLOAD_INTERVAL_MS = 1000;

export const DEFAULT_GEO = {lat: 43.6532, lon: -79.3832};
export const DEFAULT_SPEED_MPS = 5;
export const DEFAULT_WEATHER = {
  visibility_m: 9000,
  condition: 'Clear',
};

export const MODEL_PATHS = {
  owlvit: '',
  deeplab: '',
  midas: '',
};

// Toggle to keep the mobile pipeline in demo/fallback mode when native ONNX runtime
// binaries are unavailable. When true, the HUD uses synthetic detections so the rest
// of the Week 2 flow (risk evaluation, uploader, backend ingestion) can be exercised
// without the heavy model dependencies.
export const USE_DEMO_PIPELINE = false;
