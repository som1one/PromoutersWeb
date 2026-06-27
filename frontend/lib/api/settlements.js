import { apiClient } from "@/lib/apiClient";

/**
 * Fetch settlements (payouts) with optional filters.
 * @param {Object} params
 * @param {string|null} params.status - Filter by payout status (calculated, approved, paid)
 * @param {string|null} params.search - Search by promoter name or route address (min 2 chars)
 * @param {number} params.page - Page number (1-based)
 * @param {number} params.pageSize - Items per page (default 50)
 * @returns {Promise<Array>} List of settlement records
 */
export async function fetchSettlements({ status, search, page, pageSize } = {}) {
  const params = new URLSearchParams();

  if (status) {
    params.append("status", status);
  }
  if (search && search.length >= 2) {
    params.append("search", search);
  }
  if (page) {
    params.append("page", String(page));
  }
  if (pageSize) {
    params.append("page_size", String(pageSize));
  }

  const query = params.toString();
  const url = `/api/v1/payouts${query ? `?${query}` : ""}`;
  return apiClient.get(url);
}

/**
 * Approve and pay a settlement in one action (CALCULATED → APPROVED → PAID).
 * @param {string} payoutId - UUID of the payout
 * @returns {Promise<Object>} Updated payout record
 */
export async function approveAndPaySettlement(payoutId) {
  return apiClient.post(`/api/v1/payouts/${payoutId}/approve-and-pay`);
}

/**
 * Mark an approved settlement as paid (APPROVED → PAID).
 * @param {string} payoutId - UUID of the payout
 * @returns {Promise<Object>} Updated payout record
 */
export async function paySettlement(payoutId) {
  return apiClient.post(`/api/v1/payouts/${payoutId}/pay`);
}
