import { NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  Building2,
  Command,
  LayoutDashboard,
  Radar,
  Users,
  Sparkles,
  MessageSquareText,
  Send,
  ShieldCheck,
  ScrollText,
  FileDown,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
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
  { labelKey: "nav.assistant", href: appPaths.assistant, icon: MessageSquareText },
  { labelKey: "nav.outreach", href: appPaths.outreach, icon: Send },
];

const GOVERN: NavItem[] = [
  { labelKey: "nav.admin", href: appPaths.admin, icon: ShieldCheck, roles: ["account_owner", "admin"] },
  { labelKey: "nav.team", href: appPaths.team, icon: Users },
  { labelKey: "nav.billing", href: appPaths.billing, icon: ShieldCheck },
  { labelKey: "nav.invoices", href: appPaths.invoices, icon: ScrollText },
  { labelKey: "nav.usage", href: appPaths.usage, icon: FileDown },
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
          "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
          active
            ? "bg-sidebar-accent/90 text-sidebar-accent-foreground"
            : "text-muted-foreground hover:bg-sidebar-accent/65 hover:text-sidebar-accent-foreground",
        )}
      >
        {active ? (
          <motion.span
            layoutId="sidebar-active"
            transition={{ type: "spring", stiffness: 400, damping: 34 }}
            className="absolute inset-y-1.5 inset-s-0 w-0.5 rounded-full bg-[oklch(var(--signal))] shadow-[0_0_10px_oklch(var(--signal)/0.7)]"
          />
        ) : null}
        <Icon className={cn("size-4 shrink-0", active && "text-[oklch(var(--signal))]")} />
        <span className="flex-1 font-medium">{t(item.labelKey)}</span>
        {item.badge ? <span className="font-mono text-[10px] font-medium text-muted-foreground tabular-nums">{item.badge}</span> : null}
      </NavLink>
    );
  }

  return (
    <aside className="hidden w-80 shrink-0 border-r border-sidebar-border bg-sidebar lg:order-first lg:flex rtl:border-r-0 rtl:border-l">
      <div className="flex w-full flex-col bg-[oklch(var(--sidebar))]">
        <div className="border-b border-sidebar-border px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md border border-sidebar-border bg-sidebar-accent/40">
              <Command className="size-3.5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground/80">
                Platform control
              </p>
              <p className="truncate text-[14px] font-semibold text-foreground">Admin command center</p>
            </div>
          </div>
        </div>

        <div className="px-3 py-3">
          <div className="rounded-lg border border-sidebar-border/90 bg-sidebar-accent/35 p-3">
            <div className="mb-1 inline-flex items-center gap-1 rounded-md border border-sidebar-border/80 bg-background/30 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground/85">
              Admin command center
            </div>
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              Users, operations, payments, and settings in one operational view.
            </p>
          </div>
        </div>

        <ScrollArea className="flex-1 px-2">
          <nav className="flex flex-col gap-0.5 pb-4">
            <div className="px-2 pb-1.5 pt-2 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground/70">
              Main navigation
            </div>
            {PRIMARY.map(renderItem)}

            <div className="mt-3 px-2 pb-1.5 pt-2 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground/70">
              More workflows
            </div>
            {GOVERN.map(renderItem)}
          </nav>
        </ScrollArea>

        <div className="border-t border-sidebar-border px-3 py-3">
          <div className="rounded-lg border border-sidebar-border bg-sidebar-accent/30 px-2.5 py-2.5">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-full bg-[oklch(var(--signal)/0.18)] text-[11px] font-semibold text-[oklch(var(--signal))]">
                {user?.full_name
                  ?.split(" ")
                  .map((n) => n[0])
                  .slice(0, 2)
                  .join("") ?? "WS"}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12px] font-medium text-foreground">
                  {user?.full_name ?? "System Administrator"}
                </div>
                <div className="truncate text-[11px] text-muted-foreground">
                  {user?.email ?? "admin@localhost"}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-2 flex items-center gap-2 rounded-md border border-sidebar-border/80 bg-sidebar-accent/20 px-2.5 py-2 text-[11px] text-muted-foreground">
            <Building2 className="size-3.5 shrink-0" />
            <span className="truncate">
              {user?.workspace_name ?? t("common.workspace")} · {user?.workspace_slug ?? t("shell.workspaceFallbackSlug")}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
