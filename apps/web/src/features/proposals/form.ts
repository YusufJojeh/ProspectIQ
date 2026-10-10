import { z } from "zod";

import type { Proposal, ProposalBrand, ProposalUpdateRequest } from "@/types/proposals";

import type { ProposalDocumentData } from "./components/proposal-document";
import { minorToInput, parseMinor } from "./money";

/**
 * The editor form. Validation here is structural (lengths, formats); whether
 * a proposal is complete enough to send is the server's readiness check, so
 * an unfinished draft can always be saved.
 */
export const proposalFormSchema = z
  .object({
    brand_key: z.string().min(1),
    language: z.enum(["en", "ar"]),
    title: z.string().max(255),
    client_company: z.string().max(255),
    client_contact_name: z.string().max(255),
    client_email: z.union([z.literal(""), z.string().trim().email().max(320)]),
    client_location: z.string().max(255),
    currency: z.string().trim().regex(/^[A-Za-z]{3}$/),
    issue_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    valid_until: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    outcome: z.string().max(4000),
    milestones: z
      .array(
        z.object({
          title: z.string().max(200),
          description: z.string().max(600),
          amount: z.string().refine((value) => parseMinor(value) !== undefined, {
            message: "invalidAmount",
          }),
        }),
      )
      .max(12),
    commercial_notes: z.string().max(2000),
    validity_notes: z.string().max(2000),
    sender_contact: z.string().max(255),
  })
  .refine((values) => values.valid_until > values.issue_date, {
    path: ["valid_until"],
    message: "validityBeforeIssue",
  });

export type ProposalFormValues = z.infer<typeof proposalFormSchema>;

export function toFormValues(proposal: Proposal): ProposalFormValues {
  return {
    brand_key: proposal.brand.key,
    language: proposal.language,
    title: proposal.title,
    client_company: proposal.client_company,
    client_contact_name: proposal.client_contact_name ?? "",
    client_email: proposal.client_email ?? "",
    client_location: proposal.client_location ?? "",
    currency: proposal.currency,
    issue_date: proposal.issue_date,
    valid_until: proposal.valid_until,
    outcome: proposal.outcome,
    milestones: proposal.milestones.map((line) => ({
      title: line.title,
      description: line.description,
      amount: minorToInput(line.amount_minor),
    })),
    commercial_notes: proposal.commercial_notes,
    validity_notes: proposal.validity_notes,
    sender_contact: proposal.sender_contact,
  };
}

function amountOf(value: string): number | null {
  return parseMinor(value) ?? null;
}

export function toUpdateRequest(values: ProposalFormValues): ProposalUpdateRequest {
  return {
    brand_key: values.brand_key,
    language: values.language,
    title: values.title.trim(),
    client_company: values.client_company.trim(),
    client_contact_name: values.client_contact_name.trim() || null,
    client_email: values.client_email.trim() || null,
    client_location: values.client_location.trim() || null,
    currency: values.currency.trim().toUpperCase(),
    issue_date: values.issue_date,
    valid_until: values.valid_until,
    outcome: values.outcome.trim(),
    milestones: values.milestones.map((line) => ({
      title: line.title.trim(),
      description: line.description.trim(),
      amount_minor: amountOf(line.amount),
    })),
    commercial_notes: values.commercial_notes.trim(),
    validity_notes: values.validity_notes.trim(),
    sender_contact: values.sender_contact.trim(),
  };
}

/** The live preview: unsaved form values rendered with the chosen brand. */
export function toDocumentData(
  values: ProposalFormValues,
  number: string,
  brand: ProposalBrand,
): ProposalDocumentData {
  return {
    brand,
    language: values.language,
    number,
    title: values.title,
    client_company: values.client_company,
    client_contact_name: values.client_contact_name || null,
    client_email: values.client_email || null,
    client_location: values.client_location || null,
    currency: values.currency.toUpperCase(),
    issue_date: values.issue_date,
    valid_until: values.valid_until,
    outcome: values.outcome,
    milestones: values.milestones.map((line) => ({
      title: line.title,
      description: line.description,
      amount_minor: amountOf(line.amount),
    })),
    commercial_notes: values.commercial_notes,
    validity_notes: values.validity_notes,
    sender_contact: values.sender_contact,
  };
}
