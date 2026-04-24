import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { AuthSidebar } from "@/components/brand/auth-sidebar";
import { LeadScopeWordmark } from "@/components/brand/logo";
import { appPaths } from "@/app/paths";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type AuthShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  footer: ReactNode;
  children: ReactNode;
};

export function AuthShell({ eyebrow, title, description, footer, children }: AuthShellProps) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr),minmax(0,1.1fr)]">
      <div className="relative flex flex-col">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 sm:py-5 lg:px-12">
          <LeadScopeWordmark />
          <Link
            to={appPaths.home}
            className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-3" /> Back to site
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-center px-4 py-6 sm:px-6 sm:py-8 lg:px-12">
          <div className="w-full max-w-md">
            <div className="mb-6 inline-flex items-center gap-1.5 rounded-full border border-[oklch(var(--signal)/0.3)] bg-[oklch(var(--signal)/0.08)] px-2.5 py-0.5 text-[11px] font-medium text-[oklch(var(--signal))]">
              {eyebrow}
            </div>
            <Card className="border-border bg-card/70 backdrop-blur">
              <CardHeader className="gap-3">
                <CardTitle className="text-pretty text-[30px] font-semibold leading-[1.1] tracking-tight">
                  {title}
                </CardTitle>
                <CardDescription className="text-sm leading-relaxed text-muted-foreground">
                  {description}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-6">
                {children}
                {footer}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <AuthSidebar />
    </div>
  );
}
