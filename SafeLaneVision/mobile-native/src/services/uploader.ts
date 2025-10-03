import {
  ALERT_MAX_PRECIP_MM,
  ALERT_MIN_VISIBILITY_M,
  ALERT_SPEED_MAX_MPS,
  API_BASE_URL,
  DEVICE_ID,
  DEVICE_SECRET,
  EVENT_RISK_THRESHOLD,
  FRAME_UPLOAD_INTERVAL_MS,
  DEFAULT_GEO,
  DEFAULT_WEATHER,
} from '../config';
import {HazardBox, PipelineSummary} from '../pipeline/types';
import {buildDeviceAuthHeader} from './deviceAuth';
import {usePipelineState} from '../state/pipelineStore';
import {getStoredDeviceSecret} from './credentials';

type FramePayload = {
  frame_id: string;
  ts: string;
  geo: {lat: number; lon: number};
  speed_mps?: number;
  weather?: Record<string, unknown>;
  meta?: Record<string, unknown>;
};

type EventPayload = {
  ts: string;
  device_id: string;
  geo: {lat: number; lon: number};
  class_: string;
  score: number;
  bbox_xyxy: [number, number, number, number];
  depth_m: number;
  lane_offset_m: number;
  ttc_s: number;
  risk: number;
  frame_id: string;
};

class Uploader {
  private frameQueue: FramePayload[] = [];
  private eventQueue: EventPayload[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastFrameSentAt = 0;
  private cachedSecret: string | null = null;
  private retryDelayMs = 500;

  enqueueFrame(summary: PipelineSummary) {
    if (!API_BASE_URL) {
      return;
    }
    const now = Date.now();
    if (now - this.lastFrameSentAt < FRAME_UPLOAD_INTERVAL_MS) {
      return;
    }
    const state = usePipelineState.getState();
    const payload: FramePayload = {
      frame_id: `frame-${now}`,
      ts: new Date(now).toISOString(),
      geo: state.geo.lat || state.geo.lon ? state.geo : DEFAULT_GEO,
      speed_mps: state.speedMps,
      weather: (state.weather ?? DEFAULT_WEATHER) as Record<string, unknown>,
      meta: {fps: summary.fps, status: summary.status} as Record<string, unknown>,
    };
    this.frameQueue.push(payload);
    this.lastFrameSentAt = now;
    this.ensureTimer();
  }

  enqueueEvent(box: HazardBox) {
    if (!API_BASE_URL || box.risk < EVENT_RISK_THRESHOLD || this.alertsSuppressed()) {
      return;
    }
    const now = Date.now();
    const state = usePipelineState.getState();
    const geo = state.geo.lat || state.geo.lon ? state.geo : DEFAULT_GEO;
    const payload: EventPayload = {
      ts: new Date(now).toISOString(),
      device_id: DEVICE_ID,
      geo,
      class_: box.classLabel,
      score: Math.min(1, Math.max(0, box.risk + 0.2)),
      bbox_xyxy: [box.x, box.y, box.x + box.width, box.y + box.height],
      depth_m: box.depth,
      lane_offset_m: box.laneOffset,
      ttc_s: box.ttc,
      risk: box.risk,
      frame_id: `frame-${now}`,
    };
    this.eventQueue.push(payload);
    this.ensureTimer();
  }

  private ensureTimer() {
    if (!this.timer && API_BASE_URL) {
      this.timer = setInterval(() => {
        void this.flush();
      }, 500);
    }
  }

  private async flush() {
    if (!API_BASE_URL || (!this.frameQueue.length && !this.eventQueue.length)) {
      return;
    }
    const secret = await this.ensureSecret();
    if (!secret) {
      this.stopTimer();
      return;
    }
    const header = buildDeviceAuthHeader(DEVICE_ID, secret).header;
    const frame = this.frameQueue.shift();
    if (frame) {
      await this.postWithRetry('/v1/ingest/frame', frame, header);
    }
    const event = this.eventQueue.shift();
    if (event) {
      await this.postWithRetry('/v1/ingest/event', event, header);
    }
    if (!this.frameQueue.length && !this.eventQueue.length) {
      this.stopTimer();
    }
  }

  private async postWithRetry(path: string, body: FramePayload | EventPayload, authHeader: string, attempt = 0): Promise<void> {
    try {
      const res = await fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: authHeader,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      this.retryDelayMs = 500;
    } catch (err) {
      const delay = Math.min(this.retryDelayMs * Math.pow(2, attempt), 30_000);
      setTimeout(() => {
        if (path.includes('frame')) {
          this.frameQueue.unshift(body as FramePayload);
        } else {
          this.eventQueue.unshift(body as EventPayload);
        }
        this.ensureTimer();
      }, delay);
      this.retryDelayMs = delay;
    }
  }

  private stopTimer() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private async ensureSecret(): Promise<string | null> {
    if (this.cachedSecret) {
      return this.cachedSecret;
    }
    const stored = await getStoredDeviceSecret();
    if (stored) {
      this.cachedSecret = stored;
      return stored;
    }
    if (DEVICE_SECRET) {
      this.cachedSecret = DEVICE_SECRET;
      return DEVICE_SECRET;
    }
    console.warn('[Uploader] Device secret missing; skipping uploads');
    return null;
  }

  private alertsSuppressed(): boolean {
    const state = usePipelineState.getState();
    const speedOk = state.speedMps <= ALERT_SPEED_MAX_MPS;
    const weather = state.weather ?? DEFAULT_WEATHER;
    const visibilityOk =
      (weather.visibility_m ?? DEFAULT_WEATHER.visibility_m ?? Number.POSITIVE_INFINITY) >=
      ALERT_MIN_VISIBILITY_M;
    const precipitationOk =
      (weather.precipitation_mm ?? DEFAULT_WEATHER.precipitation_mm ?? 0) <= ALERT_MAX_PRECIP_MM;
    if (!(speedOk && visibilityOk && precipitationOk)) {
      console.debug('[Uploader] Alerts gated due to conditions', {
        speedOk,
        visibilityOk,
        precipitationOk,
      });
    }
    return !(speedOk && visibilityOk && precipitationOk);
  }
}

export const uploader = new Uploader();
