const {getDefaultConfig, mergeConfig} = require('@react-native/metro-config');

const defaultConfig = getDefaultConfig(__dirname);

const {assetExts, sourceExts} = defaultConfig.resolver;

module.exports = mergeConfig(defaultConfig, {
  resolver: {
    assetExts: [...assetExts, 'onnx'],
    sourceExts: [...new Set([...sourceExts, 'ts', 'tsx', 'js', 'jsx', 'json'])],
  },
});
