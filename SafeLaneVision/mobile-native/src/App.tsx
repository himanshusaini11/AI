import React from 'react';
import {SafeAreaView, StatusBar, StyleSheet, View} from 'react-native';
import CameraHUD from './components/CameraHUD';
import DashboardTiles from './components/DashboardTiles';
import {useDashboardData} from './hooks/useDashboardData';
import {initializeModelPaths} from './modelLoader';

const App = () => {
  const {clusters, route, gate, loading, error, lastUpdated, refresh} = useDashboardData();

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="light-content" />
      <View style={styles.container}>
        <CameraHUD />
        <View style={styles.overlay} pointerEvents="box-none">
          <DashboardTiles
            clusters={clusters}
            route={route}
            gate={gate}
            loading={loading}
            error={error}
            lastUpdated={lastUpdated}
            onRefresh={refresh}
          />
        </View>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#000',
  },
  container: {
    flex: 1,
  },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
  },
});

export default App;

initializeModelPaths();
