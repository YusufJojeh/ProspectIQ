import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { Copy, FileDown } from "lucide-react";
import { toast } from "sonner";

import { appPaths } from "@/app/paths";
import { PageHeader } from "@/components/shell/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useDocumentTitle } from "@/hooks/use-document-title";
import type { LeadAudit, ProposalBrand, ProposalLanguage } from "@/types/proposals";

import { getLeadAudit, listProposalBrands, proposalKeys } from "../api";
import { auditCoverEmail, auditLabels, findingText } from "../audit-labels";
import { AuditDocument, type AuditDocumentData } from "../components/audit-document";
import { ScaledPage } from "../components/proposal-document";
import { appProposalBrandsPath } from "../paths";

export function LeadAuditPage() {
  const { t } = useTranslation();
  const { leadId = "" } = useParams();
  const auditQuery = useQuery({
    queryKey: proposalKeys.audit(leadId),
    queryFn: () => getLeadAudit(leadId),
    enabled: leadId !== "",
  });
  const brandsQuery = useQuery({
    queryKey: proposalKeys.brandList(false),
    queryFn: () => listProposalBrands(false),
  });
  useDocumentTitle(auditQuery.data ? `${t("proposals.audit.title")} · ${auditQuery.data.company_name}` : t("proposals.audit.title"));

  const error = auditQuery.error ?? brandsQuery.error;
  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-3 py-6">
        <QueryStateNotice tone="error" title={t("proposals.audit.loadError")} error={error} />
      </div>
    );
  }
  if (!auditQuery.data || !brandsQuery.data) {
    return (
      <div className="mx-auto grid max-w-7xl gap-6 px-3 py-6 sm:px-4 lg:px-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Skeleton className="h-[30rem] rounded-[1.5rem]" />
        <Skeleton className="h-[40rem] rounded-[1.5rem]" />
      </div>
    );
  }
  return <AuditWorkspace audit={auditQuery.data} brands={brandsQuery.data.items} />;
}

function AuditWorkspace({ audit, brands }: { audit: LeadAudit; brands: ProposalBrand[] }) {
  const { t, i18n } = useTranslation();
  const [brandId, setBrandId] = useState(() => (brands.find((brand) => brand.is_default) ?? brands[0])?.public_id ?? "");
  const [language, setLanguage] = useState<ProposalLanguage>(i18n.language.startsWith("ar") ? "ar" : "en");
  // Reps choose what the prospect sees: every check starts included, and
  // collected evidence is opt-in because it was written for internal use.
  const [excluded, setExcluded] = useState<Set<string>>(() => new Set());
  const [showBenchmark, setShowBenchmark] = useState(true);
  const [includedEvidence, setIncludedEvidence] = useState<Set<number>>(() => new Set());
  const [note, setNote] = useState("");
  const [nextStep, setNextStep] = useState("");
  const brand = brands.find((item) => item.public_id === brandId) ?? brands[0];

  const data: AuditDocumentData | null = useMemo(
    () =>
      brand
        ? {
            brand,
            language,
            companyName: audit.company_name,
            category: audit.category,
            city: audit.city,
            websiteUrl: audit.website_url,
            generatedOn: audit.generated_on,
            findings: audit.findings.filter((finding) => !excluded.has(finding.key)),
            benchmark: showBenchmark ? audit.benchmark : null,
            evidence: audit.evidence.filter((_, index) => includedEvidence.has(index)),
            note,
            nextStep,
          }
        : null,
    [audit, brand, language, excluded, showBenchmark, includedEvidence, note, nextStep],
  );

  function toggle<T>(set: Set<T>, value: T, on: boolean): Set<T> {
    const next = new Set(set);
    if (on) next.add(value);
    else next.delete(value);
    return next;
  }

  function downloadPdf() {
    const previous = document.title;
    document.title = `${auditLabels(language).footerKind} - ${audit.company_name}`.replace(/[\\/:*?"<>|]/g, "");
    window.addEventListener("afterprint", () => (document.title = previous), { once: true });
    window.print();
  }

  async function copyCoverEmail() {
    if (!data) return;
    const email = auditCoverEmail({
      language,
      companyName: audit.company_name,
      findings: data.findings,
      senderName: data.brand.name,
    });
    try {
      await navigator.clipboard.writeText(email);
      toast.success(t("proposals.coverCopied"));
    } catch {
      toast.error(t("proposals.copyFailed"));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("proposals.audit.eyebrow")}
        title={audit.company_name}
        description={t("proposals.audit.description")}
        actions={
          <Button asChild size="sm" variant="ghost">
            <Link to={appPaths.leadDetail(audit.lead_id)}>{t("proposals.openLead")}</Link>
          </Button>
        }
      />
      <div className="mx-auto grid max-w-7xl gap-6 px-3 py-4 sm:px-4 lg:px-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card className="h-fit rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle role="heading" aria-level={2}>
              {t("proposals.audit.customize")}
            </CardTitle>
            <CardDescription>{t("proposals.audit.customizeDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="audit-brand">{t("proposals.fields.brand")}</Label>
                <Select value={brand?.public_id ?? ""} onValueChange={setBrandId}>
                  <SelectTrigger id="audit-brand">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {brands.map((item) => (
                      <SelectItem key={item.public_id} value={item.public_id}>
                        {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Link to={appProposalBrandsPath()} className="text-xs text-muted-foreground underline-offset-4 hover:underline">
                  {t("proposals.brands.manage")}
                </Link>
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium">{t("proposals.fields.language")}</p>
                <ToggleGroup
                  type="single"
                  variant="outline"
                  value={language}
                  onValueChange={(value) => value && setLanguage(value as ProposalLanguage)}
                  aria-label={t("proposals.fields.language")}
                >
                  <ToggleGroupItem value="en" className="px-3">
                    {t("proposals.languages.en")}
                  </ToggleGroupItem>
                  <ToggleGroupItem value="ar" className="px-3">
                    {t("proposals.languages.ar")}
                  </ToggleGroupItem>
                </ToggleGroup>
              </div>
            </div>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">{t("proposals.audit.checks")}</legend>
              {audit.findings.map((finding) => {
                const id = `audit-finding-${finding.key}`;
                return (
                  <div key={finding.key} className="flex items-start gap-2">
                    <Checkbox
                      id={id}
                      checked={!excluded.has(finding.key)}
                      onCheckedChange={(checked) => setExcluded((set) => toggle(set, finding.key, checked !== true))}
                    />
                    <Label htmlFor={id} className="text-sm font-normal leading-snug">
                      {findingText(finding, language).title}
                      <span className="ms-2 text-xs text-muted-foreground">
                        {t(`proposals.audit.status.${finding.status}`)}
                      </span>
                    </Label>
                  </div>
                );
              })}
            </fieldset>

            <div className="space-y-2">
              <p className="text-sm font-medium">{t("proposals.audit.benchmark")}</p>
              {audit.benchmark ? (
                <div className="flex items-start gap-2">
                  <Checkbox
                    id="audit-benchmark"
                    checked={showBenchmark}
                    onCheckedChange={(checked) => setShowBenchmark(checked === true)}
                  />
                  <Label htmlFor="audit-benchmark" className="text-sm font-normal leading-snug">
                    {t("proposals.audit.benchmarkInclude", { count: audit.benchmark.peer_count })}
                  </Label>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">{t("proposals.audit.benchmarkUnavailable")}</p>
              )}
            </div>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">{t("proposals.audit.evidence")}</legend>
              {audit.evidence.length === 0 ? (
                <p className="text-xs text-muted-foreground">{t("proposals.audit.noEvidence")}</p>
              ) : (
                <>
                  <p className="text-xs text-muted-foreground">{t("proposals.audit.evidenceHint")}</p>
                  {audit.evidence.map((item, index) => {
                    const id = `audit-evidence-${index}`;
                    return (
                      <div key={id} className="flex items-start gap-2">
                        <Checkbox
                          id={id}
                          checked={includedEvidence.has(index)}
                          onCheckedChange={(checked) =>
                            setIncludedEvidence((set) => toggle(set, index, checked === true))
                          }
                        />
                        <Label htmlFor={id} className="text-sm font-normal leading-snug">
                          {item.text}
                        </Label>
                      </div>
                    );
                  })}
                </>
              )}
            </fieldset>

            <div className="space-y-2">
              <Label htmlFor="audit-note">{t("proposals.audit.note")}</Label>
              <Textarea
                id="audit-note"
                rows={3}
                maxLength={600}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder={t("proposals.audit.notePlaceholder")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="audit-next-step">{t("proposals.audit.nextStep")}</Label>
              <Textarea
                id="audit-next-step"
                rows={2}
                maxLength={300}
                value={nextStep}
                onChange={(event) => setNextStep(event.target.value)}
                placeholder={auditLabels(language).nextStepDefault}
              />
            </div>

            <div className="flex flex-wrap gap-2 border-t border-border pt-4">
              <Button onClick={downloadPdf} disabled={!data}>
                <FileDown className="size-4" aria-hidden />
                {t("proposals.downloadPdf")}
              </Button>
              <Button variant="outline" className="bg-transparent" onClick={() => void copyCoverEmail()} disabled={!data}>
                <Copy className="size-4" aria-hidden />
                {t("proposals.copyCoverEmail")}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">{t("proposals.audit.privacyHint")}</p>
          </CardContent>
        </Card>

        <section aria-label={t("proposals.previewLabel")} className="min-w-0 xl:sticky xl:top-4 xl:self-start">
          {data ? (
            <ScaledPage>
              <AuditDocument data={data} printable />
            </ScaledPage>
          ) : null}
        </section>
      </div>
    </div>
  );
}
