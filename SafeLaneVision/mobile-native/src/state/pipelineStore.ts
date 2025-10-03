import {create} from 'zustand';

import {DEFAULT_GEO, DEFAULT_SPEED_MPS, DEFAULT_WEATHER} from '../config';

export interface GeoPoint {
  lat: number;
  lon: number;
}

export interface WeatherSample {
  visibility_m?: number;
  precipitation_mm?: number;
  condition?: string;
}

interface PipelineState {
  geo: GeoPoint;
  speedMps: number;
  weather: WeatherSample | null;
  setGeo: (geo: GeoPoint) => void;
  setSpeed: (speed: number) => void;
  setWeather: (weather: WeatherSample | null) => void;
}

export const usePipelineState = create<PipelineState>(set => ({
  geo: DEFAULT_GEO,
  speedMps: DEFAULT_SPEED_MPS,
  weather: DEFAULT_WEATHER,
  setGeo: geo => set({geo}),
  setSpeed: speed => set({speedMps: speed}),
  setWeather: weather => set({weather}),
}));
