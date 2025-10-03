import {InferenceSession, Tensor} from 'onnxruntime-react-native';

import {HazardBox, FrameMeta, PipelineSummary} from './types';
import {calculateRisk} from './risk';
import {usePipelineState} from '../state/pipelineStore';
import {getModelPath} from './modelRegistry';
import promptTokens from './promptTokens.json';

interface DetectorOutputs {
  boxes: HazardBox[];
  summary: PipelineSummary;
}

const DETECTOR_MODEL_KEY = 'owlvit';
const SEGMENTER_MODEL_KEY = 'deeplab';
const DEPTH_MODEL_KEY = 'midas';

class PipelineEngine {
  private detectorSession: InferenceSession | null = null;
  private segmenterSession: InferenceSession | null = null;
  private depthSession: InferenceSession | null = null;
  private ready = false;
  private lastDepth = 4.0;
  private lastDepthTs = Date.now();

  async initialize(): Promise<boolean> {
    if (this.ready || this.detectorSession) {
      return this.ready;
    }
    try {
      const [detectorUri, segUri, depthUri] = [
        getModelPath(DETECTOR_MODEL_KEY),
        getModelPath(SEGMENTER_MODEL_KEY),
        getModelPath(DEPTH_MODEL_KEY),
      ];
      if (!detectorUri || !segUri || !depthUri) {
        console.warn('[PipelineEngine] Model paths missing; staying in demo mode.');
        this.ready = false;
        return false;
      }
      const [detector, segmenter, depth] = await Promise.all([
        InferenceSession.create(detectorUri),
        InferenceSession.create(segUri),
        InferenceSession.create(depthUri),
      ]);
      this.detectorSession = detector;
      this.segmenterSession = segmenter;
      this.depthSession = depth;
      this.ready = true;
      console.log('[PipelineEngine] ONNX Runtime sessions ready');
    } catch (err) {
      console.warn('[PipelineEngine] Failed to initialize models, using demo loop', err);
      this.ready = false;
    }
    return this.ready;
  }

  dispose() {
    this.detectorSession = null;
    this.segmenterSession = null;
    this.depthSession = null;
    this.ready = false;
  }

  isReady() {
    return this.ready;
  }

  async processBuffer(buffer: Uint8Array, meta: FrameMeta): Promise<DetectorOutputs | null> {
    if (!this.ready || !this.detectorSession || !this.segmenterSession || !this.depthSession) {
      return null;
    }
    try {
      const state = usePipelineState.getState();
      const detectorResult = await this.runDetector(buffer, meta);
      if (!detectorResult) {
        return null;
      }
      const {score, bbox, classLabel} = detectorResult;
      const segmentation = await this.runSegmenter(buffer, meta, bbox);
      const depth = await this.runDepth(buffer, meta, bbox);
      const now = meta.ts;
      const depthDelta = depth - this.lastDepth;
      const dt = Math.max(1, (now - this.lastDepthTs) / 1000);
      const depthSlope = depthDelta / dt;
      this.lastDepth = depth;
      this.lastDepthTs = now;

      const laneOffset = segmentation.laneOffset;
      const risk = calculateRisk({
        classLabel,
        score,
        depth,
        laneOffset,
        depthDelta: depthSlope,
      });

      const speed = Math.max(0.1, state.speedMps);
      const ttc = depth / speed;
      const hazard: HazardBox = {
        id: `${classLabel}-${now}`,
        x: bbox[0],
        y: bbox[1],
        width: bbox[2],
        height: bbox[3],
        depth,
        risk,
        classLabel,
        laneOffset,
        ttc,
      };

      const summary: PipelineSummary = {
        status: 'running',
        fps: 12,
        lastUpdated: now,
      };
      return {boxes: [hazard], summary};
    } catch (err) {
      console.warn('[PipelineEngine] Falling back to demo output', err);
      this.ready = false;
      return null;
    }
  }

  private async runDetector(buffer: Uint8Array, meta: FrameMeta): Promise<{score: number; bbox: [number, number, number, number]; classLabel: string} | null> {
    if (!this.detectorSession) {
      return null;
    }
    const input = await convertFrameToTensor(buffer, meta.width, meta.height, 768, 768);
    if (!input) {
      return null;
    }
    const textFeed = getDetectorTextTensor();
    const feeds: Record<string, Tensor> = {
      pixel_values: input.tensor,
      input_ids: textFeed.inputIds,
      attention_mask: textFeed.attentionMask,
    };
    const outputs = await this.detectorSession.run(feeds);
    const logits = outputs.logits.data as Float32Array;
    const boxes = outputs.pred_boxes.data as Float32Array;
    // take highest scoring class across queries
    let bestScore = 0;
    let bestIndex = 0;
    for (let i = 0; i < logits.length; i++) {
      if (logits[i] > bestScore) {
        bestScore = logits[i];
        bestIndex = i;
      }
    }
    const classLabel = detectorPrompts[bestIndex % detectorPrompts.length];
    const bbox: [number, number, number, number] = [
      boxes[bestIndex * 4] * meta.width,
      boxes[bestIndex * 4 + 1] * meta.height,
      Math.max(4, boxes[bestIndex * 4 + 2] * meta.width),
      Math.max(4, boxes[bestIndex * 4 + 3] * meta.height),
    ];
    return {score: Math.min(1, bestScore), bbox, classLabel};
  }

  private async runSegmenter(buffer: Uint8Array, meta: FrameMeta, bbox: [number, number, number, number]) {
    if (!this.segmenterSession) {
      return {laneOffset: 0};
    }
    const input = await convertFrameToTensor(buffer, meta.width, meta.height, 512, 512);
    if (!input) {
      return {laneOffset: 0};
    }
    await this.segmenterSession.run({input: input.tensor});
    // TODO: use segmentation output to compute lane offset.
    return {laneOffset: 0.2};
  }

  private async runDepth(buffer: Uint8Array, meta: FrameMeta, bbox: [number, number, number, number]) {
    if (!this.depthSession) {
      return this.lastDepth;
    }
    const input = await convertFrameToTensor(buffer, meta.width, meta.height, 256, 256);
    if (!input) {
      return this.lastDepth;
    }
    const result = await this.depthSession.run({input: input.tensor});
    const depthMap = result.depth.data as Float32Array;
    const depth = depthMap[0] ?? this.lastDepth;
    return Math.max(0.1, depth);
  }
}

const detectorPrompts = promptTokens.prompts as string[];

interface DetectorTextFeeds {
  inputIds: Tensor;
  attentionMask: Tensor;
}

let cachedTextFeeds: DetectorTextFeeds | null = null;

function getDetectorTextTensor(): DetectorTextFeeds {
  if (cachedTextFeeds) {
    return cachedTextFeeds;
  }
  const idsFlat = promptTokens.input_ids.flat();
  const maskFlat = promptTokens.attention_mask.flat();
  const promptsCount = promptTokens.input_ids.length;
  const seqLen = promptTokens.input_ids[0]?.length ?? 0;
  const ids = new Int32Array(idsFlat);
  const mask = new Int32Array(maskFlat);
  cachedTextFeeds = {
    inputIds: new Tensor('int32', ids, [1, promptsCount, seqLen]),
    attentionMask: new Tensor('int32', mask, [1, promptsCount, seqLen]),
  };
  return cachedTextFeeds;
}

interface TensorWithSize {
  tensor: Tensor;
  width: number;
  height: number;
}

async function convertFrameToTensor(buffer: Uint8Array, width: number, height: number, targetWidth: number, targetHeight: number): Promise<TensorWithSize | null> {
  try {
    const tensorData = new Float32Array(targetWidth * targetHeight * 3);
    const stride = 4; // RGBA
    const xScale = width / targetWidth;
    const yScale = height / targetHeight;
    for (let y = 0; y < targetHeight; y++) {
      for (let x = 0; x < targetWidth; x++) {
        const srcX = Math.floor(x * xScale);
        const srcY = Math.floor(y * yScale);
        const srcIndex = (srcY * width + srcX) * stride;
        const destIndex = y * targetWidth + x;
        tensorData[destIndex] = buffer[srcIndex] / 255;
        tensorData[targetWidth * targetHeight + destIndex] = buffer[srcIndex + 1] / 255;
        tensorData[targetWidth * targetHeight * 2 + destIndex] = buffer[srcIndex + 2] / 255;
      }
    }
    const tensor = new Tensor('float32', tensorData, [1, 3, targetHeight, targetWidth]);
    return {tensor, width, height};
  } catch (err) {
    console.warn('[PipelineEngine] Failed to convert frame to tensor', err);
    return null;
  }
}

export const pipelineEngine = new PipelineEngine();
