import { apiClient } from "@/lib/apiClient";

/**
 * Fetch routes list with optional pagination.
 * @param {{ page?: number, pageSize?: number }} params
 * @returns {Promise<Array>} List of routes
 */
export function fetchRoutes({ page, pageSize } = {}) {
  const params = new URLSearchParams();
  if (page != null) params.set("page", String(page));
  if (pageSize != null) params.set("page_size", String(pageSize));

  const query = params.toString();
  return apiClient.get(`/api/v1/routes${query ? `?${query}` : ""}`);
}

/**
 * Create a new route.
 * @param {object} payload - Route creation data (title, work_date, address, description, promoter_id, etc.)
 * @returns {Promise<object>} Created route
 */
export function createRoute(payload) {
  return apiClient.post("/api/v1/routes", payload);
}

/**
 * Fetch list of available promoters for route assignment.
 * @returns {Promise<Array>} List of available promoters (active, role=promoter)
 */
export function fetchAvailablePromoters() {
  return apiClient.get("/api/v1/routes/available-promoters");
}
