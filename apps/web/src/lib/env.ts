import { z } from "zod";

declare global {
  interface Window {
    __APP_CONFIG__?: {
      VITE_API_BASE_URL?: string;
    };
  }
}

const envSchema = z.object({
  VITE_API_BASE_URL: z
    .string()
    .refine(
      (value) =>
        value === "" || value.startsWith("/") || /^https?:\/\//.test(value),
      "VITE_API_BASE_URL must be empty, a relative path, or an absolute HTTP(S) URL.",
    ),
});

function normalizeApiBaseUrl(value: string | undefined): string {
  const raw = (value ?? "").trim();
  if (!raw || raw === "/") {
    return "";
  }
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

const runtimeApiBaseUrl =
  typeof window !== "undefined" ? window.__APP_CONFIG__?.VITE_API_BASE_URL : undefined;

export const env = envSchema.parse({
  VITE_API_BASE_URL: normalizeApiBaseUrl(
    runtimeApiBaseUrl ?? import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  ),
});
