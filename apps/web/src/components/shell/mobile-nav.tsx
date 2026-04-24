import { NavLink, useLocation } from "react-router-dom";
import { LayoutDashboard, Radar, Users, Sparkles, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { appPaths } from "@/app/paths";

const ITEMS = [
  { label: "Home", href: appPaths.dashboard, icon: LayoutDashboard },
  { label: "Jobs", href: appPaths.searches, icon: Radar },
  { label: "Leads", href: appPaths.leads, icon: Users },
  { label: "AI", href: appPaths.aiAnalysis, icon: Sparkles },
  { label: "Outreach", href: appPaths.outreach, icon: Send },
];

export function MobileNav() {
  const location = useLocation();
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-center justify-around border-t border-border bg-background/95 px-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] backdrop-blur-xl lg:hidden"
      aria-label="Primary"
    >
      {ITEMS.map((it) => {
        const active = location.pathname === it.href || location.pathname.startsWith(it.href + "/");
        const Icon = it.icon;
        return (
          <NavLink
            key={it.href}
            to={it.href}
            className={cn(
              "flex min-h-12 flex-1 flex-col items-center justify-center gap-1 rounded-md text-[10px] font-medium transition-colors",
              active ? "text-[oklch(var(--signal))]" : "text-muted-foreground",
            )}
          >
            <Icon className="size-5" />
            {it.label}
          </NavLink>
        );
      })}
    </nav>
  );
}
