import React from 'react';
import {StyleSheet, Text, View} from 'react-native';
import type {FeatureCollection} from 'geojson';

interface Props {
  clusters: FeatureCollection;
}

export default function DashboardTiles({clusters}: Props) {
  const total = clusters.features?.length ?? 0;
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Hazard Snapshot</Text>
      <Text style={styles.metric}>Clusters in view: {total}</Text>
      <Text style={styles.note}>
        Heatmap/dashboard tiles will render actual geospatial overlays in Week 3.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    borderRadius: 12,
    backgroundColor: '#10131a',
    gap: 8,
  },
  title: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
  metric: {
    color: '#90caf9',
    fontSize: 16,
  },
  note: {
    color: '#ccc',
    fontSize: 13,
  },
});
