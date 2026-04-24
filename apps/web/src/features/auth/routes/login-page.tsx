import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { appPaths } from "@/app/paths";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { login } from "@/features/auth/api";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { useDocumentTitle } from "@/hooks/use-document-title";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(12),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("auth.signIn"));
  const navigate = useNavigate();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: () => navigate(appPaths.dashboard),
  });

  return (
    <AuthShell
      eyebrow="Workspace sign in"
      title={t("auth.signInTitle")}
      description={t("auth.signInSubtitle")}
      footer={
        <p className="text-[12px] text-muted-foreground">
          {t("auth.noAccount")}{" "}
          <Link to={appPaths.signUp} className="font-medium text-foreground hover:text-[oklch(var(--signal))]">
            {t("auth.signUp")}
          </Link>
        </p>
      }
    >
      <Form {...form}>
        <form
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
        >
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("auth.workEmail")}</FormLabel>
                <FormControl>
                  <Input autoComplete="email" placeholder="you@company.com" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between gap-3">
                  <FormLabel>{t("auth.password")}</FormLabel>
                  <Link to={appPaths.forgotPassword} className="text-[12px] text-muted-foreground hover:text-foreground">
                    {t("auth.forgotPassword")}
                  </Link>
                </div>
                <FormControl>
                  <Input type="password" autoComplete="current-password" placeholder={t("auth.password") as string} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {mutation.error ? (
            <QueryStateNotice tone="error" title={t("auth.signInFailed")} description={mutation.error.message} />
          ) : null}

          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? t("auth.signingIn") : t("auth.openWorkspace")}
            {!mutation.isPending ? <ArrowRight data-icon="inline-end" /> : null}
          </Button>
        </form>
      </Form>
    </AuthShell>
  );
}
