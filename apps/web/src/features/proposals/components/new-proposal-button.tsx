import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { FilePlus2, Palette } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { resolveErrorMessage } from "@/lib/error-messages";

import { appProposalBrandsPath, appProposalPath } from "../paths";
import { createProposal, listProposalBrands, proposalKeys } from "../api";

/** Brand picker + create, prefilled from the lead by the API. */
export function NewProposalButton({ leadId }: { leadId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const brandsQuery = useQuery({
    queryKey: proposalKeys.brandList(false),
    queryFn: () => listProposalBrands(false),
  });
  const [brandId, setBrandId] = useState<string>("");
  const brands = brandsQuery.data?.items ?? [];
  const fallback = brands.find((brand) => brand.is_default) ?? brands[0];
  const selected = brands.some((brand) => brand.public_id === brandId)
    ? brandId
    : (fallback?.public_id ?? "");

  const mutation = useMutation({
    mutationFn: () => createProposal({ lead_id: leadId, brand_id: selected }),
    onSuccess: (proposal) => {
      void queryClient.invalidateQueries({ queryKey: ["proposals", "list"] });
      navigate(appProposalPath(proposal.public_id));
    },
    onError: (error) => toast.error(resolveErrorMessage(error, t)),
  });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={selected} onValueChange={setBrandId} disabled={brands.length === 0}>
        <SelectTrigger className="h-9 w-44" aria-label={t("proposals.fields.brand")}>
          <SelectValue placeholder={t("proposals.fields.brand")} />
        </SelectTrigger>
        <SelectContent>
          {brands.map((brand) => (
            <SelectItem key={brand.public_id} value={brand.public_id}>
              {brand.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button size="sm" onClick={() => mutation.mutate()} disabled={!selected || mutation.isPending}>
        <FilePlus2 className="size-4" aria-hidden />
        {mutation.isPending ? t("proposals.creating") : t("proposals.newProposal")}
      </Button>
      <Button asChild size="icon" variant="ghost" className="size-9">
        <Link to={appProposalBrandsPath()} aria-label={t("proposals.brands.manage")} title={t("proposals.brands.manage")}>
          <Palette className="size-4" aria-hidden />
        </Link>
      </Button>
    </div>
  );
}
