import { apiRequest } from './http';

export type UserRecord = {
  id: string;
  username: string;
  email: string;
  phone: string | null;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  status: string;
  is_superuser: boolean;
  role_id: string;
  role_code: string | null;
  role_name: string | null;
  branch_id: string | null;
  branch_name: string | null;
  branch_city: string | null;
  created_at: string;
  updated_at: string;
};

export async function fetchUsers(accessToken: string) {
  return apiRequest<UserRecord[]>('/users', {
    method: 'GET',
    accessToken,
  });
}
