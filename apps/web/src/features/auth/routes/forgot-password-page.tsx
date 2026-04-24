import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { appPaths } from "@/app/paths";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function ForgotPasswordPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("auth.forgotPasswordTitle"));
  const [sent, setSent] = useState(false);

  return (
    <AuthShell
      eyebrow="Password reset"
      title={t("auth.forgotPasswordTitle")}
      description={t("auth.forgotPasswordSubtitle")}
      footer={
        <p className="text-[12px] text-muted-foreground">
          {t("auth.haveAccount")}{" "}
          <Link to={appPaths.login} className="font-medium text-foreground hover:text-[oklch(var(--signal))]">
            {t("auth.signIn")}
          </Link>
        </p>
      }
    >
      {!sent ? (
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            setSent(true);
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">{t("auth.workEmail")}</Label>
            <Input id="email" type="email" autoComplete="email" required placeholder="you@company.com" />
          </div>
          <Button type="submit">
            {t("auth.sendResetLink")}
            <ArrowRight data-icon="inline-end" />
          </Button>
        </form>
      ) : (
        <QueryStateNotice
          tone="success"
          title={t("auth.resetLinkSent")}
          description="The reset API is not implemented yet, but the auth shell is ready for the future flow."
        />
      )}
    </AuthShell>
  );
}
