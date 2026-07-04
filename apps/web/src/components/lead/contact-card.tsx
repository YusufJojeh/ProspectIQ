import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Building2, ExternalLink, Linkedin, Mail, Users } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeadResponse } from "@/types/api";

function faviconUrl(domain: string | null): string | null {
  if (!domain) return null;
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`;
}

function LeadLogo({ lead }: { lead: LeadResponse }) {
  const [failed, setFailed] = useState(false);
  const fallback = faviconUrl(lead.website_domain);
  const src = !failed ? (lead.logo_url ?? fallback) : fallback;
  if (!src || (failed && !fallback)) {
    return (
      <div className="flex size-12 items-center justify-center rounded-xl border border-border bg-muted/40 text-lg font-semibold uppercase text-muted-foreground">
        {lead.company_name.charAt(0)}
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={lead.company_name}
      className="size-12 rounded-xl border border-border bg-card object-contain"
      onError={() => setFailed(true)}
    />
  );
}

function ContactRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-muted/20 p-3">
      <span className="mt-0.5 text-muted-foreground">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
        <div className="mt-1 break-words text-sm font-medium">{children}</div>
      </div>
    </div>
  );
}

export function LeadContactCard({ lead }: { lead: LeadResponse }) {
  const { t } = useTranslation();
  const missing = <span className="text-muted-foreground">{t("leadContact.notAvailable")}</span>;
  const confidencePercent =
    lead.email_confidence !== null ? Math.round(lead.email_confidence * 100) : null;

  return (
    <Card className="overflow-hidden rounded-[1.5rem] border-border bg-card/95">
      <CardHeader>
        <div className="flex items-center gap-3">
          <LeadLogo lead={lead} />
          <div className="min-w-0">
            <CardTitle>{t("leadContact.title")}</CardTitle>
            <CardDescription>{t("leadContact.description")}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        <ContactRow icon={<Building2 className="size-4" />} label={t("leadContact.industry")}>
          {lead.industry ?? missing}
        </ContactRow>
        <ContactRow icon={<Users className="size-4" />} label={t("leadContact.employeeCount")}>
          {lead.employee_count !== null ? String(lead.employee_count) : missing}
        </ContactRow>
        <ContactRow icon={<Mail className="size-4" />} label={t("leadContact.email")}>
          {lead.email ? (
            <div className="space-y-1">
              <a className="hover:text-[oklch(var(--signal))]" href={`mailto:${lead.email}`}>
                {lead.email}
              </a>
              {confidencePercent !== null ? (
                <div className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-[oklch(var(--signal))]"
                      style={{ width: `${confidencePercent}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {t("leadContact.confidence", { value: confidencePercent })}
                  </span>
                </div>
              ) : null}
            </div>
          ) : (
            missing
          )}
        </ContactRow>
        <ContactRow icon={<Linkedin className="size-4" />} label={t("leadContact.linkedin")}>
          {lead.linkedin_url ? (
            <a
              className="inline-flex items-center gap-1 hover:text-[oklch(var(--signal))]"
              href={lead.linkedin_url}
              target="_blank"
              rel="noreferrer noopener"
            >
              {t("leadContact.openLinkedin")}
              <ExternalLink className="size-3.5" />
            </a>
          ) : (
            missing
          )}
        </ContactRow>
        {lead.ai_opener ? (
          <div className="sm:col-span-2">
            <ContactRow icon={<Mail className="size-4" />} label={t("leadContact.aiOpener")}>
              <p className="leading-6 text-muted-foreground">{lead.ai_opener}</p>
            </ContactRow>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
