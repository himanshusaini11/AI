import type {FeatureCollection} from 'geojson';

import {API_BASE_URL} from '../config';

export type HazardScore = {
  cluster_count: number;
  cluster_weight: number;
};

type SafeRouteResponse = {
  best: {
    distance: number;
    duration: number;
    hazard_score: HazardScore;
  };
  alternatives: Array<{
    distance: number;
    duration: number;
    hazard_score: HazardScore;
  }>;
};

export interface RouteCandidate {
  distance_m: number;
  duration_s: number;
  hazard: HazardScore;
}

export interface SafeRouteImprovement {
  hazardDelta: number;
  hazardPercent: number | null;
  distanceDelta_m: number;
  durationDelta_s: number;
}

export interface SafeRouteSummary {
  best: RouteCandidate;
  baseline: RouteCandidate | null;
  alternatives: RouteCandidate[];
  improvement: SafeRouteImprovement | null;
}

type ClusterQueryOptions = {
  radius?: number;
  sinceMinutes?: number;
  limit?: number;
  classes?: string[];
};

export async function fetchHazardClusters(
  origin: {lat: number; lon: number},
  options: ClusterQueryOptions = {},
): Promise<FeatureCollection | null> {
  if (!API_BASE_URL) {
    return null;
  }
  const params = new URLSearchParams({
    lat: origin.lat.toString(),
    lon: origin.lon.toString(),
    r: Math.max(1, options.radius ?? 800).toString(),
    since_min: Math.max(1, options.sinceMinutes ?? 1440).toString(),
    limit: Math.max(1, options.limit ?? 50).toString(),
  });
  if (options.classes?.length) {
    params.set('classes', options.classes.join(','));
  }

  try {
    const res = await fetch(`${API_BASE_URL}/v1/hazards/clustered?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return (await res.json()) as FeatureCollection;
  } catch (err) {
    console.warn('[routing] failed to load hazard clusters', err);
    return null;
  }
}

export async function fetchSafeRoute(
  origin: {lat: number; lon: number},
  destination: {lat: number; lon: number},
): Promise<SafeRouteSummary | null> {
  if (!API_BASE_URL) {
    return null;
  }
  const params = new URLSearchParams({
    lat1: origin.lat.toString(),
    lon1: origin.lon.toString(),
    lat2: destination.lat.toString(),
    lon2: destination.lon.toString(),
  });
  try {
    const res = await fetch(`${API_BASE_URL}/v1/routes/safe?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = (await res.json()) as SafeRouteResponse;
    if (!data.best) {
      return null;
    }

    const mapCandidate = (entry: SafeRouteResponse['best']): RouteCandidate => ({
      distance_m: entry.distance,
      duration_s: entry.duration,
      hazard: entry.hazard_score ?? {cluster_count: 0, cluster_weight: 0},
    });

    const best = mapCandidate(data.best);
    const epsilon = 1e-3;
    const isSameCandidate = (a: RouteCandidate, b: RouteCandidate) =>
      Math.abs(a.distance_m - b.distance_m) < 1 &&
      Math.abs(a.duration_s - b.duration_s) < 1 &&
      Math.abs(a.hazard.cluster_weight - b.hazard.cluster_weight) < epsilon;

    const alternatives = (data.alternatives ?? [])
      .map(mapCandidate)
      .filter(candidate => !isSameCandidate(candidate, best));

    const baseline = alternatives.length ? alternatives[0] : null;
    const improvement = baseline
      ? {
          hazardDelta: baseline.hazard.cluster_weight - best.hazard.cluster_weight,
          hazardPercent:
            baseline.hazard.cluster_weight > epsilon
              ? ((baseline.hazard.cluster_weight - best.hazard.cluster_weight) /
                  baseline.hazard.cluster_weight) *
                100
              : null,
          distanceDelta_m: baseline.distance_m - best.distance_m,
          durationDelta_s: baseline.duration_s - best.duration_s,
        }
      : null;

    return {
      best,
      baseline,
      alternatives,
      improvement,
    };
  } catch (err) {
    console.warn('[routing] failed to fetch safe route', err);
    return null;
  }
}
