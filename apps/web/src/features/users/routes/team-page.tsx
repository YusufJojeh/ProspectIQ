import { useState, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { createUser, listUsers, resetUserPassword, updateUser } from "@/features/users/api";
import { useAuthSession } from "@/features/auth/session";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDocumentTitle } from "@/hooks/use-document-title";
import type { UserRole, UserStatus } from "@/types/api";

const CREATE_ROLE_OPTIONS: UserRole[] = ["admin", "manager", "member"];
const STATUS_OPTIONS: UserStatus[] = ["active", "inactive"];

function generateTempPassword(): string {
  const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
  const lower = "abcdefghjkmnpqrstuvwxyz";
  const digits = "23456789";
  const special = "!@#$%^&*";
  const all = upper + lower + digits + special;
  const buf = new Uint8Array(16);
  window.crypto.getRandomValues(buf);
  const chars = Array.from(buf).map((b) => all[b % all.length]);
  // Guarantee one of each required class in the first 4 positions
  chars[0] = upper[buf[0] % upper.length];
  chars[1] = lower[buf[1] % lower.length];
  chars[2] = digits[buf[2] % digits.length];
  chars[3] = special[buf[3] % special.length];
  return chars.join("");
}

export function TeamPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("team.title"));
  const queryClient = useQueryClient();
  const { user } = useAuthSession();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [role, setRole] = useState<UserRole>("member");
  const [drafts, setDrafts] = useState<Record<string, { role: UserRole; status: UserStatus; jobTitle: string }>>({});
  const [resetResult, setResetResult] = useState<{ userId: string; tempPassword: string } | null>(null);
  const tempPasswordRef = useRef<HTMLInputElement>(null);

  const usersQuery = useQuery({
    queryKey: ["team-users"],
    queryFn: listUsers,
  });

  const canManage = user?.permissions?.includes("team:manage") ?? false;

  const refreshTeam = () => {
    queryClient.invalidateQueries({ queryKey: ["team-users"] });
    queryClient.invalidateQueries({ queryKey: ["billing-usage"] });
  };

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      setEmail("");
      setFullName("");
      setPassword("");
      setJobTitle("");
      setRole("member");
      refreshTeam();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: { role: UserRole; status: UserStatus; job_title: string | null } }) =>
      updateUser(userId, payload),
    onSuccess: refreshTeam,
  });

  const resetPasswordMutation = useMutation({
    mutationFn: async (userId: string) => {
      const tempPassword = generateTempPassword();
      await resetUserPassword(userId, { password: tempPassword });
      return { userId, tempPassword };
    },
    onSuccess: (result) => {
      setResetResult(result);
      refreshTeam();
    },
  });

  if (usersQuery.isPending) {
    return <QueryStateNotice tone="loading" title={t("team.loadingTitle")} description={t("team.loadingDescription")} />;
  }

  if (usersQuery.isError) {
    return <QueryStateNotice tone="error" title={t("team.unavailableTitle")} error={usersQuery.error} />;
  }

  const getDraft = (userId: string, currentRole: UserRole, currentStatus: UserStatus, currentJobTitle?: string | null) =>
    drafts[userId] ?? {
      role: currentRole,
      status: currentStatus,
      jobTitle: currentJobTitle ?? "",
    };

  return (
    <div className="flex flex-col gap-6 p-4 lg:p-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">{t("team.usersTitle")}</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          {t("team.usersDescription")}
        </p>
      </div>

      {resetResult ? (
        <Alert className="border-warning bg-warning/10">
          <AlertTitle>{t("team.passwordResetTitle")}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2">
            <p>{t("team.passwordResetDescription")}</p>
            <div className="flex items-center gap-2">
              <input
                ref={tempPasswordRef}
                readOnly
                value={resetResult.tempPassword}
                className="flex-1 rounded border border-border bg-background px-3 py-1 font-mono text-sm"
                aria-label={t("team.tempPasswordLabel")}
              />
              <button
                className="rounded border border-border px-2 py-1 text-xs"
                onClick={() => {
                  tempPasswordRef.current?.select();
                  navigator.clipboard.writeText(resetResult.tempPassword);
                }}
              >
                {t("team.copy")}
              </button>
              <button
                className="rounded border border-border px-2 py-1 text-xs"
                onClick={() => setResetResult(null)}
              >
                {t("team.dismiss")}
              </button>
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("team.usersTitle")}</CardTitle>
          <CardDescription>
            {t("team.usersCardDescription")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {canManage ? (
            <div className="grid gap-3 rounded-xl border border-border bg-card/50 p-4 md:grid-cols-2 xl:grid-cols-5">
              <div className="flex flex-col gap-2">
                <Label htmlFor="team-full-name">{t("team.fullName")}</Label>
                <Input id="team-full-name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Jordan Lee" />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="team-email">{t("common.email")}</Label>
                <Input id="team-email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="jordan@company.com" />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="team-password">{t("team.temporaryPassword")}</Label>
                <Input id="team-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="TempPass123!" />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="team-job-title">{t("team.jobTitle")}</Label>
                <Input id="team-job-title" value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} placeholder="RevOps Lead" />
              </div>
              <div className="flex flex-col gap-2">
                <Label>{t("common.role")}</Label>
                <Select value={role} onValueChange={(value) => setRole(value as UserRole)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CREATE_ROLE_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {t(`team.roles.${option}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                className="md:col-span-2 xl:col-span-5"
                disabled={createMutation.isPending}
                onClick={() =>
                  createMutation.mutate({
                    email,
                    full_name: fullName,
                    password,
                    role,
                    job_title: jobTitle || null,
                  })
                }
              >
                {createMutation.isPending ? t("team.creating") : t("team.createTeamUser")}
              </Button>
              {createMutation.error ? (
                <QueryStateNotice tone="error" title={t("team.createErrorTitle")} error={createMutation.error} />
              ) : (
                <QueryStateNotice
                  tone="info"
                  title={t("team.workspaceScopedTitle")}
                  description={t("team.workspaceScopedDescription")}
                />
              )}
            </div>
          ) : (
            <QueryStateNotice tone="info" title={t("team.readOnlyTitle")} description={t("team.readOnlyDescription")} />
          )}

          <div className="grid gap-3">
            {usersQuery.data.items.map((item) => {
              const draft = getDraft(item.public_id, item.role, item.status, item.job_title);
              const isOwner = item.role === "account_owner";
              const isSelf = item.public_id === user?.public_id;

              return (
                <div key={item.public_id} className="grid gap-4 rounded-xl border border-border bg-card/50 p-4 xl:grid-cols-[1.4fr_1fr_auto]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate font-medium text-foreground">{item.full_name}</p>
                      <Badge tone={item.status === "active" ? "success" : "warning"}>{item.status}</Badge>
                      <Badge>{t(`team.roles.${item.role}`)}</Badge>
                      {isSelf ? <Badge tone="neutral">{t("team.you")}</Badge> : null}
                    </div>
                    <p className="text-sm text-muted-foreground">{item.email}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{item.job_title || t("team.noJobTitle")}</p>
                  </div>

                  {canManage && !isOwner ? (
                    <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-1">
                      <div className="flex flex-col gap-2">
                        <Label>{t("common.role")}</Label>
                        <Select
                          value={draft.role}
                          onValueChange={(value) =>
                            setDrafts((current) => ({
                              ...current,
                              [item.public_id]: { ...draft, role: value as UserRole },
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {CREATE_ROLE_OPTIONS.map((option) => (
                              <SelectItem key={option} value={option}>
                                {t(`team.roles.${option}`)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label>{t("common.status")}</Label>
                        <Select
                          value={draft.status}
                          onValueChange={(value) =>
                            setDrafts((current) => ({
                              ...current,
                              [item.public_id]: { ...draft, status: value as UserStatus },
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {STATUS_OPTIONS.map((option) => (
                              <SelectItem key={option} value={option}>
                                {t(`team.statuses.${option}`)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label>{t("team.jobTitle")}</Label>
                        <Input
                          value={draft.jobTitle}
                          onChange={(event) =>
                            setDrafts((current) => ({
                              ...current,
                              [item.public_id]: { ...draft, jobTitle: event.target.value },
                            }))
                          }
                          placeholder="Sales lead"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
                      {isOwner ? t("team.ownerProtected") : t("team.membersViewOnly")}
                    </div>
                  )}

                  {canManage && !isOwner ? (
                    <div className="flex flex-wrap items-start gap-2 xl:justify-end">
                      <Button
                        variant="outline"
                        disabled={updateMutation.isPending}
                        onClick={() =>
                          updateMutation.mutate({
                            userId: item.public_id,
                            payload: {
                              role: draft.role,
                              status: draft.status,
                              job_title: draft.jobTitle || null,
                            },
                          })
                        }
                      >
                        {t("team.saveChanges")}
                      </Button>
                      <Button variant="outline" disabled={resetPasswordMutation.isPending} onClick={() => resetPasswordMutation.mutate(item.public_id)}>
                        {t("team.resetPassword")}
                      </Button>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
