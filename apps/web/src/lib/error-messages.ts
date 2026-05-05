import type { TFunction } from "i18next";
import type { ApiError } from "@/lib/api-client";

/**
 * Resolve an API error to a localized message.
 *
 * Maps error.code to i18next key: errors.<code>
 * Falls back to a generic localized error message if code is not found.
 */
export function resolveErrorMessage(error: unknown, t: TFunction): string {
  if (!error) {
    return t("errors.generic");
  }

  const apiError = error as ApiError | null;
  if (!apiError?.code) {
    return t("errors.generic");
  }

  // Try the specific error code first
  const errorKey = `errors.${apiError.code}`;
  const message = t(errorKey);

  // If the translation key wasn't found, t() returns the key itself
  // So check if we got back a translated string or the key
  if (message === errorKey) {
    // Key doesn't exist, fall back to generic
    return t("errors.generic");
  }

  return message;
}

/**
 * Get a readable error message from any error type.
 * Used in catch blocks and error boundaries.
 */
export function getErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof Error) {
    // Try API error first
    if ("code" in error) {
      return resolveErrorMessage(error, t);
    }
    // Fall back to error message
    return error.message || t("errors.generic");
  }

  return t("errors.generic");
}
