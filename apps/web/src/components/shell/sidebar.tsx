import { NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  Radar,
  Users,
  Sparkles,
  Send,
  ShieldCheck,
  ScrollText,
  FileDown,
  Settings,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LeadScopeWordmark } from "@/components/brand/logo";
import { ScrollArea } from "@/components/ui/scroll-area";
import { appPaths } from "@/app/paths";
import { useAuthSession } from "@/features/auth/session";
import type { UserRole } from "@/types/api";

type NavItem = {
  labelKey: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  roles?: UserRole[];
  permission?: string;
};

const PRIMARY: NavItem[] = [
  { labelKey: "nav.dashboard", href: appPaths.dashboard, icon: LayoutDashboard },
  { labelKey: "nav.searches", href: appPaths.searches, icon: Radar },
  { labelKey: "nav.leads", href: appPaths.leads, icon: Users },
  { labelKey: "nav.aiAnalysis", href: appPaths.aiAnalysis, icon: Sparkles },
  { labelKey: "nav.outreach", href: appPaths.outreach, icon: Send },
];

const GOVERN: NavItem[] = [
  { labelKey: "nav.admin", href: appPaths.admin, icon: ShieldCheck, roles: ["account_owner", "admin"] },
  { labelKey: "nav.team", href: appPaths.team, icon: Users, roles: ["account_owner", "admin"] },
  { labelKey: "nav.billing", href: appPaths.billing, icon: ShieldCheck, roles: ["account_owner", "admin"] },
  { labelKey: "nav.invoices", href: appPaths.invoices, icon: ScrollText, roles: ["account_owner", "admin"] },
  { labelKey: "nav.usage", href: appPaths.usage, icon: FileDown, roles: ["account_owner", "admin"] },
  { labelKey: "nav.auditLogs", href: appPaths.auditLogs, icon: ScrollText, roles: ["account_owner", "admin"] },
  { labelKey: "nav.exports", href: appPaths.exports, icon: FileDown },
  { labelKey: "nav.settings", href: appPaths.settings, icon: Settings, roles: ["account_owner", "admin"] },
];

export function AppSidebar() {
  const { t } = useTranslation();
  const location = useLocation();
  const { user } = useAuthSession();
  const role = user?.role;

  function renderItem(item: NavItem) {
    if (item.roles && (!role || !item.roles.includes(role))) return null;
    if (item.permission && !(user?.permissions?.includes(item.permission) ?? false)) return null;
    const active = location.pathname === item.href || location.pathname.startsWith(item.href + "/");
    const Icon = item.icon;
    return (
      <NavLink
        key={item.href}
        to={item.href}
        end={item.href === appPaths.dashboard}
        className={cn(
          "group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
          active
            ? "bg-sidebar-accent text-sidebar-accent-foreground"
            : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
        )}
      >
        {active && (
          <motion.span
            layoutId="sidebar-active"
            transition={{ type: "spring", stiffness: 400, damping: 34 }}
            className="absolute inset-y-1.5 start-0 w-0.5 rounded-full bg-[oklch(var(--signal))] shadow-[0_0_10px_oklch(var(--signal)/0.7)]"
          />
        )}
        <Icon className={cn("size-4 shrink-0", active && "text-[oklch(var(--signal))]")} />
        <span className="flex-1 font-medium tracking-tight">{t(item.labelKey)}</span>
        {item.badge && (
          <span className="font-mono text-[10px] font-medium text-muted-foreground tabular-nums">{item.badge}</span>
        )}
      </NavLink>
    );
  }

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:flex rtl:border-r-0 rtl:border-l">
      <div className="flex h-14 items-center border-b border-sidebar-border px-4">
        <LeadScopeWordmark />
      </div>

      <div className="px-3 py-3">
        <div className="flex w-full items-center gap-2 rounded-md border border-sidebar-border bg-sidebar-accent/40 px-2.5 py-2 text-left text-xs">
          <div className="flex size-7 items-center justify-center rounded-md bg-[oklch(var(--signal)/0.12)] font-semibold text-[oklch(var(--signal))]">
            N
          </div>
          <div className="flex-1">
            <div className="text-[13px] font-medium leading-tight text-foreground">{user?.workspace_name ?? "Workspace"}</div>
            <div className="text-[11px] leading-tight text-muted-foreground">{user?.workspace_slug ?? "isolated-account"}</div>
          </div>
          <ChevronRight className="size-3.5 text-muted-foreground" />
        </div>
      </div>

      <ScrollArea className="flex-1 px-2">
        <nav className="flex flex-col gap-0.5">
          <div className="px-2 pb-1.5 pt-2 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground/70">
            {t("nav.operate")}
          </div>
          {PRIMARY.map(renderItem)}

          <div className="mt-3 px-2 pb-1.5 pt-2 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground/70">
            {t("nav.govern")}
          </div>
          {GOVERN.map(renderItem)}
        </nav>

        <div className="mx-2 mt-6 rounded-lg border border-sidebar-border bg-gradient-to-b from-sidebar-accent/40 to-transparent p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-[oklch(var(--signal))]">
            <Sparkles className="size-3.5" /> Scoring · v12
          </div>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Deterministic weights shipped 2d ago. Review velocity +0.05.
          </p>
          <NavLink
            to={appPaths.admin}
            className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-foreground hover:text-[oklch(var(--signal))]"
          >
            View changelog <ChevronRight className="size-3" />
          </NavLink>
        </div>
      </ScrollArea>

      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-full bg-[oklch(var(--signal)/0.15)] text-[11px] font-semibold text-[oklch(var(--signal))]">
            {user?.full_name
              ?.split(" ")
              .map((n) => n[0])
              .slice(0, 2)
              .join("") ?? "WS"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium">{user?.full_name ?? "Workspace"}</div>
            <div className="truncate text-[11px] capitalize text-muted-foreground">
              {user?.role?.replace("_", " ") ?? "user"}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
