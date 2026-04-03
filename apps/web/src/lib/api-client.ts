import { env } from "@/lib/env";
import type { AuthenticatedUser, TokenResponse } from "@/types/api";

const AUTH_SESSION_KEY = "prospectiq-auth-session";
const AUTH_SESSION_EVENT = "prospectiq:auth-session";

let cachedSessionRawValue: string | null | undefined;
let cachedParsedSession: AuthSession | null;

type JsonBody = unknown;
type ApiErrorPayload = {
  error?: {
    code?: string;
    detail?: string;
  };
} | null;

export interface AuthSession {
  accessToken: string;
  tokenType: string;
  expiresAt: string;
  user: AuthenticatedUser;
}

export class ApiError extends Error {
  statusCode: number;
  code: string | null;

  constructor(message: string, statusCode: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.code = code;
  }
}

function isBrowser() {
  return typeof window !== "undefined";
}

function emitAuthSessionChanged() {
  if (isBrowser()) {
    window.dispatchEvent(new CustomEvent(AUTH_SESSION_EVENT));
  }
}

function parseStoredSession(rawValue: string | null): AuthSession | null {
  if (rawValue === cachedSessionRawValue) {
    return cachedParsedSession ?? null;
  }

  cachedSessionRawValue = rawValue;

  if (!rawValue) {
    cachedParsedSession = null;
    return null;
  }

  try {
    cachedParsedSession = JSON.parse(rawValue) as AuthSession;
    return cachedParsedSession;
  } catch {
    cachedParsedSession = null;
    return null;
  }
}

async function buildApiError(response: Response): Promise<ApiError> {
  const payload = (await response.json().catch(() => null)) as ApiErrorPayload;
  return new ApiError(
    payload?.error?.detail ?? "Request failed.",
    response.status,
    payload?.error?.code ?? null,
  );
}

function getActiveSession(): AuthSession | null {
  const session = readStoredSession();
  if (!session) {
    return null;
  }
  if (isSessionExpired(session)) {
    clearSession();
    return null;
  }
  return session;
}

function buildRequestUrl(path: string): string {
  return env.VITE_API_BASE_URL ? `${env.VITE_API_BASE_URL}${path}` : path;
}

export async function request<T>(path: string, init: RequestInit = {}, body?: JsonBody): Promise<T> {
  const session = getActiveSession();
  const response = await fetch(buildRequestUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.accessToken}` } : {}),
      ...(init.headers ?? {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearSession();
    }
    throw await buildApiError(response);
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}

export async function requestBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const session = getActiveSession();
  const response = await fetch(buildRequestUrl(path), {
    ...init,
    headers: {
      ...(session ? { Authorization: `Bearer ${session.accessToken}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearSession();
    }
    throw await buildApiError(response);
  }

  return await response.blob();
}

export function persistSession(response: TokenResponse): AuthSession {
  const session: AuthSession = {
    accessToken: response.access_token,
    tokenType: response.token_type,
    expiresAt: new Date(Date.now() + response.expires_in * 1000).toISOString(),
    user: response.user,
  };

  if (isBrowser()) {
    window.localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
    emitAuthSessionChanged();
  }

  return session;
}

export function readStoredSession(): AuthSession | null {
  if (!isBrowser()) {
    return null;
  }

  return parseStoredSession(window.localStorage.getItem(AUTH_SESSION_KEY));
}

export function readSession(): AuthSession | null {
  return getActiveSession();
}

export function readToken() {
  return getActiveSession()?.accessToken ?? null;
}

export function isSessionExpired(session: AuthSession): boolean {
  return Date.parse(session.expiresAt) <= Date.now();
}

export function clearSession() {
  if (isBrowser()) {
    window.localStorage.removeItem(AUTH_SESSION_KEY);
    emitAuthSessionChanged();
  }
}

export function subscribeAuthSession(listener: () => void) {
  if (!isBrowser()) {
    return () => undefined;
  }

  const handleStorage = (event: StorageEvent) => {
    if (event.key === AUTH_SESSION_KEY || event.key === null) {
      listener();
    }
  };

  const handleSessionEvent = () => {
    listener();
  };

  window.addEventListener("storage", handleStorage);
  window.addEventListener(AUTH_SESSION_EVENT, handleSessionEvent);

  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(AUTH_SESSION_EVENT, handleSessionEvent);
  };
}
