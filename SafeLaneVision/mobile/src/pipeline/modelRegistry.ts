export type ModelKey = 'owlvit' | 'deeplab' | 'midas';

const modelPaths: Partial<Record<ModelKey, string>> = {};

export function registerModelPath(key: ModelKey, uri: string) {
  modelPaths[key] = uri;
}

export function getModelPath(key: ModelKey): string | undefined {
  return modelPaths[key];
}
