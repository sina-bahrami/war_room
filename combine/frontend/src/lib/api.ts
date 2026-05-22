import type { DashboardSummary, TenderFilters, TenderListResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return fetchJson<DashboardSummary>("/dashboard/summary");
}

export async function getTenders(
  filters: TenderFilters,
  options: { internalOnly?: boolean } = {},
): Promise<TenderListResponse> {
  const params = new URLSearchParams();
  if (filters.query) params.set("query", filters.query);
  if (filters.source) params.set("source", filters.source);
  if (filters.status) params.set("status", filters.status);
  if (filters.state) params.set("state", filters.state);
  if (filters.sector_primary) params.set("sector_primary", filters.sector_primary);
  if (filters.value_band) params.set("value_band", filters.value_band);
  if (filters.closing_from) params.set("closing_from", filters.closing_from);
  if (filters.closing_to) params.set("closing_to", filters.closing_to);
  if (filters.view_bucket) params.set("view_bucket", filters.view_bucket);
  if (filters.value_known === "known") params.set("value_known", "true");
  if (filters.value_known === "unknown") params.set("value_known", "false");
  if (typeof options.internalOnly === "boolean") {
    params.set("internal_only", String(options.internalOnly));
  }
  return fetchJson<TenderListResponse>(`/tenders?${params.toString()}`);
}

export async function triggerIngestion(source = ""): Promise<void> {
  const suffix = source ? `?source=${encodeURIComponent(source)}` : "";
  const response = await fetch(`${API_BASE}/tenders/admin/run-ingestion${suffix}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Ingestion failed: ${response.status}`);
  }
}
