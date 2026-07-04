import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Radar,
  Users,
  Sparkles,
  Send,
  Megaphone,
  ShieldCheck,
  ScrollText,
  FileDown,
  Settings,
  BriefcaseBusiness,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { appPaths } from "@/app/paths";
import { useAuthSession } from "@/features/auth/session";
import type { UserRole } from "@/types/api";

const ITEMS = [
  {
    labelKey: "nav.dashboard",
    shortLabelKey: "mobileNav.home",
    href: appPaths.dashboard,
    icon: LayoutDashboard,
  },
  {
    labelKey: "nav.searches",
    shortLabelKey: "mobileNav.jobs",
    href: appPaths.searches,
    icon: Radar,
  },
  {
    labelKey: "nav.leads",
    shortLabelKey: "nav.leads",
    href: appPaths.leads,
    icon: Users,
  },
  {
    labelKey: "nav.aiAnalysis",
    shortLabelKey: "mobileNav.ai",
    href: appPaths.aiAnalysis,
    icon: Sparkles,
  },
  {
    labelKey: "nav.outreach",
    shortLabelKey: "nav.outreach",
    href: appPaths.outreach,
    icon: Send,
  },
  {
    labelKey: "nav.campaigns",
    shortLabelKey: "nav.campaigns",
    href: appPaths.campaigns,
    icon: Megaphone,
  },
  {
    labelKey: "nav.crm",
    shortLabelKey: "nav.crm",
    href: appPaths.crm,
    icon: BriefcaseBusiness,
  },
  {
    labelKey: "nav.admin",
    shortLabelKey: "nav.admin",
    href: appPaths.admin,
    icon: ShieldCheck,
    roles: ["platform_admin"] as UserRole[],
  },
  {
    labelKey: "nav.admin",
    shortLabelKey: "nav.admin",
    href: appPaths.workspaceAdmin,
    icon: ShieldCheck,
    roles: ["account_owner", "admin"] as UserRole[],
  },
  {
    labelKey: "nav.team",
    shortLabelKey: "nav.team",
    href: appPaths.team,
    icon: Users,
  },
  {
    labelKey: "nav.billing",
    shortLabelKey: "nav.billing",
    href: appPaths.billing,
    icon: ShieldCheck,
  },
  {
    labelKey: "nav.invoices",
    shortLabelKey: "nav.invoices",
    href: appPaths.invoices,
    icon: ScrollText,
  },
  {
    labelKey: "nav.usage",
    shortLabelKey: "nav.usage",
    href: appPaths.usage,
    icon: FileDown,
  },
  {
    labelKey: "nav.exports",
    shortLabelKey: "nav.exports",
    href: appPaths.exports,
    icon: FileDown,
  },
  {
    labelKey: "nav.settings",
    shortLabelKey: "nav.settings",
    href: appPaths.settings,
    icon: Settings,
    roles: ["account_owner", "admin"] as UserRole[],
  },
];

export function MobileNav() {
  const { t } = useTranslation();
  const location = useLocation();
  const { user } = useAuthSession();
  const role = user?.role;
  const visibleItems = ITEMS.filter(
    (item) => !item.roles || (role && item.roles.includes(role)),
  );

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-center gap-1 overflow-x-auto border-t border-border bg-background/95 px-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] backdrop-blur-xl lg:hidden"
      aria-label="Primary"
    >
      {visibleItems.map((it) => {
        const active =
          location.pathname === it.href ||
          location.pathname.startsWith(it.href + "/");
        const Icon = it.icon;
        return (
          <NavLink
            key={it.href}
            to={it.href}
            className={cn(
              "flex min-h-12 min-w-[4.5rem] flex-1 flex-col items-center justify-center gap-1 rounded-md px-2 text-[10px] font-medium transition-colors",
              active ? "text-[oklch(var(--signal))]" : "text-muted-foreground",
            )}
            aria-label={t(it.labelKey)}
          >
            <Icon className="size-5" />
            <span className="max-w-full truncate">{t(it.shortLabelKey)}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
