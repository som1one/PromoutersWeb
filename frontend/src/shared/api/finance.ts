import { apiRequest } from './http';

export type MoneyValue = string | number;
export type PayoutStatus = 'draft' | 'calculated' | 'approved' | 'paid' | 'cancelled';
export type PayoutRateType = 'hourly' | 'per_leaflet' | 'fixed_shift';

export type PayoutRecord = {
  id: string;
  route_id: string;
  route_title: string;
  work_date: string;
  session_id: string | null;
  promoter_id: string;
  promoter_name: string;
  payout_rate_id: string | null;
  payout_rate_name: string | null;
  payout_rate_type: PayoutRateType | null;
  amount: MoneyValue;
  currency: string;
  units: MoneyValue | null;
  notes: string | null;
  status: PayoutStatus;
  calculated_at: string | null;
  approved_at: string | null;
  paid_at: string | null;
  calculation_details: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type PayoutSummaryRecord = {
  promoter_id: string;
  promoter_name: string;
  payout_count: number;
  total_amount: MoneyValue;
  currency: string;
  payouts: PayoutRecord[];
};

type PayoutQuery = {
  promoterId?: string;
  routeId?: string;
  branchId?: string;
  status?: PayoutStatus;
};

function buildQuery(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      search.set(key, value);
    }
  });

  const query = search.toString();
  return query ? `?${query}` : '';
}

export async function fetchPayouts(accessToken: string, query: PayoutQuery = {}) {
  return apiRequest<PayoutRecord[]>(
    `/payouts${buildQuery({
      promoter_id: query.promoterId,
      route_id: query.routeId,
      branch_id: query.branchId,
      status: query.status,
    })}`,
    {
      method: 'GET',
      accessToken,
    },
  );
}

export async function fetchPayoutSummaryByPromoter(accessToken: string, branchId?: string) {
  return apiRequest<PayoutSummaryRecord[]>(
    `/payouts/summary/by-promoter${buildQuery({ branch_id: branchId })}`,
    {
      method: 'GET',
      accessToken,
    },
  );
}
