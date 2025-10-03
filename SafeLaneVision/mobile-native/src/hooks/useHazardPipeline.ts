import {useEffect, useRef, useState} from 'react';

import {frameScheduler} from '../pipeline/frameScheduler';
import {HazardBox, PipelineSummary} from '../pipeline/types';
import {uploader} from '../services/uploader';
import {pipelineEngine} from '../pipeline/engine';
import {initializeModelPaths} from '../modelLoader';

export default function useHazardPipeline(): {
  boxes: HazardBox[];
  summary: PipelineSummary;
} {
  const [boxes, setBoxes] = useState<HazardBox[]>([]);
  const [summary, setSummary] = useState<PipelineSummary>({
    status: 'warming',
    fps: 0,
    lastUpdated: null,
  });
  const lastEventRef = useRef<number>(0);

  useEffect(() => {
    let cancelled = false;
    const unsubscribe = frameScheduler.subscribe((nextBoxes, nextSummary) => {
      setBoxes(nextBoxes);
      setSummary(nextSummary);
    });
    initializeModelPaths()
      .then(() => pipelineEngine.initialize())
      .then(ready => {
        if (!ready && !cancelled) {
          frameScheduler.startDemoLoop();
        }
      })
      .catch(() => {
        if (!cancelled) {
          frameScheduler.startDemoLoop();
        }
      });
    return () => {
      cancelled = true;
      unsubscribe();
      frameScheduler.stop();
      pipelineEngine.dispose();
    };
  }, []);

  useEffect(() => {
    if (!summary.lastUpdated) {
      return;
    }
    uploader.enqueueFrame(summary);
    if (!boxes.length) {
      return;
    }
    const top = boxes[0];
    const now = Date.now();
    if (now - lastEventRef.current >= 5000) {
      uploader.enqueueEvent(top);
      if (top.risk > 0) {
        lastEventRef.current = now;
      }
    }
  }, [boxes, summary]);

  return {boxes, summary};
}
