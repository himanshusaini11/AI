import {Platform} from 'react-native';
import RNFS from 'react-native-fs';

import {MODEL_OVERRIDES} from './config';
import {ModelKey, registerModelPath} from './pipeline/modelRegistry';

const MODEL_FILENAMES: Record<ModelKey, string> = {
  owlvit: 'owlvit.ort',
  deeplab: 'deeplab_mnv3.ort',
  midas: 'midas_small.ort',
};

const DEST_DIR = `${RNFS.DocumentDirectoryPath}/models`;
let initPromise: Promise<void> | null = null;

export function initializeModelPaths(): Promise<void> {
  if (!initPromise) {
    initPromise = initialiseAsync().catch(err => {
      console.warn('[Models] Failed to initialise model paths', err);
      initPromise = null; // allow retry on next invocation
      throw err;
    });
  }
  return initPromise ?? Promise.resolve();
}

async function initialiseAsync() {
  try {
    await RNFS.mkdir(DEST_DIR);
  } catch (err) {
    // Directory may already exist; ignore errors thrown for EEXIST
  }

  for (const [key, filename] of Object.entries(MODEL_FILENAMES) as [ModelKey, string][]) {
    const destPath = `${DEST_DIR}/${filename}`;
    const destExists = await RNFS.exists(destPath);
    if (!destExists) {
      const copied = await copyBundledModel(filename, destPath);
      if (!copied) {
        console.warn('[Models] Failed to stage bundled model', {filename});
      }
    }
    registerModelPath(key, destPath);
  }

  Object.entries(MODEL_OVERRIDES).forEach(([key, uri]) => {
    if (uri) {
      registerModelPath(key as ModelKey, normalisePath(uri));
    }
  });
}

async function copyBundledModel(filename: string, destPath: string): Promise<boolean> {
  if (Platform.OS === 'ios') {
    return copyFromIOSBundle(filename, destPath);
  }
  return copyFromAndroidAssets(filename, destPath);
}

async function copyFromIOSBundle(filename: string, destPath: string): Promise<boolean> {
  const candidates = [
    `${RNFS.MainBundlePath}/${filename}`,
    `${RNFS.MainBundlePath}/Models/${filename}`,
  ];

  for (const candidate of candidates) {
    if (await RNFS.exists(candidate)) {
      await RNFS.copyFile(candidate, destPath);
      return true;
    }
  }
  console.warn('[Models] iOS bundle model missing', {filename, candidates});
  return false;
}

async function copyFromAndroidAssets(filename: string, destPath: string): Promise<boolean> {
  const assetPath = `models/${filename}`;
  try {
    await RNFS.copyFileAssets(assetPath, destPath);
    return true;
  } catch (err) {
    console.warn('[Models] Android asset copy failed', {filename, assetPath, err});
    return false;
  }
}

function normalisePath(input: string): string {
  return input.startsWith('file://') ? input.replace('file://', '') : input;
}
