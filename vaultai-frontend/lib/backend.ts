const API_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_URL) {
  throw new Error("NEXT_PUBLIC_API_URL not set");
}

export async function apiFetch(
  path: string,
  options: RequestInit = {}
) {
  const token = localStorage.getItem("token");

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  // Always use trailing slash to avoid CORS-breaking 307 redirects from FastAPI/uvicorn.
  // Handles: /expenses  →  /expenses/
  //          /expenses?foo=bar  →  /expenses/?foo=bar
  //          /expenses/  →  /expenses/  (unchanged)
  const [basePath, queryString] = path.split("?");
  const normBase = basePath.endsWith("/") ? basePath : `${basePath}/`;
  const normPath = queryString ? `${normBase}?${queryString}` : normBase;

  const res = await fetch(`${API_URL}${normPath}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
  localStorage.removeItem("token");
  window.location.href = "/auth";
  return;}

  if (!res.ok) {
  const text = await res.text();
  throw new Error(text || res.statusText);
}

// Handle No Content (DELETE etc.)
if (res.status === 204) {
  return null;
}

return res.json();

}

export async function getMe() {
  return apiFetch("/me");
}

export async function registerUser(data: {
  email: string;
  password: string;
}) {
  return apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function loginUser(data: {
  email: string;
  password: string;
}) {
  return apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getExpenses(params?: {
  category?: string;
  sort?: string;
  order?: string;
  from_date?: string;
  to_date?: string;
}) {
  const query = new URLSearchParams();

  if (params?.category) query.append("category", params.category);
  if (params?.sort) query.append("sort", params.sort);
  if (params?.order) query.append("order", params.order);
  if (params?.from_date) query.append("from_date", params.from_date);
  if (params?.to_date) query.append("to_date", params.to_date);

  const qs = query.toString();

  return apiFetch(`/expenses${qs ? `?${qs}` : ""}`);
}


export async function createExpense(data: {
  amount: number;
  category: string;
  description?: string;
  expense_date?: string;
  extra_data?: Record<string, string>;
}) {
  return apiFetch("/expenses", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getExpenseStats(
  from_date?: string,
  to_date?: string
) {
  const query = new URLSearchParams();

  if (from_date) query.append("from_date", from_date);
  if (to_date) query.append("to_date", to_date);

  const qs = query.toString();

  return apiFetch(`/expenses/stats${qs ? `?${qs}` : ""}`);
}

// UPDATE
export async function updateExpense(
  id: number,
  data: {
    amount?: number;
    category?: string;
    description?: string;
    expense_date?: string;
    extra_data?: Record<string, string>;
  }
) {
  return apiFetch(`/expenses/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}


// DELETE
export async function deleteExpense(id: number) {
  return apiFetch(`/expenses/${id}`, {
    method: "DELETE",
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// V2 Extensions - Insight Intelligence Layer
// ─────────────────────────────────────────────────────────────────────────────

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== "undefined" 
    ? localStorage.getItem("token") 
    : null;
  
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function handleResponse(res: Response) {
  if (res.status === 401) {
    throw new Error("unauthorized");
  }
  
  if (!res.ok) {
    const errorText = await res.text().catch(() => "Unknown error");
    throw new Error(`API Error: ${errorText || res.statusText}`);
  }
  
  return res.json();
}

// ─── Insights ────────────────────────────────────────────────────────────────

export async function getInsights() {
  const res = await fetch(`${API_URL}/insights/trends/`, {
    headers: getAuthHeaders(),
  });
  
  if (!res.ok) {
    if (res.status === 401) throw new Error("unauthorized");
    throw new Error(`Failed to fetch insight: ${res.status}`);
  }
  
  return res.json();
}

export async function runInsights() {
  const res = await fetch(`${API_URL}/insights/trends/`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  
  if (!res.ok) {
    if (res.status === 401) throw new Error("unauthorized");
    throw new Error(`Failed to start insight: ${res.status}`);
  }
  
  return res.json();
}

// ─── Executions ──────────────────────────────────────────────────────────────

export async function getExecution(executionId: number) {
  const res = await fetch(`${API_URL}/executions/${executionId}/`, {
    headers: getAuthHeaders(),
  });
  
  if (!res.ok) {
    if (res.status === 401) throw new Error("unauthorized");
    throw new Error(`Failed to fetch execution: ${res.status}`);
  }
  
  return res.json();
}

export async function getSystemMetrics() {
  const res = await fetch(`${API_URL}/system/metrics/`, {
    headers: getAuthHeaders(),
  });
  
  if (!res.ok) {
    if (res.status === 401) throw new Error("unauthorized");
    throw new Error(`Failed to fetch metrics: ${res.status}`);
  }
  
  return res.json();
}


// ─────────────────────────────────────────────────────────────────────────────
// V2 RAG Documents API
// ─────────────────────────────────────────────────────────────────────────────
export async function uploadRagDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  
  const token = typeof window !== "undefined" 
    ? localStorage.getItem("token") 
    : null;
  
  const res = await fetch(`${API_URL}/rag/upload/`, {
    method: "POST",
    headers: {
      // Don't set Content-Type for FormData - browser sets it with boundary
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });
  
  return handleResponse(res);
}

export async function getRagDocuments() {
  const res = await fetch(`${API_URL}/rag/documents/`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  
  const data = await handleResponse(res);
  return Array.isArray(data) ? data : [];
}

export async function deleteRagDocument(docId: number) {
  const res = await fetch(`${API_URL}/rag/documents/${docId}/`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  
  return handleResponse(res);
}

export async function getDocumentStatus(docId: number) {
  const res = await fetch(`${API_URL}/rag/documents/${docId}/status/`, {
    method: "GET",
    headers: getAuthHeaders(),
  });
  
  return handleResponse(res);
}

// ─── V3 — Plans ───────────────────────────────────────────────────────────────
// Endpoints confirmed from Swagger:
//   POST /plans/budget/   — Create Budget Plan
//   POST /plans/invest/   — Create Invest Plan
//   POST /plans/goal/     — Create Goal Plan
//   POST /plans/chat/     — Chat → returns a plan
//   GET  /plans/{id}/     — Get Plan by ID
//   GET  /plans/{id}/trace/ — Get Plan Trace

import type {
  BudgetPlan,
  InvestPlan,
  GoalPlan,
  Plan,
  ChatResponse,
} from "./types/plans";

export async function createBudgetPlan(payload: Record<string, unknown>): Promise<BudgetPlan> {
  const res = await fetch(`${API_URL}/plans/budget/`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function createInvestPlan(payload: Record<string, unknown>): Promise<InvestPlan> {
  const res = await fetch(`${API_URL}/plans/invest/`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function createGoalPlan(payload: Record<string, unknown>): Promise<GoalPlan> {
  const res = await fetch(`${API_URL}/plans/goal/`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/plans/chat/`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ message }),
  });
  return handleResponse(res);
}

export async function getPlan(planId: string): Promise<Plan> {
  const res = await fetch(`${API_URL}/plans/${planId}/`, { headers: getAuthHeaders() });
  return handleResponse(res);
}

export async function getPlanTrace(planId: string) {
  const res = await fetch(`${API_URL}/plans/${planId}/trace/`, { headers: getAuthHeaders() });
  return handleResponse(res);
}

// ─── TypeScript Types ─────────────────────────────────────────────────────────

export interface InsightResponse {
  status: "ready" | "stale" | "unavailable" | "error";
  degraded?: boolean;
  confidence?: number;
  data?: {
    summary: string;
    explanation: string | null;
    metrics: {
      rolling: {
        "30_day_avg": number;
        "60_day_avg": number;
        "90_day_avg": number;
      };
      monthly: {
        current_month: number;
        previous_month: number;
        percent_change: number;
      };
      trend_type: string;
      categories: { category: string; total: number }[];
    };
  };
  artifact_id?: number;
  created_at?: string;
  generated_from_execution?: number;
  stable?: boolean;
  pipeline_version?: string;
  execution_required?: boolean;
  message?: string;
}

export interface ExecutionResponse {
  execution_id: number;
  status: string;
  is_terminal: boolean;
  result?: unknown;
  error?: string;
  error_code?: string;
}

export interface RagDocument {
  id: number;
  filename: string;
  trust_level: number;
  active: boolean;
  uploaded_at: string;
  version: number;
  status?: string;
}

export interface SystemMetrics {
  executions: {
    total: number;
    success: number;
    fallback: number;
    failed: number;
  };
  rates: {
    success_rate: number;
    fallback_rate: number;
    cache_hit_rate: number;
  };
  performance: {
    avg_execution_time_seconds: number;
  };
  artifacts: {
    total: number;
  };
}