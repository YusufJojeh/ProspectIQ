import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, ShieldCheck, Sparkles } from "lucide-react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { CardDescription, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { login } from "@/features/auth/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { productName } from "@/lib/brand";

const loginSchema = z.object({
  workspace: z.string().min(2),
  email: z.string().email(),
  password: z.string().min(8),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  useDocumentTitle("Sign In");
  const navigate = useNavigate();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      workspace: "ws_default",
      email: "admin@prospectiq.dev",
      password: "ChangeMe123!",
    },
  });

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: () => navigate("/"),
  });

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(15,118,110,0.16),transparent_28%),radial-gradient(circle_at_bottom_left,rgba(180,83,9,0.1),transparent_22%)]" />
      <div className="relative grid w-full max-w-6xl overflow-hidden rounded-[2rem] border border-[color:var(--border)] bg-[color:var(--panel)] shadow-[0_35px_70px_-45px_rgba(15,23,42,0.35)] lg:grid-cols-[0.92fr_1.08fr]">
        <div className="border-b border-[color:var(--border)] bg-[color:var(--panel-strong)] p-6 lg:border-b-0 lg:border-e lg:p-10">
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-[color:var(--muted)]">{productName}</p>
          <CardTitle className="mt-4 text-3xl leading-tight">
            Sign in to the agency lead qualification workspace
          </CardTitle>
          <CardDescription className="mt-3 max-w-lg text-sm leading-6">
            Use a valid workspace account to access the live FastAPI API, persisted evidence, deterministic scores, and assistive workflow tools.
          </CardDescription>

          <form className="mt-8 space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
            <div className="space-y-2">
              <label className="text-sm font-semibold" htmlFor="login-workspace">Workspace</label>
              <Input id="login-workspace" {...form.register("workspace")} />
              {form.formState.errors.workspace ? (
                <p className="text-sm text-red-600">{form.formState.errors.workspace.message}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold" htmlFor="login-email">Email</label>
              <Input id="login-email" {...form.register("email")} />
              {form.formState.errors.email ? (
                <p className="text-sm text-red-600">{form.formState.errors.email.message}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold" htmlFor="login-password">Password</label>
              <Input id="login-password" type="password" {...form.register("password")} />
              {form.formState.errors.password ? (
                <p className="text-sm text-red-600">{form.formState.errors.password.message}</p>
              ) : null}
            </div>

            {mutation.error ? (
              <QueryStateNotice
                tone="error"
                title="Sign-in failed"
                description={mutation.error.message}
              />
            ) : null}

            <Button className="w-full justify-center" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Signing in..." : "Open workspace"}
              {!mutation.isPending ? <ArrowRight className="ms-2 h-4 w-4" /> : null}
            </Button>
          </form>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
              <ShieldCheck className="h-4 w-4 text-[color:var(--accent)]" />
              <p className="mt-3 text-sm font-semibold">Workspace-aware auth</p>
            </div>
            <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
              <Sparkles className="h-4 w-4 text-[color:var(--accent)]" />
              <p className="mt-3 text-sm font-semibold">Assistive AI outputs</p>
            </div>
            <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
              <CheckCircle2 className="h-4 w-4 text-[color:var(--accent)]" />
              <p className="mt-3 text-sm font-semibold">Auditable evidence</p>
            </div>
          </div>
        </div>

        <div className="relative overflow-hidden bg-[linear-gradient(160deg,#16302b_0%,#112520_55%,#0f1f1b_100%)] p-6 text-white lg:p-10">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(94,234,212,0.2),transparent_25%),radial-gradient(circle_at_bottom_right,rgba(251,191,36,0.14),transparent_22%)]" />
          <div className="relative flex h-full flex-col justify-between gap-8">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.24em] text-teal-100/70">Decision support</p>
              <h2 className="mt-3 max-w-xl text-3xl font-extrabold leading-tight">
                Discover local businesses, normalize evidence, score lead quality, and ship a draft outreach path.
              </h2>
              <p className="mt-4 max-w-xl text-sm leading-7 text-teal-50/80">
                The authenticated app is tuned for dense operations work: search jobs, filterable lead tables, maps, score explanations, provider settings, and audit visibility.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[1.5rem] border border-white/10 bg-white/8 p-5 backdrop-blur">
                <p className="text-xs uppercase tracking-[0.18em] text-teal-100/70">Stack</p>
                <p className="mt-3 text-lg font-bold">FastAPI, SQLAlchemy, React, TanStack Query, React Leaflet</p>
              </div>
              <div className="rounded-[1.5rem] border border-white/10 bg-white/8 p-5 backdrop-blur">
                <p className="text-xs uppercase tracking-[0.18em] text-teal-100/70">Rules</p>
                <p className="mt-3 text-lg font-bold">Deterministic facts first, AI second</p>
              </div>
            </div>

            <div className="rounded-[1.75rem] border border-white/10 bg-white/8 p-5 backdrop-blur">
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-teal-100/70">Provider</p>
                  <p className="mt-2 text-2xl font-extrabold">SerpAPI</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-teal-100/70">Maps</p>
                  <p className="mt-2 text-2xl font-extrabold">Leaflet</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-teal-100/70">Shell</p>
                  <p className="mt-2 text-2xl font-extrabold">Dashboard-first</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
