import type { ReactNode } from "react";
import { BarChart3, DatabaseZap, LogOut, Search, Settings2 } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { clearToken } from "@/lib/api-client";

const navigation = [
  { to: "/", label: "Overview", icon: BarChart3, end: true },
  { to: "/searches", label: "Search Jobs", icon: Search },
  { to: "/leads", label: "Leads", icon: DatabaseZap },
  { to: "/settings", label: "Admin", icon: Settings2 },
];

type AppShellProps = {
  children?: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[color:var(--bg)] text-[color:var(--text)]">
      <div className="mx-auto grid min-h-screen max-w-[1440px] grid-cols-1 gap-6 px-4 py-4 lg:grid-cols-[260px_minmax(0,1fr)] lg:px-6">
        <aside className="rounded-xl border border-[color:var(--border)] bg-[color:var(--panel)] p-4 backdrop-blur">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[color:var(--accent-soft)] text-[color:var(--accent)]">
              PI
            </div>
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--muted)]">
                ProspectIQ
              </p>
              <h1 className="text-lg font-extrabold">Agency Lead Desk</h1>
            </div>
          </div>

          <nav className="space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-3 rounded-xl border px-3 py-3 text-sm font-semibold transition",
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

          <Button
            className="mt-6 w-full justify-center"
            variant="secondary"
            onClick={() => {
              clearToken();
              navigate("/login");
            }}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </aside>

        <main className="space-y-6 rounded-xl border border-[color:var(--border)] bg-[color:var(--panel)] p-4 backdrop-blur lg:p-6">
          <header className="flex flex-col gap-4 border-b border-[color:var(--border)] pb-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--muted)]">
                Decision support
              </p>
              <h2 className="mt-2 text-2xl font-extrabold">Foundation workspace for agency prospecting</h2>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              <div className="rounded-xl border border-[color:var(--border)] bg-white/80 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Mode</p>
                <p className="mt-1 text-sm font-bold">Modular monolith</p>
              </div>
              <div className="rounded-xl border border-[color:var(--border)] bg-white/80 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">Truth</p>
                <p className="mt-1 text-sm font-bold">Evidence first</p>
              </div>
              <div className="rounded-xl border border-[color:var(--border)] bg-white/80 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">AI role</p>
                <p className="mt-1 text-sm font-bold">Assist only</p>
              </div>
            </div>
          </header>

          {children ?? <Outlet />}
        </main>
      </div>
    </div>
  );
}
