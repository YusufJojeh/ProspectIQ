import { useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFieldArray, useForm, useWatch, type Control, type FieldPath } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import {
  CheckCircle2,
  CircleAlert,
  Copy,
  FileDown,
  Plus,
  Save,
  Send,
  ThumbsDown,
  ThumbsUp,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { appPaths } from "@/app/paths";
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { resolveErrorMessage } from "@/lib/error-messages";
import type { Proposal, ProposalBrand, ProposalDecision } from "@/types/proposals";

import {
  getProposal,
  listProposalBrands,
  markProposalReady,
  markProposalSent,
  proposalKeys,
  recordProposalDecision,
  updateProposal,
} from "../api";
import { ScaledProposalDocument, documentTotals } from "../components/proposal-document";
import { coverEmail } from "../document-labels";
import {
  proposalFormSchema,
  toDocumentData,
  toFormValues,
  toUpdateRequest,
  type ProposalFormValues,
} from "../form";
import { formatMoney, parseMinor } from "../money";
import { isEditable, proposalStatusTone } from "../status";

export function ProposalPage() {
  const { t } = useTranslation();
  const { proposalId = "" } = useParams();
  const proposalQuery = useQuery({
    queryKey: proposalKeys.detail(proposalId),
    queryFn: () => getProposal(proposalId),
    enabled: proposalId !== "",
  });
  // Archived brands are included so a draft still on one keeps rendering it.
  const brandsQuery = useQuery({
    queryKey: proposalKeys.brandList(true),
    queryFn: () => listProposalBrands(true),
  });
  useDocumentTitle(proposalQuery.data?.number ?? t("proposals.title"));

  if (proposalQuery.isPending || brandsQuery.isPending) {
    return (
      <div className="mx-auto grid max-w-7xl gap-6 px-3 py-6 sm:px-4 lg:px-6 xl:grid-cols-2">
        <Skeleton className="h-[36rem] rounded-[1.5rem]" />
        <Skeleton className="h-[36rem] rounded-[1.5rem]" />
      </div>
    );
  }
  if (proposalQuery.isError || brandsQuery.isError) {
    return (
      <div className="mx-auto max-w-3xl px-3 py-6">
        <QueryStateNotice
          tone="error"
          title={t("proposals.loadError")}
          error={proposalQuery.error ?? brandsQuery.error}
        />
      </div>
    );
  }
  return (
    // Keyed so a saved response resets the form to exactly what the server stored.
    <ProposalWorkspace
      key={`${proposalQuery.data.public_id}:${proposalQuery.data.updated_at}`}
      proposal={proposalQuery.data}
      brands={brandsQuery.data.items.filter(
        (brand) => !brand.archived || brand.public_id === proposalQuery.data.brand.public_id,
      )}
    />
  );
}

function ProposalWorkspace({ proposal, brands }: { proposal: Proposal; brands: ProposalBrand[] }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const editable = isEditable(proposal.status);
  const [confirmSent, setConfirmSent] = useState(false);

  const form = useForm<ProposalFormValues>({
    resolver: zodResolver(proposalFormSchema),
    defaultValues: toFormValues(proposal),
    mode: "onChange",
  });
  const { fields, append, remove } = useFieldArray({ control: form.control, name: "milestones" });
  const dirty = form.formState.isDirty;

  function applyServer(next: Proposal) {
    queryClient.setQueryData(proposalKeys.detail(next.public_id), next);
    void queryClient.invalidateQueries({ queryKey: ["proposals", "list"] });
  }

  async function saveIfDirty(): Promise<Proposal> {
    if (!form.formState.isDirty) return proposal;
    const valid = await form.trigger();
    if (!valid) throw new Error(t("proposals.fixFormErrors"));
    return updateProposal(proposal.public_id, toUpdateRequest(form.getValues()));
  }

  const saveMutation = useMutation({
    mutationFn: saveIfDirty,
    onSuccess: (next) => {
      applyServer(next);
      toast.success(t("proposals.saved"));
    },
    onError: (error) => toast.error(resolveErrorMessage(error, t)),
  });

  const readyMutation = useMutation({
    mutationFn: async () => {
      const saved = await saveIfDirty();
      return markProposalReady(saved.public_id);
    },
    onSuccess: (next) => {
      applyServer(next);
      toast.success(t("proposals.markedReady"));
    },
    onError: (error) => {
      void queryClient.invalidateQueries({ queryKey: proposalKeys.detail(proposal.public_id) });
      toast.error(resolveErrorMessage(error, t));
    },
  });

  const sentMutation = useMutation({
    mutationFn: () => markProposalSent(proposal.public_id),
    onSuccess: (next) => {
      applyServer(next);
      toast.success(t("proposals.markedSent"));
    },
    onError: (error) => toast.error(resolveErrorMessage(error, t)),
  });

  const decisionMutation = useMutation({
    mutationFn: (decision: ProposalDecision) => recordProposalDecision(proposal.public_id, decision),
    onSuccess: (next) => applyServer(next),
    onError: (error) => toast.error(resolveErrorMessage(error, t)),
  });

  const busy =
    saveMutation.isPending || readyMutation.isPending || sentMutation.isPending || decisionMutation.isPending;

  function downloadPdf() {
    // The browser's print dialog saves the A4 page as a PDF; the title
    // becomes the suggested file name.
    const previous = document.title;
    document.title = `${proposal.number} - ${proposal.client_company}`.replace(/[\\/:*?"<>|]/g, "");
    window.addEventListener("afterprint", () => (document.title = previous), { once: true });
    window.print();
  }

  async function copyCoverEmail() {
    const email = coverEmail({
      language: proposal.language,
      number: proposal.number,
      title: proposal.title,
      clientCompany: proposal.client_company,
      contactName: proposal.client_contact_name,
      total: formatMoney(proposal.currency, proposal.totals.total_minor),
      validUntil: proposal.valid_until,
      senderName: proposal.brand.name,
    });
    try {
      await navigator.clipboard.writeText(`${email.subject}\n\n${email.body}`);
      toast.success(t("proposals.coverCopied"));
    } catch {
      toast.error(t("proposals.copyFailed"));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("proposals.eyebrow")}
        title={proposal.title || proposal.number}
        description={t("proposals.detailDescription", {
          number: proposal.number,
          company: proposal.lead_company_name,
        })}
        actions={
          <>
            <Badge tone={proposalStatusTone(proposal.status)}>
              {t(`proposals.status.${proposal.status}`)}
            </Badge>
            <Button asChild size="sm" variant="ghost">
              <Link to={appPaths.leadDetail(proposal.lead_id)}>{t("proposals.openLead")}</Link>
            </Button>
          </>
        }
      />

      <div className="mx-auto grid max-w-7xl gap-6 px-3 py-4 sm:px-4 lg:px-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <ReadinessCard proposal={proposal} dirty={dirty} />

          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader>
              <CardTitle role="heading" aria-level={2}>
                {t("proposals.editorTitle")}
              </CardTitle>
              <CardDescription>
                {editable ? t("proposals.editorDescription") : t("proposals.lockedDescription")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit(() => saveMutation.mutate())}
                  className="space-y-6"
                  noValidate
                >
                  <fieldset disabled={!editable || busy} className="space-y-6">
                    <section className="grid gap-4 sm:grid-cols-2">
                      <FormField
                        control={form.control}
                        name="brand_id"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{t("proposals.fields.brand")}</FormLabel>
                            <Select value={field.value} onValueChange={field.onChange} disabled={!editable}>
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {brands.map((brand) => (
                                  <SelectItem key={brand.public_id} value={brand.public_id}>
                                    {brand.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="language"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{t("proposals.fields.language")}</FormLabel>
                            <Select value={field.value} onValueChange={field.onChange} disabled={!editable}>
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="en">{t("proposals.languages.en")}</SelectItem>
                                <SelectItem value="ar">{t("proposals.languages.ar")}</SelectItem>
                              </SelectContent>
                            </Select>
                          </FormItem>
                        )}
                      />
                      <TextField control={form.control} name="title" label={t("proposals.fields.title")} wide />
                    </section>

                    <section className="space-y-3">
                      <h3 className="text-sm font-semibold">{t("proposals.sections.client")}</h3>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <TextField control={form.control} name="client_company" label={t("proposals.fields.clientCompany")} />
                        <TextField control={form.control} name="client_contact_name" label={t("proposals.fields.contactName")} />
                        <TextField control={form.control} name="client_email" label={t("proposals.fields.clientEmail")} type="email" />
                        <TextField control={form.control} name="client_location" label={t("proposals.fields.location")} />
                      </div>
                    </section>

                    <section className="grid gap-4 sm:grid-cols-3">
                      <TextField control={form.control} name="currency" label={t("proposals.fields.currency")} />
                      <TextField control={form.control} name="issue_date" label={t("proposals.fields.issueDate")} type="date" />
                      <TextField control={form.control} name="valid_until" label={t("proposals.fields.validUntil")} type="date" />
                    </section>

                    <TextAreaField control={form.control} name="outcome" label={t("proposals.fields.outcome")} rows={3} />

                    <section className="space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-sm font-semibold">{t("proposals.sections.milestones")}</h3>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="bg-transparent"
                          disabled={!editable || fields.length >= 12}
                          onClick={() => append({ title: "", description: "", amount: "" })}
                        >
                          <Plus className="size-3.5" aria-hidden />
                          {t("proposals.addMilestone")}
                        </Button>
                      </div>
                      {fields.length === 0 ? (
                        <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                          {t("proposals.noMilestones")}
                        </p>
                      ) : null}
                      <ol className="space-y-3">
                        {fields.map((field, index) => (
                          <li key={field.id} className="rounded-xl border border-border p-3">
                            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_9rem_auto] sm:items-start">
                              <TextField
                                control={form.control}
                                name={`milestones.${index}.title`}
                                label={t("proposals.fields.milestoneTitle", { index: index + 1 })}
                              />
                              <TextField
                                control={form.control}
                                name={`milestones.${index}.amount`}
                                label={t("proposals.fields.amount")}
                                inputMode="decimal"
                                placeholder={t("proposals.amountPlaceholder")}
                              />
                              <Button
                                type="button"
                                size="icon"
                                variant="ghost"
                                className="sm:mt-6"
                                disabled={!editable}
                                aria-label={t("proposals.removeMilestone", { index: index + 1 })}
                                onClick={() => remove(index)}
                              >
                                <Trash2 className="size-4" aria-hidden />
                              </Button>
                            </div>
                            <div className="mt-3">
                              <TextAreaField
                                control={form.control}
                                name={`milestones.${index}.description`}
                                label={t("proposals.fields.milestoneDescription")}
                                rows={2}
                              />
                            </div>
                          </li>
                        ))}
                      </ol>
                      <MilestoneTotals control={form.control} />
                    </section>

                    <section className="grid gap-4 sm:grid-cols-2">
                      <TextAreaField control={form.control} name="commercial_notes" label={t("proposals.fields.commercialNotes")} rows={4} />
                      <TextAreaField control={form.control} name="validity_notes" label={t("proposals.fields.validityNotes")} rows={4} />
                    </section>
                    <TextField control={form.control} name="sender_contact" label={t("proposals.fields.senderContact")} />
                  </fieldset>

                  {editable ? (
                    <div className="sticky bottom-0 -mx-6 flex flex-wrap gap-2 border-t border-border bg-card/95 px-6 py-3 backdrop-blur">
                      <Button type="submit" disabled={!dirty || busy}>
                        <Save className="size-4" aria-hidden />
                        {saveMutation.isPending ? t("proposals.saving") : t("common.save")}
                      </Button>
                      {dirty ? (
                        <Button
                          type="button"
                          variant="ghost"
                          disabled={busy}
                          onClick={() => form.reset(toFormValues(proposal))}
                        >
                          {t("proposals.discardChanges")}
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </form>
              </Form>
            </CardContent>
          </Card>
        </div>

        <div className="min-w-0 space-y-4 xl:sticky xl:top-4 xl:self-start">
          <Card className="rounded-[1.5rem] border-border bg-card/95">
            <CardHeader className="pb-3">
              <CardTitle role="heading" aria-level={2}>
                {t("proposals.sendTitle")}
              </CardTitle>
              <CardDescription>{t(`proposals.sendHint.${proposal.status}`)}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {editable ? (
                <Button
                  onClick={() => readyMutation.mutate()}
                  disabled={busy || (proposal.status === "ready" && !dirty)}
                >
                  <CheckCircle2 className="size-4" aria-hidden />
                  {readyMutation.isPending ? t("proposals.checking") : t("proposals.markReady")}
                </Button>
              ) : null}
              <Button variant="outline" className="bg-transparent" onClick={downloadPdf} disabled={dirty}>
                <FileDown className="size-4" aria-hidden />
                {t("proposals.downloadPdf")}
              </Button>
              <Button variant="outline" className="bg-transparent" onClick={() => void copyCoverEmail()} disabled={dirty}>
                <Copy className="size-4" aria-hidden />
                {t("proposals.copyCoverEmail")}
              </Button>
              {proposal.status === "ready" ? (
                <Button variant="secondary" onClick={() => setConfirmSent(true)} disabled={busy || dirty}>
                  <Send className="size-4" aria-hidden />
                  {t("proposals.markSent")}
                </Button>
              ) : null}
              {proposal.status === "sent" ? (
                <>
                  <Button variant="secondary" onClick={() => decisionMutation.mutate("accepted")} disabled={busy}>
                    <ThumbsUp className="size-4" aria-hidden />
                    {t("proposals.markAccepted")}
                  </Button>
                  <Button variant="ghost" onClick={() => decisionMutation.mutate("declined")} disabled={busy}>
                    <ThumbsDown className="size-4" aria-hidden />
                    {t("proposals.markDeclined")}
                  </Button>
                </>
              ) : null}
              {dirty ? (
                <p className="w-full text-xs text-muted-foreground">{t("proposals.saveBeforeExport")}</p>
              ) : null}
            </CardContent>
          </Card>

          <PreviewPane control={form.control} proposal={proposal} brands={brands} />
        </div>
      </div>

      <AlertDialog open={confirmSent} onOpenChange={setConfirmSent}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("proposals.confirmSentTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("proposals.confirmSentDescription", { number: proposal.number })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={() => sentMutation.mutate()}>{t("proposals.markSent")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

type FieldName = FieldPath<ProposalFormValues>;

function TextField({
  control,
  name,
  label,
  type = "text",
  wide = false,
  inputMode,
  placeholder,
}: {
  control: Control<ProposalFormValues>;
  name: FieldName;
  label: string;
  type?: string;
  wide?: boolean;
  inputMode?: "decimal" | "text";
  placeholder?: string;
}) {
  const { t } = useTranslation();
  return (
    <FormField
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <FormItem className={wide ? "sm:col-span-2" : undefined}>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input
              type={type}
              inputMode={inputMode}
              placeholder={placeholder}
              name={field.name}
              ref={field.ref}
              onBlur={field.onBlur}
              onChange={field.onChange}
              value={typeof field.value === "string" ? field.value : ""}
              dir={type === "email" ? "ltr" : undefined}
            />
          </FormControl>
          {fieldState.error ? (
            <p role="alert" className="text-xs text-destructive">
              {t(`proposals.errors.${fieldState.error.message ?? "invalid"}`, {
                defaultValue: t("proposals.errors.invalid"),
              })}
            </p>
          ) : null}
        </FormItem>
      )}
    />
  );
}

function TextAreaField({
  control,
  name,
  label,
  rows,
}: {
  control: Control<ProposalFormValues>;
  name: FieldName;
  label: string;
  rows: number;
}) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Textarea
              rows={rows}
              name={field.name}
              ref={field.ref}
              onBlur={field.onBlur}
              onChange={field.onChange}
              value={typeof field.value === "string" ? field.value : ""}
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

function MilestoneTotals({ control }: { control: Control<ProposalFormValues> }) {
  const { t } = useTranslation();
  const values = useWatch({ control });
  const currency = (values.currency ?? "").toUpperCase();
  const totals = useMemo(
    () =>
      documentTotals(
        (values.milestones ?? []).map((line) => ({
          title: "",
          description: "",
          amount_minor: parseMinor(line.amount ?? "") ?? null,
        })),
      ),
    [values.milestones],
  );
  return (
    <dl className="grid grid-cols-3 gap-2 rounded-xl bg-muted/40 p-3 text-xs">
      <div>
        <dt className="text-muted-foreground">{t("proposals.deposit")}</dt>
        <dd className="font-mono font-medium tabular-nums">{formatMoney(currency, totals.deposit)}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground">{t("proposals.remaining")}</dt>
        <dd className="font-mono font-medium tabular-nums">{formatMoney(currency, totals.remaining)}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground">{t("proposals.total")}</dt>
        <dd className="font-mono font-semibold tabular-nums">{formatMoney(currency, totals.total)}</dd>
      </div>
    </dl>
  );
}

function PreviewPane({
  control,
  proposal,
  brands,
}: {
  control: Control<ProposalFormValues>;
  proposal: Proposal;
  brands: ProposalBrand[];
}) {
  const { t } = useTranslation();
  const values = useWatch({ control }) as ProposalFormValues;
  // A sent proposal shows the brand frozen when it went out, never today's.
  const brand = isEditable(proposal.status)
    ? (brands.find((item) => item.public_id === values.brand_id) ?? proposal.brand)
    : proposal.brand;
  const data = toDocumentData(values, proposal.number, brand);
  return (
    <section aria-label={t("proposals.previewLabel")} className="space-y-2">
      <ScaledProposalDocument data={data} printable />
      {proposal.pricing_basis ? (
        <p className="text-xs text-muted-foreground">
          {t("proposals.pricingBasis")}: {proposal.pricing_basis}
        </p>
      ) : null}
    </section>
  );
}

function ReadinessCard({ proposal, dirty }: { proposal: Proposal; dirty: boolean }) {
  const { t } = useTranslation();
  const { ready, issues } = proposal.readiness;
  return (
    <Card
      className={`rounded-[1.5rem] border ${ready ? "border-[oklch(var(--evidence)/0.35)]" : "border-[oklch(var(--caution)/0.35)]"} bg-card/95`}
    >
      <CardContent className="space-y-2 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold">
          {ready ? (
            <CheckCircle2 className="size-4 text-[oklch(var(--evidence))]" aria-hidden />
          ) : (
            <CircleAlert className="size-4 text-[oklch(var(--caution))]" aria-hidden />
          )}
          {ready ? t("proposals.readyToSend") : t("proposals.notReady", { count: issues.length })}
        </p>
        {issues.length > 0 ? (
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {issues.map((issue) => (
              <li key={issue}>{t(`proposals.issues.${issue}`)}</li>
            ))}
          </ul>
        ) : null}
        {dirty ? <p className="text-xs text-muted-foreground">{t("proposals.recheckAfterSave")}</p> : null}
      </CardContent>
    </Card>
  );
}
