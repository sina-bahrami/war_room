import type {
  AuthSessionResponse,
  DashboardSummary,
  LoginPayload,
  RegisterPayload,
  TenderFilters,
  TenderListResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.clone().json() as { detail?: string };
    if (payload.detail) {
      return payload.detail;
    }
  } catch {
    // Ignore JSON parse failures and use a generic fallback instead.
  }
  return `Request failed: ${response.status}`;
}

async function fetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers,
  });
  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status);
  }
  return response.json() as Promise<T>;
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers ?? {});
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers,
  });
  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status);
  }
  return response;
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
  await send(`/tenders/admin/run-ingestion${suffix}`, { method: "POST" });
}

export async function login(payload: LoginPayload): Promise<AuthSessionResponse> {
  return fetchJson<AuthSessionResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function register(payload: RegisterPayload): Promise<AuthSessionResponse> {
  return fetchJson<AuthSessionResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getSession(): Promise<AuthSessionResponse> {
  return fetchJson<AuthSessionResponse>("/auth/session");
}

export async function logout(): Promise<void> {
  await send("/auth/logout", { method: "POST" });
}
