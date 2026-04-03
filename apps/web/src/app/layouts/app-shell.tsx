import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Compass, DatabaseZap, LogOut, Search, Settings2 } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getMe } from "@/features/auth/api";
import { useAuthSession } from "@/features/auth/session";
import { productInitials, productName } from "@/lib/brand";

const navigation = [
  { to: "/", label: "Overview", icon: Compass, end: true },
  { to: "/searches", label: "Search Jobs", icon: Search },
  { to: "/leads", label: "Lead Workspace", icon: DatabaseZap },
  { to: "/settings", label: "Admin", icon: Settings2 },
];

const pageMeta = {
  "/": {
    eyebrow: "Overview",
    title: "Agency lead desk",
    description: "Evidence-first workspace for discovery runs, qualification, and outreach drafting.",
  },
  "/searches": {
    eyebrow: "Search Jobs",
    title: "Discovery runs",
    description: "Queue local prospecting jobs and monitor provider-backed discovery throughput.",
  },
  "/leads": {
    eyebrow: "Lead Workspace",
    title: "Qualification pipeline",
    description: "Filter, inspect, map, score, assign, and draft outreach from stored evidence.",
  },
  "/settings": {
    eyebrow: "Admin",
    title: "Operational controls",
    description: "Tune provider defaults, manage scoring versions, and review audit history.",
  },
};

type AppShellProps = {
  children?: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, logout, user: sessionUser } = useAuthSession();
  const meQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    enabled: isAuthenticated,
    initialData: sessionUser ?? undefined,
    retry: false,
  });
  const activePage =
    Object.entries(pageMeta).find(([path]) =>
      path === "/" ? location.pathname === "/" : location.pathname.startsWith(path),
    )?.[1] ?? pageMeta["/"];

  return (
    <div className="min-h-screen bg-[color:var(--bg)] text-[color:var(--text)]">
      <div className="mx-auto grid min-h-screen max-w-[1520px] grid-cols-1 gap-6 px-4 py-4 lg:grid-cols-[280px_minmax(0,1fr)] lg:px-6">
        <aside className="flex h-full flex-col rounded-[1.75rem] border border-[color:var(--border)] bg-[color:var(--panel)] p-5 shadow-[0_20px_50px_-36px_rgba(15,23,42,0.35)] backdrop-blur">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--accent)_0%,#155e75_100%)] text-sm font-extrabold text-white">
              {productInitials}
            </div>
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--muted)]">{productName}</p>
              <h1 className="text-lg font-extrabold">Agency prospect desk</h1>
            </div>
          </div>

          <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-[color:var(--muted)]">Operating mode</p>
            <p className="mt-2 text-sm font-semibold">
              Modular monolith with deterministic scoring and auditable evidence.
            </p>
          </div>

          <nav className="mt-6 space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-3 rounded-2xl border px-3 py-3 text-sm font-semibold transition",
                      isActive
                        ? "border-transparent bg-[color:var(--accent)] text-white shadow-[0_18px_40px_-24px_rgba(15,118,110,0.9)]"
                        : "border-transparent text-[color:var(--muted)] hover:border-[color:var(--border)] hover:bg-white/70 hover:text-[color:var(--text)]",
                    ].join(" ")
                  }
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>

          <div className="mt-auto space-y-4">
            <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-raised)] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{meQuery.data?.full_name ?? "Session"}</p>
                  <p className="text-xs text-[color:var(--muted)]">
                    {meQuery.data?.email ?? "Loading profile..."}
                  </p>
                </div>
                <Badge tone="accent">{meQuery.data?.role ?? "user"}</Badge>
              </div>
              <p className="mt-3 text-xs uppercase tracking-[0.18em] text-[color:var(--muted)]">
                Workspace {meQuery.data?.workspace_public_id ?? "..."}
              </p>
            </div>

            <Button
              className="w-full justify-center"
              variant="secondary"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </Button>
          </div>
        </aside>

        <main className="min-w-0 space-y-6 rounded-[1.75rem] border border-[color:var(--border)] bg-[color:var(--panel)] p-4 shadow-[0_20px_50px_-36px_rgba(15,23,42,0.28)] backdrop-blur lg:p-6">
          <header className="flex flex-col gap-4 rounded-[1.25rem] border border-[color:var(--border)] bg-[color:var(--panel-strong)] px-5 py-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--muted)]">
                {activePage.eyebrow}
              </p>
              <h2 className="mt-2 text-2xl font-extrabold">{activePage.title}</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[color:var(--muted)]">
                {activePage.description}
              </p>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Evidence</p>
                <p className="mt-1 text-sm font-bold">Stored provider facts</p>
              </div>
              <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Scoring</p>
                <p className="mt-1 text-sm font-bold">Reproducible bands</p>
              </div>
              <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">AI role</p>
                <p className="mt-1 text-sm font-bold">Assistive drafts only</p>
              </div>
            </div>
          </header>

          {children ?? <Outlet />}
        </main>
      </div>
    </div>
  );
}
