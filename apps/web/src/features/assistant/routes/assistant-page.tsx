"use client";

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type UIMessage } from "ai";
import { useChat } from "@ai-sdk/react";
import {
  Bot,
  CornerDownRight,
  ExternalLink,
  History,
  MessageSquareText,
  SearchCheck,
  Sparkles,
} from "lucide-react";
import { useSearchParams } from "react-router-dom";
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from "@/components/ai-elements/prompt-input";
import { AiPill, ConfidenceBadge } from "@/components/brand/badges";
import { PageHeader } from "@/components/shell/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ChatHistoryPanel } from "@/features/assistant/components/chat-history-panel";
import {
  createAssistantTransport,
  getChatSession,
  type AssistantChatRequestBody,
} from "@/features/assistant/api";
import { getLead } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { formatScore } from "@/lib/presenters";

type AssistantSearchStatus = "not_needed" | "used" | "unavailable" | "failed";

type AssistantSearchSource = {
  title: string;
  url: string;
  snippet?: string | null;
  provider: string;
};

type AssistantSearchData = {
  used_search: boolean;
  search_status: AssistantSearchStatus;
  sources?: AssistantSearchSource[];
};

function uiMessageFromDb(m: {
  public_id: string;
  role: string;
  content: string;
}): UIMessage {
  const role = m.role === "assistant" || m.role === "system" ? m.role : "user";
  return {
    id: m.public_id,
    role,
    parts: [{ type: "text", text: m.content }],
  } as UIMessage;
}

export function AssistantPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("nav.assistant"));
  const [searchParams] = useSearchParams();
  const leadId = searchParams.get("leadId") ?? "";
  const [input, setInput] = useState("");
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(
    undefined,
  );
  const [historyOpen, setHistoryOpen] = useState(false);
  const queryClient = useQueryClient();

  const leadQuery = useQuery({
    queryKey: ["lead", leadId, "assistant-context"],
    queryFn: () => getLead(leadId),
    enabled: Boolean(leadId),
  });

  const transport = useMemo(() => {
    const body: AssistantChatRequestBody = leadId
      ? { lead_id: leadId, mode: "lead-assistant" }
      : { mode: "lead-assistant" };
    if (currentSessionId) {
      body.session_id = currentSessionId;
    }
    return createAssistantTransport(body);
  }, [leadId, currentSessionId]);

  const { messages, sendMessage, status, stop, error, setMessages } =
    useChat<UIMessage>({
      transport,
    });

  const lead = leadQuery.data;
  const isStreaming = status === "submitted" || status === "streaming";

  const hasStoredScore = lead?.latest_score !== null && lead?.latest_score !== undefined;
  const starterPrompts = leadId
    ? [
        t("assistant.starterPrompt1"),
        t("assistant.starterPrompt2"),
        hasStoredScore
          ? t("assistant.starterPrompt3")
          : t("assistant.starterPrompt3Unscored"),
      ]
    : [
        t("assistant.workspacePrompt1"),
        t("assistant.workspacePrompt2"),
        t("assistant.workspacePrompt3"),
      ];

  const submitPrompt = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) {
      return;
    }
    const body: AssistantChatRequestBody = leadId
      ? { lead_id: leadId, mode: "lead-assistant" }
      : { mode: "lead-assistant" };
    if (currentSessionId) {
      body.session_id = currentSessionId;
    }
    await sendMessage({ text: trimmed }, { body });
    setInput("");
    // Refresh history list once the message lands so previews/counts update.
    void queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
  };

  const handleResumeSession = async (sessionId: string) => {
    try {
      const detail = await getChatSession(sessionId);
      setCurrentSessionId(detail.public_id);
      setMessages(detail.messages.map(uiMessageFromDb));
      setHistoryOpen(false);
    } catch {
      // Errors surface in the history panel itself; swallow here.
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(undefined);
    setMessages([]);
    setHistoryOpen(false);
  };

  return (
    <div className="mx-auto grid max-w-screen-2xl gap-4 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow={t("assistant.eyebrow")}
        title={t("assistant.title")}
        description={t("assistant.description")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" className="bg-transparent">
                  <History className="size-3.5" />
                  {t("assistant.openHistory")}
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-full sm:max-w-md">
                <SheetHeader>
                  <SheetTitle>{t("assistant.conversationHistory")}</SheetTitle>
                  <SheetDescription>
                    {leadId
                      ? t("assistant.noPreviousChatsDescription")
                      : t("assistant.noRepliesWorkspace")}
                  </SheetDescription>
                </SheetHeader>
                <div className="mt-4 h-[calc(100dvh-7rem)]">
                  <ChatHistoryPanel
                    leadId={leadId || undefined}
                    currentSessionId={currentSessionId}
                    onResume={(id) => {
                      void handleResumeSession(id);
                    }}
                    onNewChat={handleNewChat}
                  />
                </div>
              </SheetContent>
            </Sheet>
            <Button
              variant="outline"
              className="bg-transparent"
              onClick={handleNewChat}
            >
              <MessageSquareText className="size-3.5" />
              {t("assistant.newChat")}
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[0.78fr_1.22fr] 2xl:grid-cols-[0.65fr_1.35fr]">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("assistant.groundingContext")}</CardTitle>
            <CardDescription>
              {t("assistant.groundingContextDescription")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {leadId ? (
              leadQuery.isPending ? (
                <QueryStateNotice
                  tone="loading"
                  title={t("assistant.loadingContext")}
                  description={t("assistant.loadingContextDescription")}
                />
              ) : leadQuery.isError ? (
                <QueryStateNotice
                  tone="error"
                  title={t("assistant.contextUnavailable")}
                  error={leadQuery.error}
                />
              ) : lead ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <AiPill>{t("assistant.contextAttached")}</AiPill>
                    <ConfidenceBadge value={lead.data_confidence} />
                  </div>

                  <div>
                    <div className="text-lg font-semibold">
                      {lead.company_name}
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {lead.category ?? t("common.unknown")} -{" "}
                      {lead.city ?? t("common.unknown")}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <ContextMetric
                      label={t("leads.score")}
                      value={formatScore(lead.latest_score)}
                    />
                    <ContextMetric
                      label={t("leads.band")}
                      value={lead.latest_band ?? t("leads.unscored")}
                    />
                    <ContextMetric
                      label={t("leads.reviews")}
                      value={String(lead.review_count)}
                    />
                    <ContextMetric
                      label={t("leads.website")}
                      value={lead.website_domain ?? t("leads.noWebsite")}
                    />
                  </div>
                </div>
              ) : null
            ) : (
              <QueryStateNotice
                tone="info"
                title={t("assistant.noLeadSelected")}
                description={t("assistant.noLeadSelectedDescription")}
              />
            )}

            <div className="rounded-2xl border border-border bg-muted/20 p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="size-4 text-[oklch(var(--signal))]" />
                {t("assistant.suggestedPrompts")}
              </div>
              <div className="mt-3 flex flex-col gap-2">
                {starterPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="rounded-xl border border-border bg-background/70 px-3 py-3 text-start text-sm transition hover:border-[oklch(var(--signal)/0.45)] hover:bg-background"
                    onClick={() => {
                      void submitPrompt(prompt);
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>{t("assistant.conversation")}</CardTitle>
            <CardDescription>
              {t("assistant.conversationDescription")}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex min-h-[620px] flex-col">
            {error ? (
              <QueryStateNotice
                tone="error"
                title={t("assistant.replyFailed")}
                description={error.message}
              />
            ) : null}

            <Conversation className="rounded-2xl border border-border bg-background/40">
              <ConversationContent className="min-h-[420px]">
                {messages.length === 0 ? (
                  <ConversationEmptyState
                    icon={<Bot className="size-5" />}
                    title={t("assistant.noRepliesYet")}
                    description={
                      leadId
                        ? t("assistant.noRepliesWithLead")
                        : t("assistant.noRepliesWorkspace")
                    }
                  />
                ) : (
                  messages.map((message) => (
                    <Message from={message.role} key={message.id}>
                      <MessageContent>
                        {message.parts.map((part, index) => {
                          if (part.type !== "text") {
                            return null;
                          }
                          return (
                            <MessageResponse
                              key={`${message.id}-${index}`}
                              className="ai-markdown"
                            >
                              {part.text}
                            </MessageResponse>
                          );
                        })}
                        {message.role === "assistant" ? (
                          <AssistantSearchEvidence message={message} />
                        ) : null}
                      </MessageContent>
                    </Message>
                  ))
                )}
              </ConversationContent>
              <ConversationScrollButton />
            </Conversation>

            <PromptInput
              className="mt-4"
              onSubmit={async (message) => {
                await submitPrompt(message.text);
              }}
            >
              <PromptInputBody>
                <PromptInputTextarea
                  value={input}
                  onChange={(event) => setInput(event.currentTarget.value)}
                  placeholder={
                    leadId
                      ? t("assistant.placeholderWithLead")
                      : t("assistant.placeholderWorkspace")
                  }
                />
              </PromptInputBody>
              <PromptInputFooter>
                <PromptInputTools>
                  <div className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
                    <CornerDownRight className="size-3" />
                    {leadId
                      ? t("assistant.scopeLabel")
                      : t("assistant.scopeLabelWorkspace")}
                  </div>
                </PromptInputTools>
                <PromptInputSubmit
                  disabled={!input.trim() && !isStreaming}
                  onStop={stop}
                  status={status}
                />
              </PromptInputFooter>
            </PromptInput>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ContextMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background/70 p-3">
      <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}

export function AssistantSearchEvidence({ message }: { message: UIMessage }) {
  const { t } = useTranslation();
  const searchData = getSearchData(message);
  if (!searchData) {
    return null;
  }

  const sources = searchData.sources ?? [];
  if (searchData.search_status === "not_needed" && sources.length === 0) {
    return null;
  }

  const statusLabel =
    searchData.search_status === "used"
      ? t("assistant.searchUsed")
      : searchData.search_status === "unavailable"
        ? t("assistant.searchUnavailable")
        : searchData.search_status === "failed"
          ? t("assistant.searchFailed")
          : t("assistant.basedOnSystemData");

  return (
    <div className="mt-3 w-full max-w-xl rounded-lg border border-border bg-muted/20 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
        <SearchCheck className="size-3.5" />
        <span className="font-medium text-foreground">{statusLabel}</span>
        {sources.length > 0 ? (
          <span>{t("assistant.externalEvidence")}</span>
        ) : null}
      </div>

      {sources.length > 0 ? (
        <div className="mt-2 grid gap-2">
          <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            {t("assistant.sources")}
          </div>
          {sources.map((source) => (
            <a
              key={source.url}
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="block rounded-md border border-border bg-background/70 p-2 transition hover:border-[oklch(var(--signal)/0.45)]"
            >
              <div className="flex min-w-0 items-center gap-1.5 font-medium text-foreground">
                <ExternalLink className="size-3 shrink-0" />
                <span className="truncate">{source.title || source.url}</span>
              </div>
              {source.snippet ? (
                <p className="mt-1 line-clamp-2 text-muted-foreground">
                  {source.snippet}
                </p>
              ) : null}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function getSearchData(message: UIMessage): AssistantSearchData | null {
  for (const part of message.parts) {
    if (part.type !== "data-search") {
      continue;
    }
    const data = part.data as Partial<AssistantSearchData> | undefined;
    if (!data || typeof data.search_status !== "string") {
      continue;
    }
    return {
      used_search: Boolean(data.used_search),
      search_status: data.search_status as AssistantSearchStatus,
      sources: Array.isArray(data.sources) ? data.sources : [],
    };
  }
  return null;
}
