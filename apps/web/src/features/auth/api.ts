import { persistSession, request } from "@/lib/api-client";
import type { LoginRequest, SignupRequest, TokenResponse } from "@/types/api";

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const response = await request<TokenResponse>("/api/v1/auth/login", { method: "POST" }, payload);
  persistSession(response);
  return response;
}

export async function signup(payload: SignupRequest): Promise<TokenResponse> {
  const response = await request<TokenResponse>("/api/v1/auth/signup", { method: "POST" }, payload);
  persistSession(response);
  return response;
}

export function getMe() {
  return request<TokenResponse["user"]>("/api/v1/auth/me");
}

export function logout() {
  return request<{ success: boolean }>("/api/v1/auth/logout", { method: "POST" });
}
