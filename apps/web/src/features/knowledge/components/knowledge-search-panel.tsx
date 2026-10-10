import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorKeyFor } from "@/features/copilot/use-agent-run";

import { searchKnowledge } from "../api";

/** Lets a user check what the copilot would be able to cite before relying on it. */
export function KnowledgeSearchPanel() {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const search = useMutation({ mutationFn: (text: string) => searchKnowledge({ query: text, limit: 5 }) });
  const trimmed = query.trim();

  return (
    <section aria-labelledby="ks-title" className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div>
        <h2 id="ks-title" className="text-sm font-semibold">
          {t("knowledge.search.title")}
        </h2>
        <p className="text-xs text-muted-foreground">{t("knowledge.search.description")}</p>
      </div>
      <form
        className="flex gap-2"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          if (trimmed) search.mutate(trimmed);
        }}
      >
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("knowledge.search.placeholder")}
          aria-label={t("knowledge.search.title")}
          maxLength={500}
        />
        <Button type="submit" disabled={!trimmed || search.isPending}>
          <Search className="size-4" aria-hidden />
          {t("knowledge.search.run")}
        </Button>
      </form>

      <div aria-live="polite">
        {search.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {t(errorKeyFor(search.error))}
          </p>
        ) : null}
        {search.data ? (
          <div className="space-y-2">
            {search.data.degraded ? (
              <p className="rounded-md border border-border bg-muted/40 p-2 text-xs text-muted-foreground">
                {t("knowledge.search.degraded")}
              </p>
            ) : null}
            {search.data.results.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("knowledge.search.none")}</p>
            ) : (
              <ol className="space-y-2">
                {search.data.results.map((hit) => (
                  <li key={hit.chunk_id} className="rounded-md border border-border p-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-sm font-medium">
                        {hit.document_title}
                        {hit.section ? <span className="text-muted-foreground"> · {hit.section}</span> : null}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {t("knowledge.search.match", { percent: Math.round(hit.score * 100) })}
                      </span>
                    </div>
                    {/* Plain text only: indexed content is untrusted. */}
                    <p className="mt-1 line-clamp-4 whitespace-pre-line text-sm text-muted-foreground">
                      {hit.excerpt}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
