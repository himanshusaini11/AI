import {calculateRisk} from './risk';
import {HazardBox, FrameMeta, PipelineSummary} from './types';
import {pipelineEngine} from './engine';
import {usePipelineState} from '../state/pipelineStore';

type BoxesListener = (boxes: HazardBox[], summary: PipelineSummary) => void;

const DEMO_CLASSES = ['pothole', 'debris', 'cone'];

export class FrameScheduler {
  private listeners = new Set<BoxesListener>();
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastUpdated: number | null = null;

  subscribe(listener: BoxesListener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async processFrame(buffer: Uint8Array, meta: FrameMeta) {
    const result = await pipelineEngine.processBuffer(buffer, meta);
    if (!result) {
      return;
    }
    this.lastUpdated = result.summary.lastUpdated;
    this.emit(result.boxes, result.summary);
  }

  startDemoLoop(intervalMs = 500) {
    if (this.timer) {
      return;
    }
    this.timer = setInterval(() => {
      const now = Date.now();
      const state = usePipelineState.getState();
      const speed = Math.max(0.1, state.speedMps);
      const laneOffset = 0.2;
      const depth = 4.3;
      const ttc = depth / speed;
      const risk = calculateRisk({
        classLabel: DEMO_CLASSES[now % DEMO_CLASSES.length],
        score: 0.7,
        depth,
        laneOffset,
        depthDelta: 0.1,
      });
      const hazard: HazardBox = {
        id: `demo-${now}`,
        x: 180,
        y: 280,
        width: 220,
        height: 160,
        depth,
        risk,
        classLabel: DEMO_CLASSES[now % DEMO_CLASSES.length],
        laneOffset,
        ttc,
      };
      this.lastUpdated = now;
      const summary: PipelineSummary = {
        status: pipelineEngine.isReady() ? 'running' : 'warming',
        fps: 12,
        lastUpdated: this.lastUpdated,
      };
      this.emit([hazard], summary);
    }, intervalMs);
  }

  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    const summary: PipelineSummary = {
      status: pipelineEngine.isReady() ? 'running' : 'idle',
      fps: 0,
      lastUpdated: this.lastUpdated,
    };
    this.emit([], summary);
  }

  private emit(boxes: HazardBox[], summary: PipelineSummary) {
    for (const listener of this.listeners) {
      listener(boxes, summary);
    }
  }
}

export const frameScheduler = new FrameScheduler();
