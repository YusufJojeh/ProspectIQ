import { useTranslation } from "react-i18next";
import { BookOpen, ExternalLink, FileSearch } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { displayHost, safeHttpUrl } from "@/lib/safe-url";
import type { AgentAction, AgentFinalAnswer } from "@/types/agent";

import { actionStatusPresentation, buildActionView } from "../action-preview";
import type { KnowledgeDocRef } from "../agent-state";

export interface EvidenceLabel {
  label: string;
  url: string | null;
}

interface FinalAnswerProps {
  answer: AgentFinalAnswer;
  /** Documents the run actually retrieved, by id. */
  knowledge: Record<string, KnowledgeDocRef>;
  /** Evidence ref -> readable label/url, from the Evidence Graph. */
  evidenceIndex: Map<string, EvidenceLabel>;
  actions: AgentAction[];
  onAsk: (question: string) => void;
  asking: boolean;
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/**
 * Answer hierarchy: conclusion, then what the lead's evidence says, then what
 * our internal knowledge says, then what happened / is waiting. Lead evidence
 * and internal knowledge are always separate sections and never mixed.
 */
export function FinalAnswerView({ answer, knowledge, evidenceIndex, actions, onAsk, asking }: FinalAnswerProps) {
  const { t } = useTranslation();
  const knowledgeDocs = answer.knowledge_refs.map((id) => knowledge[id] ?? null);

  return (
    <section aria-labelledby="copilot-answer-title" className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 id="copilot-answer-title" className="text-sm font-semibold">
            {t("copilot.answer.title")}
          </h3>
          <Badge tone="neutral">{t("copilot.answer.confidence", { value: percent(answer.confidence) })}</Badge>
          <Badge tone="neutral">{t("copilot.answer.coverage", { value: percent(answer.research_coverage) })}</Badge>
        </div>
        {/* Plain text on purpose: model output is never interpreted as HTML or markdown. */}
        <p className="mt-2 whitespace-pre-line text-sm leading-6">{answer.answer}</p>
      </div>

      <BulletSection title={t("copilot.answer.opportunities")} items={answer.opportunities} />
      <BulletSection title={t("copilot.answer.risks")} items={answer.risks} />
      <BulletSection title={t("copilot.answer.recommended")} items={answer.recommended_actions} />

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <FileSearch className="size-3.5" aria-hidden />
            {t("copilot.answer.evidence")}
          </h4>
          {answer.evidence_refs.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">{t("copilot.answer.noEvidence")}</p>
          ) : (
            <ul className="mt-2 space-y-1.5 text-sm">
              {answer.evidence_refs.map((ref) => {
                const found = evidenceIndex.get(ref);
                const href = safeHttpUrl(found?.url);
                return (
                  <li key={ref} className="flex items-center gap-1.5">
                    <span className="min-w-0 break-words">{found?.label ?? t("copilot.answer.evidenceItem")}</span>
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        aria-label={t("copilot.answer.openSource", { host: displayHost(href) ?? "" })}
                        className="shrink-0 text-muted-foreground hover:text-foreground"
                      >
                        <ExternalLink className="size-3.5" aria-hidden />
                      </a>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div>
          <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <BookOpen className="size-3.5" aria-hidden />
            {t("copilot.answer.knowledge")}
          </h4>
          {knowledgeDocs.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">{t("copilot.answer.noKnowledge")}</p>
          ) : (
            <ul className="mt-2 space-y-1.5 text-sm">
              {knowledgeDocs.map((doc, index) => (
                <li key={answer.knowledge_refs[index]} className="break-words">
                  {doc?.title ?? t("copilot.answer.knowledgeItem")}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-muted-foreground">{t("copilot.answer.knowledgeNote")}</p>
        </div>
      </div>

      {actions.length > 0 ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("copilot.answer.actions")}
          </h4>
          <ul className="mt-2 space-y-1.5 text-sm">
            {actions.map((action) => {
              const status = actionStatusPresentation(action.status);
              return (
                <li key={action.action_id} className="flex flex-wrap items-center gap-2">
                  <span>{t(buildActionView(action).titleKey)}</span>
                  <Badge tone={status.tone}>{t(status.labelKey)}</Badge>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {answer.follow_up_questions.length > 0 ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("copilot.answer.followUps")}
          </h4>
          <div className="mt-2 flex flex-wrap gap-2">
            {answer.follow_up_questions.map((question) => (
              <Button
                key={question}
                size="sm"
                variant="outline"
                className="h-auto whitespace-normal bg-transparent py-1.5 text-start"
                disabled={asking}
                onClick={() => onAsk(question)}
              >
                {question}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function BulletSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h4>
      <ul className="mt-2 list-disc space-y-1 ps-5 text-sm">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
