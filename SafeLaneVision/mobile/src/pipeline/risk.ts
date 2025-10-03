export interface RiskInput {
  classLabel: string;
  score: number;
  depth: number;
  laneOffset: number;
  depthDelta: number;
}

export function calculateRisk(input: RiskInput): number {
  const inverseDepth = 1 / Math.max(input.depth, 0.5);
  const normalizedDepth = Math.min(1, inverseDepth / 2); // 1/0.5 = 2
  const components = [
    0.4 * input.score,
    0.3 * normalizedDepth,
    0.2 * Math.min(1, Math.abs(input.laneOffset)),
    0.1 * Math.min(1, Math.abs(input.depthDelta)),
  ];
  return Math.max(0, Math.min(1, components.reduce((acc, v) => acc + v, 0)));
}
