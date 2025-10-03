import type {FeatureCollection} from 'geojson';

interface RouteLeg {
  distance_m: number;
  duration_s: number;
  hazard_score: number;
}

interface RouteSummary {
  path: Array<{lat: number; lon: number}>;
  legs: RouteLeg[];
  total_hazard_score: number;
}

export function scoreRoute(
  route: RouteSummary,
  clusters: FeatureCollection,
): number {
  // Placeholder: reduce overall risk by measuring how many cluster centroids are near the path.
  // Real implementation should snap points to the route polyline and weight by cluster severity.
  return route.total_hazard_score + (clusters.features?.length ?? 0);
}

export function pickSaferRoute(
  routes: RouteSummary[],
  clusters: FeatureCollection,
): RouteSummary | null {
  if (!routes.length) {
    return null;
  }
  let best = routes[0];
  let bestScore = scoreRoute(routes[0], clusters);
  for (const candidate of routes.slice(1)) {
    const score = scoreRoute(candidate, clusters);
    if (score < bestScore) {
      best = candidate;
      bestScore = score;
    }
  }
  return best;
}
