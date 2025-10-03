export type PipelineStatus = 'idle' | 'warming' | 'running' | 'error';

export interface FrameMeta {
  ts: number;
  width: number;
  height: number;
}

export interface HazardBox {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  depth: number;
  risk: number;
  classLabel: string;
  laneOffset: number;
  ttc: number;
}

export interface PipelineSummary {
  status: PipelineStatus;
  fps: number;
  lastUpdated: number | null;
}
