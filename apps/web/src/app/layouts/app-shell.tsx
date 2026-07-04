import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/shell/sidebar";
import { AppTopbar } from "@/components/shell/topbar";
import { CommandMenu } from "@/components/shell/command-menu";
import { PageTransition } from "@/components/brand/page-transition";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

type AppShellProps = {
  children?: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <SidebarProvider defaultOpen>
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <AppTopbar />
        <main className="flex-1 overflow-x-clip">
          <PageTransition>{children ?? <Outlet />}</PageTransition>
        </main>
      </SidebarInset>
      <CommandMenu />
    </SidebarProvider>
  );
}
