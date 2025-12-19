import React, {useEffect, useMemo, useState} from 'react';
import {Dimensions, PermissionsAndroid, Platform, StyleSheet, Text, View} from 'react-native';
import {
  Camera,
  type CameraPermissionStatus,
  useCameraDevice,
  useFrameProcessor,
} from 'react-native-vision-camera';
import Svg, {Rect, Text as SvgText} from 'react-native-svg';
import {runOnJS} from 'react-native-reanimated';

import useHazardPipeline from '../hooks/useHazardPipeline';
import {useFrameReplay} from '../hooks/useFrameReplay';
import {enqueueFrame, drainFrames, toMeta} from '../pipeline/frameBridge';
import {frameScheduler} from '../pipeline/frameScheduler';
import {FrameMeta} from '../pipeline/types';

const HUD_FPS = 12;

const requestCameraPermission = async (): Promise<CameraPermissionStatus> => {
  if (Platform.OS === 'android') {
    const result = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.CAMERA);
    return result === PermissionsAndroid.RESULTS.GRANTED ? 'granted' : 'denied';
  }
  return Camera.requestCameraPermission();
};

const CameraHUD: React.FC = () => {
  const device = useCameraDevice('back');
  const [permission, setPermission] = useState<CameraPermissionStatus>('not-determined');
  const {boxes, summary} = useHazardPipeline();
  const replayActive = useFrameReplay(!device || permission !== 'granted');

  useEffect(() => {
    (async () => {
      const status = await Camera.getCameraPermissionStatus();
      if (status !== 'granted') {
        const result = await requestCameraPermission();
        setPermission(result);
        return;
      }
      setPermission(status);
    })();
  }, []);

  const frameProcessor = useFrameProcessor(frame => {
    'worklet';
    const rgba = frame.toArrayBuffer?.();
    if (rgba != null) {
      const bytes = new Uint8Array(rgba);
      runOnJS(enqueueFrame)(bytes, frame.width, frame.height);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const flush = () => {
      if (cancelled) {
        return;
      }
      const frames = drainFrames();
      for (const packet of frames) {
        const meta: FrameMeta = toMeta(packet);
        frameScheduler
          .processFrame(packet.data, meta)
          .catch(err => console.warn('[CameraHUD] frame processing error', err));
      }
      requestAnimationFrame(flush);
    };

    flush();

    return () => {
      cancelled = true;
    };
  }, []);

  const viewBox = useMemo(() => {
    const {width, height} = Dimensions.get('window');
    return {width, height};
  }, []);

  useEffect(() => {
    if (device && permission === 'granted') {
      frameScheduler.stop();
      return;
    }
    if (replayActive) {
      frameScheduler.stop();
      return () => frameScheduler.stop();
    }
    frameScheduler.startDemoLoop(1000 / HUD_FPS);
    return () => frameScheduler.stop();
  }, [device, permission, replayActive]);

  if (!device || permission !== 'granted') {
    return (
      <View style={styles.permissionContainer}>
        <Text style={styles.permissionText}>
          Camera permission is required to start SafeLane Vision.
        </Text>
        <Text style={styles.permissionSubtext}>
          {replayActive
            ? 'Replaying demo video frames for telemetry.'
            : 'Showing demo telemetry.'}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.wrapper}>
      <Camera
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={true}
        video={false}
        photo={false}
        frameProcessor={frameProcessor}
      />
      <Svg
        style={StyleSheet.absoluteFill}
        viewBox={`0 0 ${viewBox.width} ${viewBox.height}`}
        pointerEvents="none">
        {boxes.map(box => (
          <React.Fragment key={box.id}>
            <Rect
              x={box.x}
              y={box.y}
              width={box.width}
              height={box.height}
              stroke={box.risk > 0.6 ? '#ff5252' : '#76ff03'}
              strokeWidth={3}
              fill="transparent"
            />
            <SvgText x={box.x} y={box.y - 12} fill="#fff" fontSize={18}>
              {`${box.depth.toFixed(1)} m · risk ${(box.risk * 100).toFixed(0)}%`}
            </SvgText>
          </React.Fragment>
        ))}
      </Svg>
      <View style={styles.hudBanner}>
        <Text style={styles.hudText}>
          HUD preview @ {HUD_FPS} FPS · pipeline {summary.status}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  wrapper: {
    flex: 1,
    backgroundColor: '#000',
  },
  permissionContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: '#000',
  },
  permissionText: {
    color: '#fff',
    fontSize: 16,
    textAlign: 'center',
  },
  permissionSubtext: {
    color: '#bbb',
    fontSize: 12,
    marginTop: 8,
    textAlign: 'center',
  },
  hudBanner: {
    position: 'absolute',
    bottom: 24,
    left: 16,
    right: 16,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#00000090',
  },
  hudText: {
    color: '#fff',
    fontSize: 14,
    textAlign: 'center',
  },
});

export default CameraHUD;
