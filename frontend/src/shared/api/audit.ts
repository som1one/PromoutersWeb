import { apiRequest } from './http';

export type AuditLogRecord = {
  id: string;
  actor_user_id: string | null;
  actor_username: string | null;
  branch_id: string | null;
  branch_name: string | null;
  entity_type: string;
  entity_id: string | null;
  action: string;
  ip_address: string | null;
  user_agent: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
};

type AuditLogQuery = {
  action?: string;
  entityType?: string;
  branchId?: string;
  limit?: number;
};

function buildQuery(query: AuditLogQuery) {
  const search = new URLSearchParams();

  if (query.action) {
    search.set('action', query.action);
  }
  if (query.entityType) {
    search.set('entity_type', query.entityType);
  }
  if (query.branchId) {
    search.set('branch_id', query.branchId);
  }
  if (query.limit) {
    search.set('limit', String(query.limit));
  }

  const value = search.toString();
  return value ? `?${value}` : '';
}

export async function fetchAuditLogs(accessToken: string, query: AuditLogQuery = {}) {
  return apiRequest<AuditLogRecord[]>(`/audit-logs${buildQuery(query)}`, {
    method: 'GET',
    accessToken,
  });
}
