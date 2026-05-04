import { useTranslation } from "react-i18next";
import { LeadScopeWordmark } from "@/components/brand/logo";

type FooterGroup = { label: string; links: Array<{ label: string; href: string }> };

export function LandingFooter() {
  const { t } = useTranslation();
  const groups = t("landing.footer.groups", { returnObjects: true }) as FooterGroup[];

  return (
    <footer className="relative border-t border-border bg-card/40">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid grid-cols-2 gap-10 lg:grid-cols-6">
          <div className="col-span-2 flex flex-col gap-4">
            <LeadScopeWordmark />
            <p className="max-w-xs text-[13px] leading-relaxed text-muted-foreground">{t("landing.footer.description")}</p>
            <div className="mt-2 flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-md border border-border bg-background/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                SOC 2 Type II
              </span>
              <span className="inline-flex items-center gap-1 rounded-md border border-border bg-background/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                GDPR
              </span>
              <span className="inline-flex items-center gap-1 rounded-md border border-border bg-background/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                CCPA
              </span>
            </div>
          </div>

          {groups.map((group) => (
            <div key={group.label} className="flex flex-col gap-3">
              <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">{group.label}</div>
              <ul className="flex flex-col gap-2">
                {group.links.map((link) => (
                  <li key={link.label}>
                    <a href={link.href} className="text-[13px] text-muted-foreground transition-colors hover:text-foreground">
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col items-start justify-between gap-4 border-t border-border pt-8 text-[11px] text-muted-foreground sm:flex-row sm:items-center">
          <div>{t("landing.footer.copyright")}</div>
          <div className="flex flex-wrap items-center gap-3 font-mono tracking-wider">
            <span className="break-words">us-west-2 / eu-west-1 / ap-south-1</span>
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-flex size-1.5 rounded-full bg-[oklch(var(--evidence))]" />
              {t("landing.footer.status")}
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
