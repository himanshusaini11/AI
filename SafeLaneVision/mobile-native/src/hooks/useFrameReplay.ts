import {useEffect, useState} from 'react';
import {Buffer} from 'buffer';
import RNFS from 'react-native-fs';

import {frameScheduler} from '../pipeline/frameScheduler';
import {FrameMeta} from '../pipeline/types';
import {usePipelineState} from '../state/pipelineStore';
import {DEFAULT_SPEED_MPS} from '../config';

const FRAME_DIR = `${RNFS.DocumentDirectoryPath}/demoFrames`;
const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 720;

function toUint8Array(base64: string) {
  const data = Buffer.from(base64, 'base64');
  return Uint8Array.from(data);
}

export function useFrameReplay(enabled: boolean, fps = 12) {
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const hydrateState = () => {
      const store = usePipelineState.getState();
      store.setSpeed(5); // ~18 km/h cycling speed for playback
    };

    const startPlayback = async () => {
      const exists = await RNFS.exists(FRAME_DIR);
      if (!exists) {
        setAvailable(false);
        return;
      }

      const entries = await RNFS.readDir(FRAME_DIR);
      const frames = entries
        .filter(entry => entry.isFile() && entry.name.endsWith('.rgba'))
        .map(entry => entry.path)
        .sort();

      if (!frames.length) {
        setAvailable(false);
        return;
      }

      setAvailable(true);
      hydrateState();

      let index = 0;
      const frameInterval = Math.max(1, Math.round(1000 / fps));

      const tick = async () => {
        if (cancelled) {
          return;
        }
        const framePath = frames[index];
        try {
          const base64 = await RNFS.readFile(framePath, 'base64');
          const buffer = toUint8Array(base64);
          const meta: FrameMeta = {
            ts: Date.now(),
            width: DEFAULT_WIDTH,
            height: DEFAULT_HEIGHT,
          };
          await frameScheduler.processFrame(buffer, meta);
        } catch (err) {
          console.warn('[FrameReplay] failed to read frame', framePath, err);
        }
        index = (index + 1) % frames.length;
      };

      timer = setInterval(tick, frameInterval);
    };

    startPlayback();

    return () => {
      cancelled = true;
      if (timer) {
        clearInterval(timer);
      }
      usePipelineState.getState().setSpeed(DEFAULT_SPEED_MPS);
    };
  }, [enabled, fps]);

  return available;
}
