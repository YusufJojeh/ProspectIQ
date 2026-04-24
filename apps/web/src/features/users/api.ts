import { request } from "@/lib/api-client";
import type {
  UserCreateRequest,
  UserDetailResponse,
  UserListResponse,
  UserPasswordResetRequest,
  UserUpdateRequest,
} from "@/types/api";

export function listUsers() {
  return request<UserListResponse>("/api/v1/users");
}

export function getUser(userId: string) {
  return request<UserDetailResponse>(`/api/v1/users/${userId}`);
}

export function createUser(payload: UserCreateRequest) {
  return request<UserDetailResponse | UserListResponse["items"][number]>("/api/v1/users", { method: "POST" }, payload);
}

export function updateUser(userId: string, payload: UserUpdateRequest) {
  return request<UserDetailResponse>(`/api/v1/users/${userId}`, { method: "PATCH" }, payload);
}

export function resetUserPassword(userId: string, payload: UserPasswordResetRequest) {
  return request<UserDetailResponse>(`/api/v1/users/${userId}/reset-password`, { method: "POST" }, payload);
}
