import { env } from "@/lib/env";

const TOKEN_KEY = "prospectiq-token";

type JsonBody = unknown;

export async function request<T>(path: string, init: RequestInit = {}, body?: JsonBody): Promise<T> {
  const token = readToken();
  const response = await fetch(`${env.VITE_API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { error?: { detail?: string } }
      | null;
    throw new Error(payload?.error?.detail ?? "Request failed.");
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}

export function persistToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function readToken() {
  return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(TOKEN_KEY);
  }
}
