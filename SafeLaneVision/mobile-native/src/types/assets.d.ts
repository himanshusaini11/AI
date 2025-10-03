declare module '*.onnx' {
  const asset: number;
  export default asset;
}

declare module 'react-native/Libraries/Image/resolveAssetSource' {
  import type {ImageResolvedAssetSource} from 'react-native';
  export default function resolveAssetSource(asset: number): ImageResolvedAssetSource | null;
}
