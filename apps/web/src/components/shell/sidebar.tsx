import type { ComponentType } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Building2,
  BriefcaseBusiness,
  Command,
  FileDown,
  LayoutDashboard,
  MessageSquareText,
  Radar,
  ScrollText,
  Send,
  Megaphone,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { appPaths } from "@/app/paths";
import { useAuthSession } from "@/features/auth/session";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import type { UserRole } from "@/types/api";

type NavItem = {
  labelKey: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  badge?: string;
  roles?: UserRole[];
  permission?: string;
};

const PRIMARY: NavItem[] = [
  {
    labelKey: "nav.dashboard",
    href: appPaths.dashboard,
    icon: LayoutDashboard,
  },
  { labelKey: "nav.searches", href: appPaths.searches, icon: Radar },
  { labelKey: "nav.leads", href: appPaths.leads, icon: Users },
  { labelKey: "nav.aiAnalysis", href: appPaths.aiAnalysis, icon: Sparkles },
  {
    labelKey: "nav.assistant",
    href: appPaths.assistant,
    icon: MessageSquareText,
  },
  { labelKey: "nav.outreach", href: appPaths.outreach, icon: Send },
  { labelKey: "nav.campaigns", href: appPaths.campaigns, icon: Megaphone },
  { labelKey: "nav.crm", href: appPaths.crm, icon: BriefcaseBusiness },
];

const GOVERN: NavItem[] = [
  {
    labelKey: "nav.admin",
    href: appPaths.admin,
    icon: ShieldCheck,
    roles: ["platform_admin"],
  },
  {
    labelKey: "nav.admin",
    href: appPaths.workspaceAdmin,
    icon: ShieldCheck,
    roles: ["account_owner", "admin"],
  },
  { labelKey: "nav.team", href: appPaths.team, icon: Users },
  { labelKey: "nav.billing", href: appPaths.billing, icon: ShieldCheck },
  { labelKey: "nav.invoices", href: appPaths.invoices, icon: ScrollText },
  { labelKey: "nav.usage", href: appPaths.usage, icon: FileDown },
  {
    labelKey: "nav.auditLogs",
    href: appPaths.auditLogs,
    icon: ScrollText,
    roles: ["account_owner", "admin"],
  },
  { labelKey: "nav.exports", href: appPaths.exports, icon: FileDown },
  {
    labelKey: "nav.settings",
    href: appPaths.settings,
    icon: Settings,
    roles: ["account_owner", "admin"],
  },
];

export function AppSidebar() {
  const { i18n } = useTranslation();
  const side = i18n.dir() === "rtl" ? "right" : "left";

  return (
    <Sidebar side={side} collapsible="icon" className="z-40">
      <AppSidebarInner tooltipSide={side === "right" ? "left" : "right"} />
      <SidebarRail />
    </Sidebar>
  );
}

function AppSidebarInner({ tooltipSide }: { tooltipSide: "left" | "right" }) {
  const { t } = useTranslation();
  const location = useLocation();
  const { state } = useSidebar();
  const { user } = useAuthSession();
  const role = user?.role;
  const collapsed = state === "collapsed";

  const renderItem = (item: NavItem) => {
    if (item.roles && (!role || !item.roles.includes(role))) return null;
    if (
      item.permission &&
      !(user?.permissions?.includes(item.permission) ?? false)
    ) {
      return null;
    }

    const active =
      location.pathname === item.href ||
      location.pathname.startsWith(`${item.href}/`);
    const Icon = item.icon;

    return (
      <SidebarMenuItem key={item.href}>
        <SidebarMenuButton
          asChild
          isActive={active}
          tooltip={{ children: t(item.labelKey), side: tooltipSide }}
        >
          <Link to={item.href}>
            <Icon />
            <span>{t(item.labelKey)}</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  };

  const initials =
    user?.full_name
      ?.split(" ")
      .map((name) => name[0])
      .slice(0, 2)
      .join("") || "WS";

  return (
    <>
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-sidebar-border bg-sidebar-accent/50">
            <Command className="size-4 text-sidebar-foreground/75" />
          </div>
          <div className="min-w-0 group-data-[collapsible=icon]:hidden">
            <p className="truncate text-[11px] font-medium uppercase tracking-[0.16em] text-sidebar-foreground/55">
              {t("shell.platformControl")}
            </p>
            <p className="truncate text-sm font-semibold text-sidebar-foreground">
              {t("shell.adminCommandCenter")}
            </p>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        {!collapsed ? (
          <SidebarGroup>
            <div className="rounded-lg border border-sidebar-border bg-sidebar-accent/35 p-3">
              <div className="inline-flex items-center rounded-md border border-sidebar-border bg-background/30 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.2em] text-sidebar-foreground/60">
                {t("shell.adminCommandCenter")}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-sidebar-foreground/65">
                {t("shell.adminCommandCenterDescription")}
              </p>
            </div>
          </SidebarGroup>
        ) : null}

        <SidebarGroup>
          <SidebarGroupLabel>{t("shell.mainNavigation")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{PRIMARY.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>{t("shell.moreWorkflows")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{GOVERN.map(renderItem)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <div className="flex min-w-0 items-center gap-2 rounded-lg border border-sidebar-border bg-sidebar-accent/30 p-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:border-transparent group-data-[collapsible=icon]:bg-transparent">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-sidebar-primary/20 text-xs font-semibold text-sidebar-primary">
            {initials}
          </div>
          <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
            <div className="truncate text-xs font-medium text-sidebar-foreground">
              {user?.full_name ?? t("shell.systemAdministrator")}
            </div>
            <div className="truncate text-[11px] text-sidebar-foreground/60">
              {user?.email ?? "admin@localhost"}
            </div>
          </div>
        </div>

        <div className="flex min-w-0 items-center gap-2 rounded-md border border-sidebar-border bg-sidebar-accent/20 px-2.5 py-2 text-[11px] text-sidebar-foreground/65 group-data-[collapsible=icon]:hidden">
          <Building2 className="size-3.5 shrink-0" />
          <span className="truncate">
            {user?.workspace_name ?? t("common.workspace")} ·{" "}
            {user?.workspace_slug ?? t("shell.workspaceFallbackSlug")}
          </span>
        </div>
      </SidebarFooter>
    </>
  );
}
