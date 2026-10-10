import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";

import { PageHeader } from "@/components/shell/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useAuthSession } from "@/features/auth/session";
import { useDocumentTitle } from "@/hooks/use-document-title";

import { listBrandTemplates, listProposalBrands, proposalKeys } from "../api";
import { BrandSwatch } from "../components/brand-swatch";
import { appProposalBrandPath } from "../paths";
import { canManageBrands } from "../status";

export function ProposalBrandsPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("proposals.brands.title"));
  const { user } = useAuthSession();
  const canManage = canManageBrands(user?.role);
  const [showArchived, setShowArchived] = useState(false);
  const brandsQuery = useQuery({
    queryKey: proposalKeys.brandList(showArchived),
    queryFn: () => listProposalBrands(showArchived),
  });
  const templatesQuery = useQuery({
    queryKey: proposalKeys.brandTemplates,
    queryFn: listBrandTemplates,
    enabled: canManage,
    staleTime: Infinity,
  });

  return (
    <div>
      <PageHeader
        eyebrow={t("proposals.title")}
        title={t("proposals.brands.title")}
        description={t("proposals.brands.description")}
        actions={
          canManage ? (
            <Button asChild size="sm">
              <Link to={appProposalBrandPath("new")}>
                <Plus className="size-4" aria-hidden />
                {t("proposals.brands.newBrand")}
              </Link>
            </Button>
          ) : null
        }
      />
      <div className="mx-auto max-w-5xl space-y-6 px-3 py-4 sm:px-4 lg:px-6">
        <section aria-labelledby="brands-heading" className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="brands-heading" className="text-sm font-semibold">
              {t("proposals.brands.yourBrands")}
            </h2>
            <div className="flex items-center gap-2">
              <Switch id="show-archived" checked={showArchived} onCheckedChange={setShowArchived} />
              <Label htmlFor="show-archived" className="text-sm text-muted-foreground">
                {t("proposals.brands.showArchived")}
              </Label>
            </div>
          </div>
          {brandsQuery.isError ? (
            <QueryStateNotice tone="error" title={t("proposals.brands.loadError")} error={brandsQuery.error} />
          ) : brandsQuery.isPending ? (
            <div className="grid gap-3 sm:grid-cols-2" aria-busy="true">
              <Skeleton className="h-24 rounded-2xl" />
              <Skeleton className="h-24 rounded-2xl" />
            </div>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2">
              {brandsQuery.data.items.map((brand) => (
                <li key={brand.public_id}>
                  <Link
                    to={appProposalBrandPath(brand.public_id)}
                    className="flex items-center gap-4 rounded-2xl border border-border bg-card/95 p-4 transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <BrandSwatch brand={brand} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{brand.name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        <span className="font-mono">{brand.number_prefix}-…</span>
                        {brand.tagline ? ` · ${brand.tagline}` : null}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      {brand.is_default ? <Badge tone="info">{t("proposals.brands.default")}</Badge> : null}
                      {brand.archived ? <Badge tone="neutral">{t("proposals.brands.archived")}</Badge> : null}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {canManage ? (
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle role="heading" aria-level={2}>
                {t("proposals.brands.templatesTitle")}
              </CardTitle>
              <CardDescription>{t("proposals.brands.templatesDescription")}</CardDescription>
            </CardHeader>
            <CardContent>
              {templatesQuery.isPending ? (
                <Skeleton className="h-20 rounded-2xl" />
              ) : (
                <ul className="grid gap-3 sm:grid-cols-3">
                  {(templatesQuery.data?.items ?? []).map((template) => (
                    <li key={template.key}>
                      <Link
                        to={appProposalBrandPath("new", template.key)}
                        className="flex h-full items-center gap-3 rounded-2xl border border-dashed border-border p-3 transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <BrandSwatch brand={template.values} size="sm" />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {t(`proposals.brands.templates.${template.key}.name`, {
                              defaultValue: template.values.name,
                            })}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {t(`proposals.brands.templates.${template.key}.hint`, { defaultValue: "" })}
                          </p>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        ) : (
          <p className="text-sm text-muted-foreground">{t("proposals.brands.readOnly")}</p>
        )}
      </div>
    </div>
  );
}
