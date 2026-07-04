import type { TFunction } from "i18next";
import type {
  LeadScoreBand,
  LeadStatus,
  UserRole,
  UserStatus,
  WebsitePreference,
} from "@/types/api";

export function leadStatusLabel(t: TFunction, status: LeadStatus) {
  return t(`leads.statuses.${status}`);
}

export function scoreBandLabel(
  t: TFunction,
  band: LeadScoreBand | null | undefined,
) {
  return band ? t(`leads.bands.${band}`) : t("leads.unscored");
}

export function userRoleLabel(t: TFunction, role: UserRole) {
  return t(`team.roles.${role}`);
}

export function userStatusLabel(t: TFunction, status: UserStatus) {
  return t(`team.statuses.${status}`);
}

export function websitePreferenceLabel(
  t: TFunction,
  preference: WebsitePreference,
) {
  return t(`searches.websitePreferences.${preference}`);
}

export function professionLabel(t: TFunction, profession: string) {
  return t(`settings.professions.${profession}`, {
    defaultValue: profession.replace(/_/g, " "),
  });
}

export function searchJobStatusLabel(t: TFunction, status: string) {
  return t(`searches.statuses.${status}`, {
    defaultValue: status.replace(/_/g, " "),
  });
}

export function discoveryRuntimeLabel(t: TFunction, runtime: string) {
  return t(`searches.runtimes.${runtime}`, { defaultValue: runtime });
}

export function billingCycleLabel(t: TFunction, cycle: string) {
  return t(`billing.cycles.${cycle}`, { defaultValue: cycle });
}

export function billingStatusLabel(t: TFunction, status: string) {
  return t(`billing.statuses.${status}`, {
    defaultValue: status.replace(/_/g, " "),
  });
}

export function usageMetricLabel(t: TFunction, metric: string) {
  return t(`billing.metrics.${metric}`, {
    defaultValue: metric.replace(/_/g, " "),
  });
}
