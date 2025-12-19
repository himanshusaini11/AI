module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['@react-native/babel-preset'],
    plugins: ['react-native-reanimated/plugin'],
  };
};
