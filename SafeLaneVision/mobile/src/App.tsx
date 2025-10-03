import React, {useEffect} from 'react';
import {SafeAreaView, StatusBar, StyleSheet, View} from 'react-native';
import CameraHUD from './components/CameraHUD';
import {MODEL_PATHS} from './config';
import {registerModelPath} from './pipeline/modelRegistry';

const App = () => {
  useEffect(() => {
    Object.entries(MODEL_PATHS).forEach(([key, uri]) => {
      if (uri) {
        registerModelPath(key as 'owlvit' | 'deeplab' | 'midas', uri);
      }
    });
  }, []);

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="light-content" />
      <View style={styles.container}>
        <CameraHUD />
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
});

export default App;
