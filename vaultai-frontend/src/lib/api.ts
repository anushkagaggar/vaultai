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

  const res = await fetch(`${API_URL}${path}`, {
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

// --- V2 Phase 5: Intelligence API Layer ---

export interface Insight {
  id: string;
  summary: string;
  type: string;
  explanation: string;
  confidence: number;
  status: 'trusted' | 'degraded';
  metrics: Record<string, any>;
  pipelineVersion: string;
  generatedAt: string;
}

export interface ExecutionRun {
  id: string;
  status: 'pending' | 'running' | 'success' | 'fallback' | 'failed';
  startedAt: string;
  completedAt?: string;
}

export interface Document {
  id: string;
  name: string;
  trustLevel: string;
  status: 'parsed' | 'failed' | 'processing';
}

// Helper to handle API responses
const handleResponse = async (res: Response) => {
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
  return res.json();
};

export const getInsights = async (): Promise<Insight[]> => 
  fetch('/api/insights').then(handleResponse);

export const getInsight = async (id: string): Promise<Insight> => 
  fetch(`/api/insights/${id}`).then(handleResponse);

export const runInsight = async (type?: string): Promise<{ executionId: string }> => 
  fetch('/api/insights/run', { 
    method: 'POST', 
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type }) 
  }).then(handleResponse);

export const getExecution = async (id: string): Promise<ExecutionRun> => 
  fetch(`/api/insights/status/${id}`).then(handleResponse);

export const getExecutions = async (): Promise<ExecutionRun[]> => 
  fetch('/api/insights/executions').then(handleResponse);

export const uploadDoc = async (file: File): Promise<Document> => {
  const formData = new FormData();
  formData.append('file', file);
  return fetch('/api/rag/upload', { method: 'POST', body: formData }).then(handleResponse);
};

export const getDocs = async (): Promise<Document[]> => 
  fetch('/api/rag/documents').then(handleResponse);

export const deleteDoc = async (id: string): Promise<void> => 
  fetch(`/api/rag/documents/${id}`, { method: 'DELETE' }).then(handleResponse);