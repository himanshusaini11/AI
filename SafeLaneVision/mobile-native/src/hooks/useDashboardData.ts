import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import type {FeatureCollection} from 'geojson';

import {
  ALERT_MAX_PRECIP_MM,
  ALERT_MIN_VISIBILITY_M,
  ALERT_SPEED_MAX_MPS,
  API_BASE_URL,
  DEFAULT_GEO,
  DEFAULT_ROUTE_DEST,
  DEFAULT_WEATHER,
} from '../config';
import {fetchHazardClusters, fetchSafeRoute, SafeRouteSummary} from '../services/routing';
import {usePipelineState} from '../state/pipelineStore';

const CLUSTER_REFRESH_MS = 60_000;
const ROUTE_REFRESH_MS = 120_000;

export interface AlertGateStatus {
  speedOkay: boolean;
  visibilityOkay: boolean;
  precipitationOkay: boolean;
  suppressed: boolean;
  reasons: string[];
}

export interface DashboardState {
  loading: boolean;
  clusters: FeatureCollection | null;
  route: SafeRouteSummary | null;
  gate: AlertGateStatus;
  error: string | null;
  lastUpdated: number | null;
  refresh: () => void;
}

export function useDashboardData(): DashboardState {
  const {geo, speedMps, weather} = usePipelineState();
  const [clusters, setClusters] = useState<FeatureCollection | null>(null);
  const [route, setRoute] = useState<SafeRouteSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!!API_BASE_URL);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => () => {
    isMountedRef.current = false;
  }, []);

  const loadClusters = useCallback(async () => {
    if (!API_BASE_URL) {
      return;
    }
    const origin = geo.lat || geo.lon ? geo : DEFAULT_GEO;
    const result = await fetchHazardClusters(origin);
    if (isMountedRef.current) {
      setClusters(result);
    }
  }, [geo]);

  const loadRoute = useCallback(async () => {
    if (!API_BASE_URL) {
      return;
    }
    const origin = geo.lat || geo.lon ? geo : DEFAULT_GEO;
    const destination = DEFAULT_ROUTE_DEST;
    const result = await fetchSafeRoute(origin, destination);
    if (isMountedRef.current) {
      setRoute(result);
      setError(result ? null : 'Unable to score a safe route');
      setLastUpdated(Date.now());
    }
  }, [geo]);

  const refresh = useCallback(async () => {
    if (!API_BASE_URL) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      await Promise.all([loadClusters(), loadRoute()]);
      if (isMountedRef.current) {
        setLastUpdated(Date.now());
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [loadClusters, loadRoute]);

  useEffect(() => {
    if (!API_BASE_URL) {
      setLoading(false);
      return;
    }

    void refresh();

    const clusterTimer = setInterval(() => {
      void loadClusters();
    }, CLUSTER_REFRESH_MS);
    const routeTimer = setInterval(() => {
      void loadRoute();
    }, ROUTE_REFRESH_MS);

    return () => {
      clearInterval(clusterTimer);
      clearInterval(routeTimer);
    };
  }, [refresh, loadClusters, loadRoute]);

  const gate = useMemo<AlertGateStatus>(() => {
    const sample = weather ?? DEFAULT_WEATHER;
    const visibility = sample.visibility_m ?? DEFAULT_WEATHER.visibility_m ?? 0;
    const precipitation = sample.precipitation_mm ?? 0;
    const reasons: string[] = [];
    const speedOkay = speedMps <= ALERT_SPEED_MAX_MPS;
    const visibilityOkay = visibility >= ALERT_MIN_VISIBILITY_M;
    const precipitationOkay = precipitation <= ALERT_MAX_PRECIP_MM;
    if (!speedOkay) {
      reasons.push('Speed above alert threshold');
    }
    if (!visibilityOkay) {
      reasons.push('Visibility too low');
    }
    if (!precipitationOkay) {
      reasons.push('Heavy precipitation');
    }
    return {
      speedOkay,
      visibilityOkay,
      precipitationOkay,
      suppressed: !(speedOkay && visibilityOkay && precipitationOkay),
      reasons,
    };
  }, [speedMps, weather]);

  return {loading, clusters, route, gate, error, lastUpdated, refresh};
}
