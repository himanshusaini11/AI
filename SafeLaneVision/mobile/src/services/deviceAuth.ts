import {hmac} from '@noble/hashes/hmac';
import {sha256} from '@noble/hashes/sha256';
import {bytesToHex} from '@noble/hashes/utils';

export interface DeviceSignature {
  header: string;
  ts: number;
}

export function buildDeviceAuthHeader(
  deviceId: string,
  secret: string,
  ts: number = Math.floor(Date.now() / 1000),
): DeviceSignature {
  if (!secret) {
    throw new Error('DEVICE_SECRET is not configured');
  }
  const encoder = new TextEncoder();
  const payload = encoder.encode(`${deviceId}.${ts}`);
  const sig = bytesToHex(hmac(sha256, encoder.encode(secret), payload));
  return {
    header: `Device device_id=${deviceId},ts=${ts},sig=${sig}`,
    ts,
  };
}
