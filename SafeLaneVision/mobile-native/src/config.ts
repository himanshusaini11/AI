export const API_BASE_URL = process.env.API_BASE_URL ?? 'http://192.168.1.2:8000';
export const DEVICE_ID = 'ios-demo';
export const DEVICE_SECRET = '9b2208a7d058c4a53a722b0661fd21f692bef5eb6f876e3fb3bc43f028bd890e';

export const EVENT_RISK_THRESHOLD = 0.6;
export const FRAME_UPLOAD_INTERVAL_MS = 1000;

export const DEFAULT_GEO = {lat: 43.6532, lon: -79.3832};
export const DEFAULT_ROUTE_DEST = {lat: 43.6629, lon: -79.3957};
export const DEFAULT_SPEED_MPS = 5;
export const DEFAULT_WEATHER = {
  visibility_m: 9000,
  condition: 'Clear',
  precipitation_mm: 0,
};

export const ALERT_SPEED_MAX_MPS = 11.2; // ~25 mph
export const ALERT_MIN_VISIBILITY_M = 500;
export const ALERT_MAX_PRECIP_MM = 2.5;

export const MODEL_OVERRIDES: Partial<Record<'owlvit' | 'deeplab' | 'midas', string>> = {
  // Provide absolute paths here to override the bundled models if needed.
};
