import { apiRequest } from './http';

export type BranchRecord = {
  id: string;
  name: string;
  code: string | null;
  city: string | null;
  address: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export async function fetchBranches(accessToken: string) {
  return apiRequest<BranchRecord[]>('/branches', {
    method: 'GET',
    accessToken,
  });
}
