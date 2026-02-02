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
  throw new Error(text || res.statusText);}

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

