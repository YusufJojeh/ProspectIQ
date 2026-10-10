import { appPaths } from "@/app/paths";

export function appProposalPath(proposalId: string): string {
  return appPaths.proposalDetail(proposalId);
}

export function appProposalBrandsPath(): string {
  return appPaths.proposalBrands;
}

/** `new` opens the editor for a brand that does not exist yet. */
export function appProposalBrandPath(brandId: string, template?: string): string {
  const path = appPaths.proposalBrandDetail(brandId);
  return template ? `${path}?template=${encodeURIComponent(template)}` : path;
}
