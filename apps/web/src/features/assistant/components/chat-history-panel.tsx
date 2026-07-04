import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Plus, Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import {
  deleteChatSession,
  listChatSessions,
  type ChatSessionSummary,
} from "@/features/assistant/api";
import { formatDate } from "@/lib/presenters";
import { cn } from "@/lib/utils";

export type ChatHistoryPanelProps = {
  leadId?: string;
  currentSessionId?: string;
  onResume: (sessionId: string) => void;
  onNewChat: () => void;
};

export function ChatHistoryPanel({
  leadId,
  currentSessionId,
  onResume,
  onNewChat,
}: ChatHistoryPanelProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<ChatSessionSummary | null>(
    null,
  );

  const queryKey = ["chat-sessions", leadId ?? "workspace"] as const;
  const sessionsQuery = useQuery({
    queryKey,
    queryFn: () => listChatSessions(leadId || undefined),
  });

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => deleteChatSession(sessionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      setPendingDelete(null);
    },
  });

  const sessions = sessionsQuery.data ?? [];

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">
          {t("assistant.conversationHistory")}
        </h2>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="bg-transparent"
          onClick={onNewChat}
        >
          <Plus className="size-3.5" />
          {t("assistant.newChat")}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto pr-1">
        {sessionsQuery.isPending ? (
          <QueryStateNotice
            tone="loading"
            title={t("assistant.loadingContext")}
            description=""
          />
        ) : sessionsQuery.isError ? (
          <QueryStateNotice
            tone="error"
            title={t("assistant.contextUnavailable")}
            error={sessionsQuery.error}
          />
        ) : sessions.length === 0 ? (
          <EmptyState
            title={t("assistant.noPreviousChats")}
            description={t("assistant.noPreviousChatsDescription")}
          />
        ) : (
          <ul className="space-y-2">
            {sessions.map((session) => {
              const isActive = currentSessionId === session.public_id;
              return (
                <li key={session.public_id}>
                  <div
                    className={cn(
                      "group flex w-full items-start gap-2 rounded-2xl border bg-card/95 p-3 text-start transition",
                      isActive
                        ? "border-[oklch(var(--signal)/0.55)] shadow-[0_0_0_1px_oklch(var(--signal)/0.25)]"
                        : "border-border hover:border-[oklch(var(--signal)/0.45)]",
                    )}
                  >
                    <button
                      type="button"
                      className="flex min-w-0 flex-1 flex-col gap-1 text-start outline-none"
                      onClick={() => onResume(session.public_id)}
                      aria-label={t("assistant.resumeChat")}
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <MessageSquare className="size-3.5 shrink-0 text-muted-foreground" />
                        <span className="truncate text-sm font-medium">
                          {session.title}
                        </span>
                      </div>
                      {session.last_message_preview ? (
                        <p className="line-clamp-2 text-xs text-muted-foreground">
                          {session.last_message_preview}
                        </p>
                      ) : null}
                      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                        <span>{formatDate(session.updated_at)}</span>
                        <span aria-hidden>·</span>
                        <span>
                          {t("assistant.messageCount", {
                            count: session.message_count,
                          })}
                        </span>
                      </div>
                    </button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-muted-foreground opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100"
                      onClick={() => setPendingDelete(session)}
                      aria-label={t("assistant.deleteChat")}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("assistant.deleteChat")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("assistant.deleteChatConfirm")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendingDelete) {
                  deleteMutation.mutate(pendingDelete.public_id);
                }
              }}
            >
              {t("assistant.deleteChat")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
