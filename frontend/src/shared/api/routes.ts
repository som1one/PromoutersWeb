import type { PayoutRecord } from './finance';
import { apiRequest } from './http';

export type RouteStatus = 'draft' | 'assigned' | 'in_progress' | 'completed' | 'cancelled';
export type RoutePointType = 'start' | 'checkpoint' | 'stop' | 'finish';
export type SessionStatus = 'planned' | 'active' | 'paused' | 'completed' | 'cancelled';
export type PhotoStatus = 'pending' | 'accepted' | 'rejected';

export type RoutePoint = {
  id: string;
  route_id: string;
  sequence: number;
  name: string;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  point_type: RoutePointType;
  planned_arrival_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type SessionSummary = {
  id: string;
  route_id: string;
  promoter_id: string;
  promoter_name: string;
  status: SessionStatus;
  started_at: string | null;
  ended_at: string | null;
  total_minutes: number | null;
  leaflet_count: number | null;
  summary: string | null;
  started_latitude: number | null;
  started_longitude: number | null;
  finished_latitude: number | null;
  finished_longitude: number | null;
  photo_count: number;
  geo_ping_count: number;
  created_at: string;
  updated_at: string;
};

export type RouteRecord = {
  id: string;
  title: string;
  description: string | null;
  work_date: string;
  planned_start_at: string | null;
  planned_end_at: string | null;
  status: RouteStatus;
  branch_id: string;
  branch_name: string;
  promoter_id: string | null;
  promoter_name: string | null;
  created_by_id: string;
  created_by_name: string;
  payout_rate_id: string | null;
  current_session: SessionSummary | null;
  points: RoutePoint[];
  photo_count: number;
  geo_ping_count: number;
  created_at: string;
  updated_at: string;
};

export type PhotoReport = {
  id: string;
  route_id: string;
  session_id: string;
  promoter_id: string;
  promoter_name: string;
  point_id: string | null;
  point_name: string | null;
  reviewed_by_id: string | null;
  reviewed_by_name: string | null;
  file_path: string;
  file_url: string;
  thumbnail_path: string | null;
  captured_at: string;
  latitude: number | null;
  longitude: number | null;
  notes: string | null;
  status: PhotoStatus;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type RouteReport = {
  route: RouteRecord;
  session: SessionSummary;
  payout: PayoutRecord | null;
  actual_started_at: string | null;
  actual_ended_at: string | null;
  total_minutes: number;
  leaflet_count: number;
  summary: string;
  geo_ping_count: number;
  photo_count: number;
  photos: PhotoReport[];
};

export type AvailablePromoter = {
  id: string;
  full_name: string;
  branch_id: string | null;
  branch_name: string | null;
  status: string;
};

export type RoutePointInput = {
  sequence: number;
  name: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  point_type: RoutePointType;
  planned_arrival_at: string | null;
  notes: string;
};

export type RouteCreatePayload = {
  title: string;
  description: string;
  work_date: string;
  planned_start_at: string | null;
  planned_end_at: string | null;
  branch_id: string;
  payout_rate_id: string | null;
  points: RoutePointInput[];
};

export type RouteUpdatePayload = Partial<RouteCreatePayload>;

export type RouteAssignPayload = {
  promoter_id: string;
};

export type RouteStartPayload = {
  captured_at: string;
  latitude: number;
  longitude: number;
};

export type RouteFinishPayload = RouteStartPayload & {
  leaflet_count: number;
  summary: string;
};

export async function fetchRoutes(accessToken: string, routeStatus?: RouteStatus) {
  const search = routeStatus ? `?status=${routeStatus}` : '';
  return apiRequest<RouteRecord[]>(`/routes${search}`, {
    method: 'GET',
    accessToken,
  });
}

export async function fetchRoute(accessToken: string, routeId: string) {
  return apiRequest<RouteRecord>(`/routes/${routeId}`, {
    method: 'GET',
    accessToken,
  });
}

export async function createRoute(accessToken: string, payload: RouteCreatePayload) {
  return apiRequest<RouteRecord>('/routes', {
    method: 'POST',
    accessToken,
    body: JSON.stringify(payload),
  });
}

export async function updateRoute(accessToken: string, routeId: string, payload: RouteUpdatePayload) {
  return apiRequest<RouteRecord>(`/routes/${routeId}`, {
    method: 'PATCH',
    accessToken,
    body: JSON.stringify(payload),
  });
}

export async function assignRoute(accessToken: string, routeId: string, payload: RouteAssignPayload) {
  return apiRequest<RouteRecord>(`/routes/${routeId}/assign`, {
    method: 'POST',
    accessToken,
    body: JSON.stringify(payload),
  });
}

export async function cancelRoute(accessToken: string, routeId: string) {
  return apiRequest<RouteRecord>(`/routes/${routeId}/cancel`, {
    method: 'POST',
    accessToken,
  });
}

export async function startRoute(accessToken: string, routeId: string, payload: RouteStartPayload) {
  return apiRequest<SessionSummary>(`/routes/${routeId}/start`, {
    method: 'POST',
    accessToken,
    body: JSON.stringify(payload),
  });
}

export async function finishRoute(accessToken: string, routeId: string, payload: RouteFinishPayload) {
  return apiRequest<SessionSummary>(`/routes/${routeId}/finish`, {
    method: 'POST',
    accessToken,
    body: JSON.stringify(payload),
  });
}

export async function fetchRouteSession(accessToken: string, routeId: string) {
  return apiRequest<SessionSummary>(`/routes/${routeId}/session`, {
    method: 'GET',
    accessToken,
  });
}

export async function fetchRoutePhotos(accessToken: string, routeId: string) {
  return apiRequest<PhotoReport[]>(`/routes/${routeId}/photos`, {
    method: 'GET',
    accessToken,
  });
}

export async function fetchRouteReport(accessToken: string, routeId: string) {
  return apiRequest<RouteReport>(`/routes/${routeId}/report`, {
    method: 'GET',
    accessToken,
  });
}

export async function fetchAvailablePromoters(accessToken: string) {
  return apiRequest<AvailablePromoter[]>('/routes/available-promoters', {
    method: 'GET',
    accessToken,
  });
}
