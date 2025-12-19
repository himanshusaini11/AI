import {InferenceSession, Tensor} from 'onnxruntime-react-native';
import RNFS from 'react-native-fs';
import {Buffer} from 'buffer';

import {HazardBox, FrameMeta, PipelineSummary} from './types';
import {calculateRisk} from './risk';
import {usePipelineState} from '../state/pipelineStore';
import {getModelPath, ModelKey} from './modelRegistry';
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
  private lastFrameTs: number | null = null;
  private fpsEma = 0;

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
      await logModelStats([
        {key: DETECTOR_MODEL_KEY, uri: detectorUri},
        {key: SEGMENTER_MODEL_KEY, uri: segUri},
        {key: DEPTH_MODEL_KEY, uri: depthUri},
      ]);
      const sessionOptions = {
        executionProviders: ['cpu'],
        logSeverityLevel: 0 as const,
        logVerbosityLevel: 1,
        logId: 'SafeLaneVision',
      };
      const detector = await createSessionWithDiagnostics(
        DETECTOR_MODEL_KEY,
        detectorUri,
        sessionOptions,
      );
      const segmenter = await createSessionWithDiagnostics(
        SEGMENTER_MODEL_KEY,
        segUri,
        sessionOptions,
      );
      const depth = await createSessionWithDiagnostics(
        DEPTH_MODEL_KEY,
        depthUri,
        sessionOptions,
      );
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
      if (this.lastFrameTs != null) {
        const intervalS = Math.max(1, now - this.lastFrameTs) / 1000;
        const instFps = intervalS > 0 ? 1 / intervalS : this.fpsEma;
        this.fpsEma = this.fpsEma ? this.fpsEma * 0.8 + instFps * 0.2 : instFps;
      }
      this.lastFrameTs = now;

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
        fps: Number((this.fpsEma || 0).toFixed(1)),
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

async function logModelStats(models: {key: ModelKey; uri: string}[]) {
  for (const model of models) {
    try {
      const exists = await RNFS.exists(model.uri);
      if (!exists) {
        console.warn('[PipelineEngine] Model path missing', model);
        continue;
      }
      const stat = await RNFS.stat(model.uri).catch(() => null);
      console.log('[PipelineEngine] Model ready', {
        key: model.key,
        uri: model.uri,
        size: stat ? Number(stat.size) : null,
        lastModified: stat?.mtime,
      });
    } catch (err) {
      console.warn('[PipelineEngine] Failed to inspect model file', model, err);
    }
  }
}

async function createSessionWithDiagnostics(
  key: ModelKey,
  uri: string,
  options: Parameters<typeof InferenceSession.create>[1],
) {
  const candidates = await resolveCandidatePaths(uri);
  let lastErr: unknown = null;
  for (const candidate of candidates) {
    console.log('[PipelineEngine] ORT creating (path)', {key, uri: candidate});
    try {
      const session = await InferenceSession.create(candidate, options);
      console.log('[PipelineEngine] ORT session ready', {key, source: 'path', candidate});
      return session;
    } catch (pathErr) {
      console.warn('[PipelineEngine] ORT create failed (path)', {key, uri: candidate, pathErr});
      lastErr = pathErr;
      try {
        const bytes = await loadModelBytes(candidate);
        console.log('[PipelineEngine] ORT creating (bytes)', {key, length: bytes.length, candidate});
        const session = await InferenceSession.create(bytes, options);
        console.log('[PipelineEngine] ORT session ready', {key, source: 'bytes', candidate});
        return session;
      } catch (bytesErr) {
        console.warn('[PipelineEngine] ORT create failed (bytes)', {
          key,
          candidate,
          bytesErr,
        });
        lastErr = bytesErr;
      }
    }
  }
  throw lastErr ?? new Error('Failed to create session');
}

async function loadModelBytes(uri: string): Promise<Uint8Array> {
  const data = await RNFS.readFile(uri, 'base64');
  const buffer = Buffer.from(data, 'base64');
  return Uint8Array.from(buffer);
}

async function resolveCandidatePaths(uri: string): Promise<string[]> {
  const candidates = new Set<string>();
  candidates.add(uri);
  const filename = uri.split('/').pop();
  if (filename) {
    const bundleCandidate = `${RNFS.MainBundlePath}/${filename}`;
    if (await RNFS.exists(bundleCandidate)) {
      candidates.add(bundleCandidate);
    }
    const assetCandidate = `${RNFS.MainBundlePath}/assets/models/${filename}`;
    if (await RNFS.exists(assetCandidate)) {
      candidates.add(assetCandidate);
    }
    const documentCandidate = `${RNFS.DocumentDirectoryPath}/models/${filename}`;
    if (await RNFS.exists(documentCandidate)) {
      candidates.add(documentCandidate);
    }
  }
  return Array.from(candidates);
}

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
