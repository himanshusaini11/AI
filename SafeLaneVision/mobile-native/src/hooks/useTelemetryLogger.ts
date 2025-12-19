import {useEffect, useRef} from 'react';

import {useTelemetryStore} from '../state/telemetryStore';

const LOG_INTERVAL_MS = 5000;

export function useTelemetryLogger() {
  const fps = useTelemetryStore(state => state.fps);
  const hazard = useTelemetryStore(state => state.hazard);
  const gating = useTelemetryStore(state => state.gating);
  const lastLoggedRef = useRef(0);

  useEffect(() => {
    const now = Date.now();
    if (now - lastLoggedRef.current < LOG_INTERVAL_MS) {
      return;
    }
    lastLoggedRef.current = now;
    const hazardText = hazard
      ? `${hazard.classLabel} · risk ${(hazard.risk * 100).toFixed(0)}% · depth ${hazard.depth.toFixed(1)}m`
      : 'none';
    const gateText = gating
      ? gating.suppressed
        ? `suppressed (${gating.reasons.join('; ') || 'conditions unmet'})`
        : 'armed'
      : 'unknown';
    console.log(
      '[telemetry] fps=%s hazard=%s gate=%s',
      fps.toFixed(1),
      hazardText,
      gateText,
    );
  }, [fps, hazard, gating]);
}
