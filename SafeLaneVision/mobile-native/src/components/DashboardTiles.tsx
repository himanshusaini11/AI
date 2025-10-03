import React from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';
import type {FeatureCollection} from 'geojson';

import type {AlertGateStatus, DashboardState} from '../hooks/useDashboardData';

interface Props {
  clusters: FeatureCollection | null;
  route: DashboardState['route'];
  gate: AlertGateStatus;
  loading: boolean;
  error: string | null;
  lastUpdated: number | null;
  onRefresh: () => void;
}

const formatDistance = (meters: number | undefined) => {
  if (!meters) {
    return '—';
  }
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${meters.toFixed(0)} m`;
};

const formatDuration = (seconds: number | undefined) => {
  if (!seconds) {
    return '—';
  }
  const minutes = Math.round(seconds / 60);
  return `${minutes} min`;
};

const formatRelativeTime = (timestamp: number | null) => {
  if (!timestamp) {
    return 'never';
  }
  const diff = Date.now() - timestamp;
  if (diff < 60_000) {
    return `${Math.max(1, Math.round(diff / 1000))}s ago`;
  }
  if (diff < 3_600_000) {
    return `${Math.round(diff / 60_000)} min ago`;
  }
  const hours = Math.round(diff / 3_600_000);
  return `${hours} hr${hours === 1 ? '' : 's'} ago`;
};

export default function DashboardTiles({
  clusters,
  route,
  gate,
  loading,
  error,
  lastUpdated,
  onRefresh,
}: Props) {
  const clusterCount = clusters?.features?.length ?? 0;
  const best = route?.best;
  const hazardWeight = best?.hazard.cluster_weight ?? 0;
  const hazardClusters = best?.hazard.cluster_count ?? 0;
  const improvement = route?.improvement;
  const baseline = route?.baseline;

  return (
    <View style={styles.container}>
      <View style={styles.headingRow}>
        <Text style={styles.heading}>Route & Hazard Snapshot</Text>
        <Pressable
          onPress={onRefresh}
          disabled={loading}
          style={({pressed}) => [styles.refreshButton, pressed && styles.refreshPressed]}>
          <Text style={styles.refreshLabel}>{loading ? 'Refreshing…' : 'Refresh'}</Text>
        </Pressable>
      </View>
      <Text style={styles.subtle}>Updated {formatRelativeTime(lastUpdated)}</Text>
      <View style={styles.row}>
        <View style={styles.tile}>
          <Text style={styles.label}>Clusters nearby</Text>
          <Text style={styles.value}>{clusterCount}</Text>
        </View>
        <View style={styles.tile}>
          <Text style={styles.label}>Route risk</Text>
          <Text style={styles.value}>
            {hazardWeight.toFixed(2)} · {hazardClusters} clusters
          </Text>
          {improvement ? (
            <Text style={styles.delta}>
              {improvement.hazardDelta <= 0 ? '↓' : '↑'}
              {Math.abs(improvement.hazardPercent ?? 0).toFixed(0)}% vs baseline
            </Text>
          ) : null}
        </View>
      </View>
      <View style={styles.row}>
        <View style={styles.tile}>
          <Text style={styles.label}>Distance</Text>
          <Text style={styles.value}>{formatDistance(best?.distance_m)}</Text>
          {baseline ? (
            <Text style={styles.delta}>
              {formatDistance(baseline.distance_m)} baseline
            </Text>
          ) : null}
        </View>
        <View style={styles.tile}>
          <Text style={styles.label}>ETA</Text>
          <Text style={styles.value}>{formatDuration(best?.duration_s)}</Text>
          {baseline ? (
            <Text style={styles.delta}>{formatDuration(baseline.duration_s)} baseline</Text>
          ) : null}
        </View>
      </View>
      <View style={styles.alertTile}>
        <Text style={styles.label}>Alert gating</Text>
        {gate.suppressed ? (
          <View style={styles.alertList}>
            <Text style={styles.alertText}>Alerts paused</Text>
            {gate.reasons.map(reason => (
              <Text key={reason} style={styles.alertReason}>
                • {reason}
              </Text>
            ))}
          </View>
        ) : (
          <Text style={styles.okText}>Alerts armed · conditions nominal</Text>
        )}
      </View>
      {loading ? <Text style={styles.hint}>Refreshing route and hazard data…</Text> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    margin: 16,
    padding: 16,
    borderRadius: 16,
    backgroundColor: '#080b16cc',
    gap: 12,
  },
  headingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heading: {
    color: '#f5f5f5',
    fontSize: 18,
    fontWeight: '600',
  },
  subtle: {
    color: '#9fb3d1',
    fontSize: 12,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  tile: {
    flex: 1,
    padding: 12,
    borderRadius: 12,
    backgroundColor: '#141a29',
    gap: 4,
  },
  label: {
    color: '#9fb3d1',
    fontSize: 13,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  value: {
    color: '#f5f5f5',
    fontSize: 16,
    fontWeight: '500',
  },
  delta: {
    color: '#9fb3d1',
    fontSize: 12,
  },
  alertTile: {
    padding: 12,
    borderRadius: 12,
    backgroundColor: '#1c2231',
    gap: 4,
  },
  alertList: {
    gap: 4,
  },
  alertText: {
    color: '#ffab91',
    fontSize: 14,
  },
  alertReason: {
    color: '#ffccbc',
    fontSize: 13,
  },
  okText: {
    color: '#8bc34a',
    fontSize: 14,
  },
  hint: {
    color: '#9fb3d1',
    fontSize: 12,
  },
  error: {
    color: '#ef9a9a',
    fontSize: 12,
  },
  refreshButton: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: '#1c283d',
  },
  refreshPressed: {
    backgroundColor: '#24324d',
  },
  refreshLabel: {
    color: '#9fb3d1',
    fontSize: 13,
    fontWeight: '600',
  },
});
