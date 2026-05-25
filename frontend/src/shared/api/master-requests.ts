import { apiRequest } from './http';

export type MasterRequestStatus =
  | 'new'
  | 'accepted'
  | 'on_the_way'
  | 'in_progress'
  | 'completed'
  | 'handed_over'
  | 'cancelled';

export type MasterRequestComment = {
  id: string;
  master_request_id: string;
  author_id: string;
  author_name: string;
  body: string;
  created_at: string;
};

export type MasterRequestStatusLog = {
  id: string;
  master_request_id: string;
  changed_by_id: string | null;
  changed_by_name: string | null;
  from_status: MasterRequestStatus | null;
  to_status: MasterRequestStatus;
  note: string | null;
  created_at: string;
};

export type MasterRequestAttachment = {
  id: string;
  master_request_id: string;
  uploaded_by_id: string;
  uploaded_by_name: string;
  attachment_type: string;
  file_path: string;
  file_url: string;
  filename: string;
  mime_type: string | null;
  size_bytes: number | null;
  comment: string | null;
  created_at: string;
};

export type MasterRequestRecord = {
  id: string;
  branch_id: string;
  branch_name: string;
  requester_id: string;
  requester_name: string;
  assignee_id: string | null;
  assignee_name: string | null;
  title: string;
  description: string | null;
  address: string | null;
  client_name: string | null;
  client_phone: string | null;
  estimated_amount: string | number | null;
  final_amount: string | number | null;
  currency: string;
  status: MasterRequestStatus;
  geo_tracking_enabled: boolean;
  requested_at: string | null;
  accepted_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  handed_over_at: string | null;
  cancelled_at: string | null;
  last_known_latitude: number | null;
  last_known_longitude: number | null;
  last_known_at: string | null;
  comments: MasterRequestComment[];
  status_logs: MasterRequestStatusLog[];
  attachments: MasterRequestAttachment[];
  geo_ping_count: number;
  created_at: string;
  updated_at: string;
};

export type MasterRequestStatusChangePayload = {
  status: MasterRequestStatus;
  note?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  captured_at?: string | null;
};

export async function fetchMasterRequests(accessToken: string, status?: MasterRequestStatus) {
  const search = status ? `?status=${status}` : '';
  return apiRequest<MasterRequestRecord[]>(`/master-requests${search}`, {
    method: 'GET',
    accessToken,
  });
}

export async function fetchMasterRequest(accessToken: string, id: string) {
  return apiRequest<MasterRequestRecord>(`/master-requests/${id}`, {
    method: 'GET',
    accessToken,
  });
}

export async function changeMasterRequestStatus(
  accessToken: string,
  id: string,
  payload: MasterRequestStatusChangePayload,
) {
  return apiRequest<MasterRequestRecord>(`/master-requests/${id}/status`, {
    method: 'POST',
    accessToken,
    body: JSON.stringify(payload),
  });
}

export async function addMasterRequestComment(accessToken: string, id: string, body: string) {
  return apiRequest<MasterRequestComment>(`/master-requests/${id}/comments`, {
    method: 'POST',
    accessToken,
    body: JSON.stringify({ body }),
  });
}

export async function uploadMasterRequestAttachment(
  accessToken: string,
  id: string,
  file: File,
  attachmentType: string = 'bso',
  comment?: string,
) {
  const formData = new FormData();
  formData.set('file', file);
  formData.set('attachment_type', attachmentType);
  if (comment) {
    formData.set('comment', comment);
  }

  return apiRequest<MasterRequestAttachment>(`/master-requests/${id}/attachments`, {
    method: 'POST',
    accessToken,
    body: formData,
  });
}
