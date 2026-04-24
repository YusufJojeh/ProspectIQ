import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Search, Command, Bell, Plus, ChevronRight, Sparkles, Radar, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { appPaths } from "@/app/paths";
import { useAuthSession } from "@/features/auth/session";
import { ThemeSwitcher } from "@/components/shell/theme-switcher";
import { LanguageSwitcher } from "@/components/shell/language-switcher";

const SEGMENT_KEYS: Record<string, string> = {
  dashboard: "nav.dashboard",
  searches: "nav.searches",
  leads: "nav.leads",
  "ai-analysis": "nav.aiAnalysis",
  outreach: "nav.outreach",
  admin: "nav.admin",
  team: "nav.team",
  billing: "nav.billing",
  invoices: "nav.invoices",
  usage: "nav.usage",
  "audit-logs": "nav.auditLogs",
  exports: "nav.exports",
  settings: "nav.settings",
};

export function AppTopbar() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthSession();

  const segments = location.pathname
    .split("/")
    .filter((segment) => segment && SEGMENT_KEYS[segment] !== undefined);

  const userInitials =
    user?.full_name
      ?.split(" ")
      .map((name) => name[0])
      .slice(0, 2)
      .join("") ?? "WS";

  return (
    <header className="sticky top-0 z-30 flex min-h-14 flex-wrap items-center gap-2 border-b border-border bg-background/85 px-3 py-2 backdrop-blur-xl sm:px-4 lg:px-6">
      <nav aria-label="Breadcrumb" className="hidden min-w-0 flex-1 items-center gap-1.5 text-sm md:flex">
        <Link to={appPaths.dashboard} className="shrink-0 text-muted-foreground hover:text-foreground">
          LeadScope
        </Link>
        {segments.map((segment, index) => (
          <div key={segment + index} className="flex min-w-0 items-center gap-1.5">
            <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/60 rtl:rotate-180" />
            <span
              className={
                index === segments.length - 1
                  ? "truncate font-medium text-foreground"
                  : "truncate text-muted-foreground hover:text-foreground"
              }
            >
              {SEGMENT_KEYS[segment] ? t(SEGMENT_KEYS[segment]) : segment.replace(/-/g, " ")}
            </span>
          </div>
        ))}
      </nav>

      <button
        className="order-4 hidden w-full items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted/70 md:flex md:max-w-sm xl:order-none xl:ml-2"
        aria-label={t("topbar.searchPlaceholder")}
        onClick={() => {
          const event = new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true });
          document.dispatchEvent(event);
        }}
      >
        <Search className="size-4" />
        <span className="flex-1 text-start">{t("topbar.searchPlaceholder")}</span>
        <kbd className="pointer-events-none inline-flex items-center gap-0.5 rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
          <Command className="size-2.5" />K
        </kbd>
      </button>

      <div className="ml-auto flex min-w-0 items-center gap-1 sm:gap-1.5 md:ml-0">
        <Button variant="outline" size="sm" className="hidden border-border bg-transparent font-medium sm:inline-flex" asChild>
          <Link to={appPaths.aiAnalysis}>
            <Sparkles className="size-3.5 text-[oklch(var(--signal))]" />
            <span className="hidden lg:inline">{t("topbar.aiAnalysis")}</span>
            <span className="lg:hidden">AI</span>
          </Link>
        </Button>

        <Button size="sm" className="h-9 gap-1.5 px-2.5 font-medium sm:px-3" asChild>
          <Link to={appPaths.searches}>
            <Plus className="size-3.5" />
            <span className="hidden sm:inline">{t("topbar.newSearch")}</span>
            <span className="sm:hidden">{t("common.search")}</span>
          </Link>
        </Button>

        <LanguageSwitcher />
        <ThemeSwitcher />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative size-9 shrink-0">
              <Bell className="size-4" />
              <span className="absolute right-2 top-2 size-1.5 rounded-full bg-[oklch(var(--signal))] shadow-[0_0_0_3px_oklch(var(--signal)/0.2)]" />
              <span className="sr-only">{t("topbar.notifications")}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80">
            <DropdownMenuLabel>{t("topbar.operationalEvents")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="flex-col items-start gap-0.5">
              <div className="flex items-center gap-1.5 text-sm">
                <Radar className="size-3.5 text-[oklch(var(--signal))]" /> Discovery job enrichment phase active
              </div>
              <div className="text-xs text-muted-foreground">2m ago</div>
            </DropdownMenuItem>
            <DropdownMenuItem className="flex-col items-start gap-0.5">
              <div className="text-sm">Scoring weights updated to v12</div>
              <div className="text-xs text-muted-foreground">1h ago / review_velocity +0.05</div>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[oklch(var(--signal)/0.15)] text-[11px] font-semibold text-[oklch(var(--signal))] transition-colors hover:bg-[oklch(var(--signal)/0.25)]">
              {userInitials}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuLabel className="flex flex-col">
              <span className="text-sm font-medium">{user?.full_name ?? "Workspace"}</span>
              <span className="text-xs text-muted-foreground">{user?.email ?? ""}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link to={appPaths.settings}>{t("topbar.profilePreferences")}</Link>
            </DropdownMenuItem>
            {user?.role === "account_owner" || user?.role === "admin" ? (
              <>
                <DropdownMenuItem asChild>
                  <Link to={appPaths.team}>{t("topbar.teamManagement")}</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to={appPaths.billing}>{t("topbar.billingPlans")}</Link>
                </DropdownMenuItem>
              </>
            ) : null}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="gap-2 text-destructive focus:text-destructive"
              onClick={() => {
                logout();
                navigate(appPaths.login, { replace: true });
              }}
            >
              <LogOut className="size-4" />
              {t("topbar.signOut")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
