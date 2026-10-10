import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { FilePlus2 } from "lucide-react";
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

import { appProposalPath } from "../paths";
import { createProposal, listProposalBrands, proposalKeys } from "../api";

/** Brand picker + create, prefilled from the lead by the API. */
export function NewProposalButton({ leadId }: { leadId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const brandsQuery = useQuery({
    queryKey: proposalKeys.brands,
    queryFn: listProposalBrands,
    staleTime: Infinity,
  });
  const [brandKey, setBrandKey] = useState<string>("");
  const brands = brandsQuery.data?.items ?? [];
  const selected = brandKey || brands[0]?.key || "";

  const mutation = useMutation({
    mutationFn: () => createProposal({ lead_id: leadId, brand_key: selected }),
    onSuccess: (proposal) => {
      void queryClient.invalidateQueries({ queryKey: ["proposals", "list"] });
      navigate(appProposalPath(proposal.public_id));
    },
    onError: (error) => toast.error(resolveErrorMessage(error, t)),
  });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={selected} onValueChange={setBrandKey} disabled={brands.length === 0}>
        <SelectTrigger className="h-9 w-44" aria-label={t("proposals.fields.brand")}>
          <SelectValue placeholder={t("proposals.fields.brand")} />
        </SelectTrigger>
        <SelectContent>
          {brands.map((brand) => (
            <SelectItem key={brand.key} value={brand.key}>
              {brand.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button size="sm" onClick={() => mutation.mutate()} disabled={!selected || mutation.isPending}>
        <FilePlus2 className="size-4" aria-hidden />
        {mutation.isPending ? t("proposals.creating") : t("proposals.newProposal")}
      </Button>
    </div>
  );
}
