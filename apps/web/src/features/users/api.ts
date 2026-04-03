import { request } from "@/lib/api-client";
import type { UserListResponse } from "@/types/api";

export function listUsers() {
  return request<UserListResponse>("/api/v1/users");
}
