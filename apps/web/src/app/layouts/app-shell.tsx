import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/shell/sidebar";
import { AppTopbar } from "@/components/shell/topbar";
import { MobileNav } from "@/components/shell/mobile-nav";
import { CommandMenu } from "@/components/shell/command-menu";
import { PageTransition } from "@/components/brand/page-transition";

type AppShellProps = {
  children?: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex min-h-screen min-w-0 bg-background">
      {/* Sidebar is always on the inline-start side (left in LTR, right in RTL) */}
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />
        <main className="flex-1 overflow-x-clip pb-20 lg:pb-0">
          <PageTransition>{children ?? <Outlet />}</PageTransition>
        </main>
      </div>
      <MobileNav />
      <CommandMenu />
    </div>
  );
}
