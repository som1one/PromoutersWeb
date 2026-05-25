import { apiRequest } from './http';

export type NotificationStatus = 'pending' | 'sent' | 'read' | 'failed';

export type NotificationRecord = {
  id: string;
  user_id: string;
  title: string;
  body: string;
  channel: string;
  status: NotificationStatus;
  payload: Record<string, unknown> | null;
  scheduled_at: string | null;
  sent_at: string | null;
  read_at: string | null;
  created_at: string;
  updated_at: string;
};

type NotificationReadResponse = {
  success: boolean;
  notification: NotificationRecord;
};

export async function fetchNotifications(accessToken: string) {
  return apiRequest<NotificationRecord[]>('/notifications', {
    method: 'GET',
    accessToken,
  });
}

export async function markNotificationRead(accessToken: string, notificationId: string) {
  const response = await apiRequest<NotificationReadResponse>(`/notifications/${notificationId}/read`, {
    method: 'POST',
    accessToken,
  });

  return response.notification;
}
