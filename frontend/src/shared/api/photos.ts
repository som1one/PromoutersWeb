import { apiRequest } from './http';
import type { PhotoReport, PhotoStatus } from './routes';

export type PhotoUploadPayload = {
  file: File;
  capturedAt: string;
  latitude: number;
  longitude: number;
  pointId?: string | null;
  notes?: string;
};

export async function fetchSessionPhotos(accessToken: string, sessionId: string) {
  return apiRequest<PhotoReport[]>(`/sessions/${sessionId}/photos`, {
    method: 'GET',
    accessToken,
  });
}

export async function uploadSessionPhoto(accessToken: string, sessionId: string, payload: PhotoUploadPayload) {
  const formData = new FormData();
  formData.append('file', payload.file);
  formData.append('captured_at', payload.capturedAt);
  formData.append('latitude', String(payload.latitude));
  formData.append('longitude', String(payload.longitude));
  if (payload.pointId) {
    formData.append('point_id', payload.pointId);
  }
  if (payload.notes?.trim()) {
    formData.append('notes', payload.notes.trim());
  }

  return apiRequest<PhotoReport>(`/sessions/${sessionId}/photos`, {
    method: 'POST',
    accessToken,
    body: formData,
  });
}

export async function reviewPhoto(accessToken: string, photoId: string, photoStatus: Exclude<PhotoStatus, 'pending'>) {
  return apiRequest<PhotoReport>(`/photo-reports/${photoId}/review`, {
    method: 'POST',
    accessToken,
    body: JSON.stringify({ status: photoStatus }),
  });
}
