import { apiRequest } from './http';

export type ExpensePlanStatus =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'cancelled';

export type ExpenseDecision = 'pending' | 'approved' | 'rejected' | 'needs_revision';

export type ExpensePlanItem = {
  id: string;
  expense_plan_id: string;
  sequence: number;
  name: string;
  category: string | null;
  quantity: string | number;
  unit_price: string | number;
  amount: string | number;
  note: string | null;
};

export type ExpenseApproval = {
  id: string;
  expense_plan_id: string;
  approver_id: string;
  approver_name: string;
  decision: ExpenseDecision;
  comment: string | null;
  decided_at: string | null;
  created_at: string;
};

export type ExpensePlanRecord = {
  id: string;
  branch_id: string;
  branch_name: string;
  created_by_id: string;
  created_by_name: string;
  title: string;
  period_start: string;
  period_end: string;
  total_amount: string | number;
  currency: string;
  status: ExpensePlanStatus;
  comment: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  items: ExpensePlanItem[];
  approvals: ExpenseApproval[];
  created_at: string;
  updated_at: string;
};

export type ExpensePlanItemPayload = {
  sequence?: number;
  name: string;
  category?: string | null;
  quantity: number;
  unit_price: number;
  note?: string | null;
};

export type ExpensePlanCreatePayload = {
  title?: string;
  branch_id: string;
  period_start: string;
  period_end: string;
  currency?: string;
  comment?: string | null;
  items?: ExpensePlanItemPayload[];
};

export type ExpensePlanDecisionPayload = {
  decision: ExpenseDecision;
  comment?: string | null;
};

export async function fetchExpensePlans(accessToken: string) {
  return apiRequest<ExpensePlanRecord[]>('/expense-plans', {
    method: 'GET',
    accessToken,
  });
}

export async function fetchExpensePlan(accessToken: string, planId: string) {
  return apiRequest<ExpensePlanRecord>(`/expense-plans/${planId}`, {
    method: 'GET',
    accessToken,
  });
}

export async function createExpensePlan(
  accessToken: string,
  payload: ExpensePlanCreatePayload,
) {
  return apiRequest<ExpensePlanRecord>('/expense-plans', {
    method: 'POST',
    accessToken,
    body: JSON.stringify(payload),
  });
}

export async function submitExpensePlan(accessToken: string, planId: string) {
  return apiRequest<ExpensePlanRecord>(`/expense-plans/${planId}/submit`, {
    method: 'POST',
    accessToken,
  });
}

export async function decideExpensePlan(
  accessToken: string,
  planId: string,
  payload: ExpensePlanDecisionPayload,
) {
  return apiRequest<ExpensePlanRecord>(`/expense-plans/${planId}/decision`, {
    method: 'POST',
    accessToken,
    body: JSON.stringify(payload),
  });
}
