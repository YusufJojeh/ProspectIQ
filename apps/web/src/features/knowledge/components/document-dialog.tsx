import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { errorKeyFor } from "@/features/copilot/use-agent-run";
import { useReturnFocus } from "@/hooks/use-return-focus";
import type {
  KnowledgeCollection,
  KnowledgeDocument,
  KnowledgeIngestion,
  KnowledgeVisibility,
} from "@/types/knowledge";

import { createKnowledgeDocument, reingestKnowledgeDocument } from "../api";
import {
  ACCEPTED_EXTENSIONS,
  MAX_DOCUMENT_CHARS,
  readKnowledgeFile,
  type FileReadFailure,
} from "../read-knowledge-file";

interface DocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  collections: KnowledgeCollection[];
  /** When set, the dialog replaces this document's content instead of creating one. */
  replacing: KnowledgeDocument | null;
  defaultCollectionId: string | null;
  canCreateRestricted: boolean;
  onFinished: (result: KnowledgeIngestion) => void;
}

export function DocumentDialog({
  open,
  onOpenChange,
  collections,
  replacing,
  defaultCollectionId,
  canCreateRestricted,
  onFinished,
}: DocumentDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const returnFocus = useReturnFocus(open);
  const fileInput = useRef<HTMLInputElement>(null);
  const [collectionId, setCollectionId] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [visibility, setVisibility] = useState<KnowledgeVisibility>("workspace");
  const [fileError, setFileError] = useState<FileReadFailure | null>(null);

  useEffect(() => {
    if (!open) return;
    setCollectionId(replacing?.collection_id ?? defaultCollectionId ?? collections[0]?.collection_id ?? "");
    setTitle(replacing?.title ?? "");
    setVisibility(replacing ? (replacing.visibility as KnowledgeVisibility) : "workspace");
    setContent("");
    setFileError(null);
  }, [open, replacing, defaultCollectionId, collections]);

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        collection_id: collectionId,
        title: title.trim(),
        content,
        visibility,
      };
      return replacing
        ? reingestKnowledgeDocument(replacing.document_id, payload)
        : createKnowledgeDocument(payload);
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge"] });
      onFinished(result);
      if (result.status !== "failed") onOpenChange(false);
    },
  });

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const result = await readKnowledgeFile(file);
    if (!result.ok) {
      setFileError(result.reason);
      return;
    }
    setFileError(null);
    setContent(result.text);
    if (!title.trim()) setTitle(result.suggestedTitle);
  }

  const tooLong = content.length > MAX_DOCUMENT_CHARS;
  const canSubmit =
    !save.isPending && collectionId !== "" && title.trim() !== "" && content.trim() !== "" && !tooLong;
  const visibilityOptions: KnowledgeVisibility[] = canCreateRestricted
    ? ["workspace", "private", "restricted"]
    : ["workspace", "private"];

  return (
    <Dialog open={open} onOpenChange={(next) => (save.isPending ? undefined : onOpenChange(next))}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl" onCloseAutoFocus={returnFocus.onCloseAutoFocus}>
        <DialogHeader>
          <DialogTitle>{replacing ? t("knowledge.dialog.replaceTitle") : t("knowledge.dialog.addTitle")}</DialogTitle>
          <DialogDescription>
            {replacing ? t("knowledge.dialog.replaceDescription") : t("knowledge.dialog.addDescription")}
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmit) save.mutate();
          }}
        >
          {!replacing ? (
            <div className="space-y-1.5">
              <Label htmlFor="kd-collection">{t("knowledge.dialog.collection")}</Label>
              <Select value={collectionId} onValueChange={setCollectionId}>
                <SelectTrigger id="kd-collection">
                  <SelectValue placeholder={t("knowledge.dialog.collectionPlaceholder")} />
                </SelectTrigger>
                <SelectContent>
                  {collections.map((collection) => (
                    <SelectItem key={collection.collection_id} value={collection.collection_id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="space-y-1.5">
            <Label htmlFor="kd-title">{t("knowledge.dialog.docTitle")}</Label>
            <Input
              id="kd-title"
              value={title}
              maxLength={300}
              disabled={Boolean(replacing)}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>

          {!replacing ? (
            <fieldset className="space-y-1.5">
              <legend className="text-sm font-medium">{t("knowledge.dialog.visibility")}</legend>
              <Select value={visibility} onValueChange={(value) => setVisibility(value as KnowledgeVisibility)}>
                <SelectTrigger aria-label={t("knowledge.dialog.visibility")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {visibilityOptions.map((option) => (
                    <SelectItem key={option} value={option}>
                      {t(`knowledge.visibility.${option}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{t(`knowledge.visibilityHint.${visibility}`)}</p>
            </fieldset>
          ) : null}

          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="kd-content">{t("knowledge.dialog.content")}</Label>
              <Button type="button" size="sm" variant="outline" className="bg-transparent" onClick={() => fileInput.current?.click()}>
                <FileUp className="size-3.5" aria-hidden />
                {t("knowledge.dialog.upload")}
              </Button>
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPTED_EXTENSIONS.join(",")}
                className="sr-only"
                tabIndex={-1}
                aria-hidden
                onChange={(event) => void onFile(event)}
              />
            </div>
            <Textarea
              id="kd-content"
              rows={9}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              aria-describedby="kd-content-help"
              aria-invalid={tooLong || fileError !== null}
            />
            <p id="kd-content-help" className="text-xs text-muted-foreground">
              {t("knowledge.dialog.contentHelp", { formats: ACCEPTED_EXTENSIONS.join(", ") })}{" "}
              {content.length > 0
                ? t("knowledge.dialog.charCount", {
                    count: content.length,
                    max: MAX_DOCUMENT_CHARS.toLocaleString(),
                  })
                : null}
            </p>
            {fileError ? (
              <p role="alert" className="text-sm text-destructive">
                {t(`knowledge.fileErrors.${fileError}`, { formats: ACCEPTED_EXTENSIONS.join(", ") })}
              </p>
            ) : null}
            {tooLong ? (
              <p role="alert" className="text-sm text-destructive">
                {t("knowledge.fileErrors.tooLarge")}
              </p>
            ) : null}
          </div>

          {save.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {t(errorKeyFor(save.error))}
            </p>
          ) : null}
          {save.data?.status === "failed" ? (
            <p role="alert" className="text-sm text-destructive">
              {t("knowledge.ingestion.failed")}
            </p>
          ) : null}

          <DialogFooter className="gap-2">
            <Button type="button" variant="ghost" disabled={save.isPending} onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={!canSubmit}>
              {save.isPending
                ? t("knowledge.ingestion.indexing")
                : replacing
                  ? t("knowledge.dialog.replace")
                  : t("knowledge.dialog.add")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
