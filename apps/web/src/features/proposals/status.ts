import type { BadgeTone } from "@/components/ui/badge";
import type { ProposalStatus } from "@/types/proposals";

export function proposalStatusTone(status: ProposalStatus): BadgeTone {
  switch (status) {
    case "draft":
      return "neutral";
    case "ready":
      return "info";
    case "sent":
      return "signal";
    case "accepted":
      return "success";
    case "declined":
      return "danger";
  }
}

export function isEditable(status: ProposalStatus): boolean {
  return status === "draft" || status === "ready";
}

/** Mirrors the API: brands are designed by workspace owners and admins. */
export function canManageBrands(role: string | undefined): boolean {
  return role === "account_owner" || role === "admin" || role === "platform_admin";
}
