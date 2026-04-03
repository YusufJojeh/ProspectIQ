import { persistSession, request } from "@/lib/api-client";
import type { LoginRequest, TokenResponse } from "@/types/api";

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const response = await request<TokenResponse>("/api/v1/auth/login", { method: "POST" }, payload);
  persistSession(response);
  return response;
}

export function getMe() {
  return request<TokenResponse["user"]>("/api/v1/me");
}
