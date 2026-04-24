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
import { signup } from "@/features/auth/api";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { useDocumentTitle } from "@/hooks/use-document-title";

const signUpSchema = z
  .object({
    full_name: z.string().min(2),
    workspace_name: z.string().min(2),
    email: z.string().email(),
    password: z
      .string()
      .min(12)
      .regex(/[a-z]/)
      .regex(/[A-Z]/)
      .regex(/\d/)
      .regex(/[^A-Za-z0-9]/),
    confirm_password: z.string().min(12),
  })
  .refine((value) => value.password === value.confirm_password, {
    message: "Passwords must match.",
    path: ["confirm_password"],
  });

type SignUpValues = z.infer<typeof signUpSchema>;

export function SignUpPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("auth.signUp"));
  const navigate = useNavigate();
  const form = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: {
      full_name: "",
      workspace_name: "",
      email: "",
      password: "",
      confirm_password: "",
    },
  });

  const mutation = useMutation({
    mutationFn: async (values: SignUpValues) =>
      signup({
        full_name: values.full_name,
        workspace_name: values.workspace_name,
        email: values.email,
        password: values.password,
      }),
    onSuccess: () => navigate(appPaths.dashboard),
  });

  return (
    <AuthShell
      eyebrow="Create workspace"
      title={t("auth.signUpTitle")}
      description={t("auth.signUpSubtitle")}
      footer={
        <p className="text-[12px] text-muted-foreground">
          {t("auth.haveAccount")}{" "}
          <Link to={appPaths.login} className="font-medium text-foreground hover:text-[oklch(var(--signal))]">
            {t("auth.signIn")}
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
            name="full_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("auth.fullName")}</FormLabel>
                <FormControl>
                  <Input autoComplete="name" placeholder="Avery North" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="workspace_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("auth.workspaceName")}</FormLabel>
                <FormControl>
                  <Input autoComplete="organization" placeholder="Northbeam Analytics" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("auth.workEmail")}</FormLabel>
                <FormControl>
                  <Input autoComplete="email" placeholder="avery@northbeam.com" {...field} />
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
                <FormLabel>{t("auth.password")}</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" placeholder="At least 12 characters" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="confirm_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("settings.confirmPassword")}</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" placeholder="Re-enter your password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {mutation.error ? (
            <QueryStateNotice tone="error" title={t("auth.signUpFailed")} description={mutation.error.message} />
          ) : (
            <QueryStateNotice
              tone="info"
              title="Simulated starter billing"
              description="Signup creates a real workspace and owner account, then seeds a simulated starter trial with internal billing records only."
            />
          )}

          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? t("common.loading") : t("auth.signUp")}
            {!mutation.isPending ? <ArrowRight data-icon="inline-end" /> : null}
          </Button>
        </form>
      </Form>
    </AuthShell>
  );
}
