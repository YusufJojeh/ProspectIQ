export type MapLatLng = [number, number];

export type MappableRecord = {
  lat: number | null;
  lng: number | null;
};

export const DEFAULT_MAP_CENTER: MapLatLng = [41.0082, 28.9784];
export const DEFAULT_MAP_ZOOM = 5;
export const DEFAULT_MAP_SINGLE_POINT_ZOOM = 11;
export const DEFAULT_MAP_SELECTED_POINT_ZOOM = 13;
export const DEFAULT_MAP_FIT_PADDING: [number, number] = [28, 28];
export const DEFAULT_MAP_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
export const DEFAULT_MAP_TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export function hasCoordinates<T extends MappableRecord>(
  record: T,
): record is T & { lat: number; lng: number } {
  if (record.lat === null || record.lng === null) {
    return false;
  }
  const lat = Number(record.lat);
  const lng = Number(record.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return false;
  }
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
    return false;
  }
  return true;
}

export function toLatLngTuple(record: { lat: number; lng: number }): [number, number] {
  return [record.lat, record.lng];
}
