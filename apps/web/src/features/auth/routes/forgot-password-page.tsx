import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { appPaths } from "@/app/paths";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { useDocumentTitle } from "@/hooks/use-document-title";

export function ForgotPasswordPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("auth.forgotPasswordTitle"));

  return (
    <AuthShell
      eyebrow={t("auth.forgotPasswordEyebrow")}
      title={t("auth.forgotPasswordTitle")}
      description={t("auth.forgotPasswordSubtitle")}
      footer={
        <p className="text-[12px] text-muted-foreground">
          {t("auth.haveAccount")}{" "}
          <Link
            to={appPaths.login}
            className="font-medium text-foreground hover:text-[oklch(var(--signal))]"
          >
            {t("auth.signIn")}
          </Link>
        </p>
      }
    >
      <div className="flex flex-col gap-4">
        <QueryStateNotice
          tone="info"
          title={t("auth.forgotPasswordUnavailableTitle")}
          description={t("auth.forgotPasswordUnavailableDescription")}
        />
        <Button asChild variant="outline">
          <Link to={appPaths.login}>{t("auth.backToSignIn")}</Link>
        </Button>
      </div>
    </AuthShell>
  );
}
