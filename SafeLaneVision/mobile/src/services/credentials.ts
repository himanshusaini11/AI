import AsyncStorage from '@react-native-async-storage/async-storage';

const DEVICE_SECRET_KEY = '@safelane/device-secret';

export async function getStoredDeviceSecret(): Promise<string | null> {
  try {
    const value = await AsyncStorage.getItem(DEVICE_SECRET_KEY);
    return value;
  } catch (err) {
    console.warn('[credentials] failed to read device secret', err);
    return null;
  }
}

export async function persistDeviceSecret(secret: string): Promise<void> {
  try {
    await AsyncStorage.setItem(DEVICE_SECRET_KEY, secret);
  } catch (err) {
    console.warn('[credentials] failed to persist device secret', err);
  }
}

export async function clearDeviceSecret(): Promise<void> {
  try {
    await AsyncStorage.removeItem(DEVICE_SECRET_KEY);
  } catch (err) {
    console.warn('[credentials] failed to clear device secret', err);
  }
}
