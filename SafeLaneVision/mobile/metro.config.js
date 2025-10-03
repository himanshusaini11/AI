const {getDefaultConfig, mergeConfig} = require('@react-native/metro-config');

const defaultConfig = getDefaultConfig(__dirname);

module.exports = mergeConfig(defaultConfig, {
  resolver: {
    sourceExts: ['ts', 'tsx', 'js', 'jsx', 'json']
  }
});
