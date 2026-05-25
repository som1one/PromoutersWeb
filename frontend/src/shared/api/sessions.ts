import { apiRequest } from './http';

export type GeoPingSource = 'start' | 'tracking' | 'finish' | 'photo' | 'manual';

export type GeoPingRecord = {
  id: string;
  session_id: string;
  route_id: string;
  promoter_id: string;
  point_id: string | null;
  point_name: string | null;
  captured_at: string;
  latitude: number;
  longitude: number;
  accuracy_meters: number | null;
  speed_mps: number | null;
  heading_degrees: number | null;
  source: GeoPingSource;
};

export type GeoPingCreatePayload = {
  captured_at: string;
  latitude: number;
  longitude: number;
  accuracy_meters?: number | null;
  speed_mps?: number | null;
  heading_degrees?: number | null;
  source: GeoPingSource;
  point_id?: string | null;
  raw_payload?: Record<string, unknown> | null;
};

export async function fetchSessionGeoPings(accessToken: string, sessionId: string) {
  return apiRequest<GeoPingRecord[]>(`/sessions/${sessionId}/geo-pings`, {
    method: 'GET',
    accessToken,
  });
}

export async function createGeoPing(accessToken: string, sessionId: string, payload: GeoPingCreatePayload) {
  return apiRequest<GeoPingRecord>(`/sessions/${sessionId}/geo-pings`, {
    method: 'POST',
    accessToken,
    body: JSON.stringify(payload),
  });
}
