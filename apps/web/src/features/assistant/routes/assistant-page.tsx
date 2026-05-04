"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useChat } from "@ai-sdk/react";
import { Bot, CornerDownRight, MessageSquareText, Sparkles } from "lucide-react";
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { createAssistantTransport, type AssistantChatRequestBody } from "@/features/assistant/api";
import { getLead } from "@/features/leads/api";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { buildRequestUrl, readToken } from "@/lib/api-client";
import { formatScore } from "@/lib/presenters";

const STARTER_PROMPTS = [
  "Summarize the strongest evidence for this lead.",
  "What is the clearest outreach angle from the stored signals?",
  "Explain the main reasons behind this lead's current score.",
];

export function AssistantPage() {
  useDocumentTitle("AI Assistant");
  const [searchParams] = useSearchParams();
  const leadId = searchParams.get("leadId") ?? "";
  const [input, setInput] = useState("");

  const leadQuery = useQuery({
    queryKey: ["lead", leadId, "assistant-context"],
    queryFn: () => getLead(leadId),
    enabled: Boolean(leadId),
  });

  const transport = useMemo(() => {
    const body: AssistantChatRequestBody | undefined = leadId
      ? { lead_id: leadId, mode: "lead-assistant" }
      : { mode: "lead-assistant" };
    return createAssistantTransport(body);
  }, [leadId]);

  const { messages, sendMessage, status, stop, error, setMessages } = useChat<UIMessage>({
    transport,
  });

  const lead = leadQuery.data;
  const isStreaming = status === "submitted" || status === "streaming";

  const submitPrompt = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) {
      return;
    }
    await sendMessage(
      { text: trimmed },
      {
        body: leadId ? { lead_id: leadId, mode: "lead-assistant" } : { mode: "lead-assistant" },
      },
    );
    setInput("");
  };

  return (
    <div className="grid gap-4 p-3 sm:p-4 lg:p-6">
      <PageHeader
        eyebrow="AI assistant"
        title="Lead-aware conversational workspace"
        description="Ask follow-up questions against stored lead evidence, current deterministic scoring, and the latest assistive analysis."
        actions={
          <Button variant="outline" className="bg-transparent" onClick={() => setMessages([])}>
            <MessageSquareText className="size-3.5" />
            Clear thread
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[0.78fr_1.22fr]">
        <Card className="rounded-[1.5rem] border-border bg-card/95">
          <CardHeader>
            <CardTitle>Grounding context</CardTitle>
            <CardDescription>
              The assistant stays tenant-scoped and only answers from stored facts and the active lead context.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {leadId ? (
              leadQuery.isPending ? (
                <QueryStateNotice
                  tone="loading"
                  title="Loading lead context"
                  description="Fetching the active lead record for grounded assistant replies."
                />
              ) : leadQuery.isError ? (
                <QueryStateNotice
                  tone="error"
                  title="Lead context unavailable"
                  description={leadQuery.error.message}
                />
              ) : lead ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <AiPill>Lead context attached</AiPill>
                    <ConfidenceBadge value={lead.data_confidence} />
                  </div>

                  <div>
                    <div className="text-lg font-semibold">{lead.company_name}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {lead.category ?? "Business"} · {lead.city ?? "Unknown city"}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <ContextMetric label="Score" value={formatScore(lead.latest_score)} />
                    <ContextMetric label="Band" value={lead.latest_band ?? "unscored"} />
                    <ContextMetric label="Reviews" value={String(lead.review_count)} />
                    <ContextMetric label="Website" value={lead.website_domain ?? "missing"} />
                  </div>
                </div>
              ) : null
            ) : (
              <QueryStateNotice
                tone="info"
                title="No lead selected"
                description="Open this assistant from a lead detail page to attach score and evidence context automatically."
              />
            )}

            <div className="rounded-2xl border border-border bg-muted/20 p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="size-4 text-[oklch(var(--signal))]" />
                Suggested prompts
              </div>
              <div className="mt-3 flex flex-col gap-2">
                {STARTER_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="rounded-xl border border-border bg-background/70 px-3 py-3 text-left text-sm transition hover:border-[oklch(var(--signal)/0.45)] hover:bg-background"
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
            <CardTitle>Conversation</CardTitle>
            <CardDescription>
              Streaming markdown responses rendered through AI Elements.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex min-h-[620px] flex-col">
            {error ? (
              <QueryStateNotice
                tone="error"
                title="Assistant reply failed"
                description={error.message}
              />
            ) : null}

            <Conversation className="rounded-2xl border border-border bg-background/40">
              <ConversationContent className="min-h-[420px]">
                {messages.length === 0 ? (
                  <ConversationEmptyState
                    icon={<Bot className="size-5" />}
                    title="No assistant replies yet"
                    description={
                      leadId
                        ? "Ask about score drivers, risks, or outreach angles for the attached lead."
                        : "Attach a lead context or start with a general workspace question."
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
                      ? "Ask about this lead's score, evidence, or outreach strategy..."
                      : "Ask about your workspace or attach lead context from a detail page..."
                  }
                />
              </PromptInputBody>
              <PromptInputFooter>
                <PromptInputTools>
                  <div className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
                    <CornerDownRight className="size-3" />
                    {leadId ? "Lead-scoped assistant" : "Workspace-scoped assistant"}
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
      <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}
