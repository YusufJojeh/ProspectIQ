import { appPaths } from "@/app/paths";

export function appProposalPath(proposalId: string): string {
  return appPaths.proposalDetail(proposalId);
}
