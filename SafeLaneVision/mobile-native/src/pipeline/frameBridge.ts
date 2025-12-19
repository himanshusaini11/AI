import type {FrameMeta} from './types';

export type PendingFrame = {
  data: Uint8Array;
  width: number;
  height: number;
  ts: number;
};

const frameQueue: PendingFrame[] = [];

export const MAX_QUEUED_FRAMES = 3;

export function enqueueFrame(buffer: ArrayBuffer | Uint8Array, width: number, height: number) {
  const source = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  const copy = new Uint8Array(source.length);
  copy.set(source);
  if (frameQueue.length >= MAX_QUEUED_FRAMES) {
    frameQueue.shift();
  }
  frameQueue.push({
    data: copy,
    width,
    height,
    ts: Date.now(),
  });
}

export function drainFrames(): PendingFrame[] {
  if (!frameQueue.length) {
    return [];
  }
  return frameQueue.splice(0, frameQueue.length);
}

export function toMeta(packet: PendingFrame): FrameMeta {
  return {
    ts: packet.ts,
    width: packet.width,
    height: packet.height,
  };
}
