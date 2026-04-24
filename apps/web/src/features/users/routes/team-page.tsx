import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createUser, listUsers, resetUserPassword, updateUser } from "@/features/users/api";
import { useAuthSession } from "@/features/auth/session";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
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

export function TeamPage() {
  useDocumentTitle("Team");
  const queryClient = useQueryClient();
  const { user } = useAuthSession();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [role, setRole] = useState<UserRole>("member");
  const [drafts, setDrafts] = useState<Record<string, { role: UserRole; status: UserStatus; jobTitle: string }>>({});

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
    mutationFn: async (userId: string) => resetUserPassword(userId, { password: "TempReset123!" }),
    onSuccess: refreshTeam,
  });

  if (usersQuery.isPending) {
    return <QueryStateNotice tone="loading" title="Loading team" description="Fetching workspace users and access states." />;
  }

  if (usersQuery.isError) {
    return <QueryStateNotice tone="error" title="Team unavailable" description={usersQuery.error.message} />;
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
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">Team users</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Manage users inside the current workspace only. Account isolation is enforced by the backend.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Team users</CardTitle>
          <CardDescription>
            Every user is bound to the active workspace. Owners and admins can add and manage team members without crossing account boundaries.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {canManage ? (
            <div className="grid gap-3 rounded-xl border border-border bg-card/50 p-4 md:grid-cols-2 xl:grid-cols-5">
              <div className="flex flex-col gap-2">
                <Label htmlFor="team-full-name">Full name</Label>
                <Input id="team-full-name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Jordan Lee" />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="team-email">Email</Label>
                <Input id="team-email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="jordan@company.com" />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="team-password">Temporary password</Label>
                <Input id="team-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="TempPass123!" />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="team-job-title">Job title</Label>
                <Input id="team-job-title" value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} placeholder="RevOps Lead" />
              </div>
              <div className="flex flex-col gap-2">
                <Label>Role</Label>
                <Select value={role} onValueChange={(value) => setRole(value as UserRole)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CREATE_ROLE_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option.replace("_", " ")}
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
                {createMutation.isPending ? "Creating user..." : "Create team user"}
              </Button>
              {createMutation.error ? (
                <QueryStateNotice tone="error" title="Team user not created" description={createMutation.error.message} />
              ) : (
                <QueryStateNotice
                  tone="info"
                  title="Workspace-scoped team access"
                  description="The first signup user is the account owner. Additional users stay inside this workspace and count against the simulated team-user limit."
                />
              )}
            </div>
          ) : (
            <QueryStateNotice tone="info" title="Read-only access" description="Only account owners and admins can manage team users." />
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
                      <Badge>{item.role.replace("_", " ")}</Badge>
                      {isSelf ? <Badge tone="neutral">You</Badge> : null}
                    </div>
                    <p className="text-sm text-muted-foreground">{item.email}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{item.job_title || "No job title set"}</p>
                  </div>

                  {canManage && !isOwner ? (
                    <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-1">
                      <div className="flex flex-col gap-2">
                        <Label>Role</Label>
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
                                {option.replace("_", " ")}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label>Status</Label>
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
                                {option}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label>Job title</Label>
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
                      {isOwner ? "The account owner stays protected inside this workspace." : "Workspace members can view team state only."}
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
                        Save changes
                      </Button>
                      <Button variant="outline" disabled={resetPasswordMutation.isPending} onClick={() => resetPasswordMutation.mutate(item.public_id)}>
                        Reset password
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
