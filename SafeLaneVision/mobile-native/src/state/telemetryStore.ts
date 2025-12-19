import {create} from 'zustand';

import type {HazardBox, PipelineSummary} from '../pipeline/types';

interface HazardSnapshot {
  classLabel: string;
  risk: number;
  depth: number;
  laneOffset: number;
  ts: number;
}

interface GatingSnapshot {
  suppressed: boolean;
  reasons: string[];
}

interface TelemetryState {
  fps: number;
  lastUpdated: number | null;
  hazard: HazardSnapshot | null;
  gating: GatingSnapshot | null;
  setFromPipeline: (summary: PipelineSummary, hazard: HazardBox | undefined) => void;
  setGating: (gating: GatingSnapshot) => void;
}

export const useTelemetryStore = create<TelemetryState>(set => ({
  fps: 0,
  lastUpdated: null,
  hazard: null,
  gating: null,
  setFromPipeline: (summary, hazard) =>
    set({
      fps: summary.fps,
      lastUpdated: summary.lastUpdated,
      hazard: hazard
        ? {
            classLabel: hazard.classLabel,
            risk: hazard.risk,
            depth: hazard.depth,
            laneOffset: hazard.laneOffset,
            ts: summary.lastUpdated ?? Date.now(),
          }
        : null,
    }),
  setGating: gating => set({gating}),
}));
