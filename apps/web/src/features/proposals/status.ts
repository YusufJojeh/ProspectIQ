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
