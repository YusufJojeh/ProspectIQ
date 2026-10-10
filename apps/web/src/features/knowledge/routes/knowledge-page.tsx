import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, FilePlus2, FolderPlus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shell/page-header";
import { QueryStateNotice } from "@/components/shared/query-state-notice";
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
import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";
import { errorKeyFor } from "@/features/copilot/use-agent-run";
import { useAuthSession } from "@/features/auth/session";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { useReturnFocus } from "@/hooks/use-return-focus";
import { formatWhen } from "@/features/leads/research-format";
import {
  KNOWLEDGE_COLLECTION_TYPES,
  type KnowledgeCollectionType,
  type KnowledgeDocument,
  type KnowledgeIngestion,
} from "@/types/knowledge";

import {
  createKnowledgeCollection,
  deleteKnowledgeDocument,
  listKnowledgeCollections,
  listKnowledgeDocuments,
} from "../api";
import { DocumentDialog } from "../components/document-dialog";
import { KnowledgeSearchPanel } from "../components/knowledge-search-panel";

const ELEVATED_ROLES = new Set(["platform_admin", "account_owner", "admin", "manager"]);

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

export function KnowledgePage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuthSession();
  const queryClient = useQueryClient();
  useDocumentTitle(t("knowledge.title"));

  const [collectionFilter, setCollectionFilter] = useState<string>("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [replacing, setReplacing] = useState<KnowledgeDocument | null>(null);
  const [collectionDialog, setCollectionDialog] = useState(false);
  const [toArchive, setToArchive] = useState<KnowledgeDocument | null>(null);
  const archiveFocus = useReturnFocus(toArchive !== null);

  const collections = useQuery({ queryKey: ["knowledge", "collections"], queryFn: listKnowledgeCollections });
  const documents = useQuery({
    queryKey: ["knowledge", "documents", collectionFilter],
    queryFn: () =>
      listKnowledgeDocuments({ collectionId: collectionFilter === "all" ? undefined : collectionFilter }),
  });

  const collectionList = useMemo(() => collections.data?.collections ?? [], [collections.data]);
  const collectionNames = useMemo(
    () => new Map(collectionList.map((collection) => [collection.collection_id, collection.name])),
    [collectionList],
  );
  // Archived documents are removed from answers, so they are not shown as usable knowledge.
  const visibleDocuments = (documents.data?.documents ?? []).filter((doc) => doc.status !== "archived");
  const canCreateRestricted = user ? ELEVATED_ROLES.has(user.role) : false;

  const archive = useMutation({
    mutationFn: (documentId: string) => deleteKnowledgeDocument(documentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge"] });
      toast.success(t("knowledge.toasts.archived"));
      setToArchive(null);
    },
  });

  function announceIngestion(result: KnowledgeIngestion) {
    if (result.status === "skipped_unchanged") toast.info(t("knowledge.ingestion.unchanged"));
    else if (result.status === "failed") toast.error(t("knowledge.ingestion.failed"));
    else if (result.fallback_used) toast.warning(t("knowledge.ingestion.keywordOnly", { count: result.chunk_count }));
    else toast.success(t("knowledge.ingestion.done", { count: result.chunk_count }));
  }

  function openAdd() {
    setReplacing(null);
    setDialogOpen(true);
  }

  return (
    <div>
      <PageHeader
        title={t("knowledge.title")}
        description={t("knowledge.description")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="bg-transparent" onClick={() => setCollectionDialog(true)}>
              <FolderPlus className="size-4" aria-hidden />
              {t("knowledge.newCollection")}
            </Button>
            <Button onClick={openAdd} disabled={collectionList.length === 0}>
              <FilePlus2 className="size-4" aria-hidden />
              {t("knowledge.addDocument")}
            </Button>
          </div>
        }
      />

      <div className="mx-auto grid max-w-6xl gap-6 px-3 py-4 sm:px-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:px-6">
        <section aria-labelledby="kn-docs" className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="kn-docs" className="text-sm font-semibold">
              {t("knowledge.documents")}
            </h2>
            <Select value={collectionFilter} onValueChange={setCollectionFilter}>
              <SelectTrigger className="w-full sm:w-56" aria-label={t("knowledge.filterByCollection")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("knowledge.allCollections")}</SelectItem>
                {collectionList.map((collection) => (
                  <SelectItem key={collection.collection_id} value={collection.collection_id}>
                    {collection.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {documents.isPending ? (
            <div className="space-y-2" aria-busy="true" aria-label={t("common.loading")}>
              {[0, 1, 2].map((key) => (
                <Skeleton key={key} className="h-16 w-full" />
              ))}
            </div>
          ) : documents.isError ? (
            <div className="space-y-2">
              <QueryStateNotice tone="error" title={t("knowledge.loadError")} error={documents.error} />
              <Button variant="outline" size="sm" className="bg-transparent" onClick={() => void documents.refetch()}>
                <RefreshCw className="size-3.5" aria-hidden />
                {t("common.retry")}
              </Button>
            </div>
          ) : visibleDocuments.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border p-10 text-center">
              <BookOpen className="size-6 text-muted-foreground" aria-hidden />
              <p className="max-w-sm text-sm text-muted-foreground">
                {collectionList.length === 0 ? t("knowledge.emptyNoCollections") : t("knowledge.empty")}
              </p>
              {collectionList.length === 0 ? (
                <Button onClick={() => setCollectionDialog(true)}>{t("knowledge.newCollection")}</Button>
              ) : (
                <Button onClick={openAdd}>{t("knowledge.addDocument")}</Button>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-border rounded-lg border border-border bg-card">
              {visibleDocuments.map((doc) => (
                <li key={doc.document_id} className="flex flex-wrap items-center justify-between gap-3 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{doc.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {collectionNames.get(doc.collection_id) ?? "—"} · {t(`knowledge.visibility.${doc.visibility}`)} ·{" "}
                      {t("knowledge.chunkCount", { count: doc.chunk_count })} · {formatWhen(doc.updated_at, i18n.language)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={doc.status === "failed" ? "destructive" : "secondary"}>
                      {t(`knowledge.status.${doc.status}`)}
                    </Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      className="bg-transparent"
                      onClick={() => {
                        setReplacing(doc);
                        setDialogOpen(true);
                      }}
                      aria-label={t("knowledge.replaceAria", { title: doc.title })}
                    >
                      <RefreshCw className="size-3.5" aria-hidden />
                      {t("knowledge.replace")}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => setToArchive(doc)}
                      aria-label={t("knowledge.archiveAria", { title: doc.title })}
                    >
                      <Trash2 className="size-4" aria-hidden />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <KnowledgeSearchPanel />
      </div>

      <DocumentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        collections={collectionList}
        replacing={replacing}
        defaultCollectionId={collectionFilter === "all" ? null : collectionFilter}
        canCreateRestricted={canCreateRestricted}
        onFinished={announceIngestion}
      />

      <CollectionDialog open={collectionDialog} onOpenChange={setCollectionDialog} />

      <AlertDialog open={toArchive !== null} onOpenChange={(open) => (open ? undefined : setToArchive(null))}>
        <AlertDialogContent onCloseAutoFocus={archiveFocus.onCloseAutoFocus}>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("knowledge.archiveTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("knowledge.archiveDescription", { title: toArchive?.title ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {archive.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {t(errorKeyFor(archive.error))}
            </p>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={archive.isPending}>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              disabled={archive.isPending}
              onClick={(event) => {
                event.preventDefault();
                if (toArchive) archive.mutate(toArchive.document_id);
              }}
            >
              {t("knowledge.archiveConfirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function CollectionDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const returnFocus = useReturnFocus(open);
  const [name, setName] = useState("");
  const [type, setType] = useState<KnowledgeCollectionType>("services");

  const create = useMutation({
    mutationFn: () => createKnowledgeCollection({ name: name.trim(), slug: slugify(name), collection_type: type }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge"] });
      toast.success(t("knowledge.toasts.collectionCreated"));
      setName("");
      onOpenChange(false);
    },
  });
  const canSubmit = name.trim() !== "" && slugify(name) !== "" && !create.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" onCloseAutoFocus={returnFocus.onCloseAutoFocus}>
        <DialogHeader>
          <DialogTitle>{t("knowledge.collectionDialog.title")}</DialogTitle>
          <DialogDescription>{t("knowledge.collectionDialog.description")}</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (canSubmit) create.mutate();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="kc-name">{t("knowledge.collectionDialog.name")}</Label>
            <Input id="kc-name" value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="kc-type">{t("knowledge.collectionDialog.type")}</Label>
            <Select value={type} onValueChange={(value) => setType(value as KnowledgeCollectionType)}>
              <SelectTrigger id="kc-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {KNOWLEDGE_COLLECTION_TYPES.map((option) => (
                  <SelectItem key={option} value={option}>
                    {t(`knowledge.collectionTypes.${option}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {create.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {t(errorKeyFor(create.error))}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={!canSubmit}>
              {t("common.create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
