import { z } from "zod";

import type { BrandCreateRequest, BrandFields, ProposalLanguage } from "@/types/proposals";

import type { ProposalDocumentData } from "./components/proposal-document";

const HEX_COLOR = /^#[0-9A-Fa-f]{6}$/;
const color = z.string().trim().regex(HEX_COLOR, { message: "invalidColor" });

/** Logos are embedded in the document, so they stay small and raster-only. */
export const MAX_LOGO_BYTES = 300 * 1024;
export const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;

export const BRAND_COLOR_FIELDS = [
  "accent",
  "accent_secondary",
  "ink",
  "muted",
  "paper",
  "line",
  "background",
] as const;

export const brandFormSchema = z.object({
  name: z.string().trim().min(1, { message: "required" }).max(120),
  tagline: z.string().max(160),
  mark: z.string().trim().max(4),
  mark_shape: z.enum(["square", "hex", "circle"]),
  font_style: z.enum(["sans", "serif"]),
  logo_data_url: z.string().nullable(),
  number_prefix: z
    .string()
    .trim()
    .regex(/^[A-Za-z0-9]{1,8}(-[A-Za-z0-9]{1,6})?$/, { message: "invalidPrefix" }),
  signer_label: z.string().max(160),
  client_signer_label: z.string().max(160),
  footer_contact: z.string().max(255),
  paper: color,
  ink: color,
  muted: color,
  line: color,
  accent: color,
  accent_secondary: color,
  background: color,
  radius_px: z.number({ message: "invalid" }).int().min(0).max(24),
  default_currency: z.string().trim().regex(/^[A-Za-z]{3}$/, { message: "invalidCurrency" }),
  validity_days: z.number({ message: "invalid" }).int().min(1).max(365),
  default_outcome: z.string().max(4000),
  default_commercial_notes: z.string().max(2000),
  default_validity_notes: z.string().max(2000),
  default_milestones: z
    .array(
      z.object({
        title: z.string().trim().min(1, { message: "required" }).max(200),
        description: z.string().max(600),
      }),
    )
    .max(12),
});

export type BrandFormValues = z.infer<typeof brandFormSchema>;

export function toBrandFormValues(brand: BrandFields): BrandFormValues {
  return {
    name: brand.name,
    tagline: brand.tagline,
    mark: brand.mark,
    mark_shape: brand.mark_shape,
    font_style: brand.font_style,
    logo_data_url: brand.logo_data_url,
    number_prefix: brand.number_prefix,
    signer_label: brand.signer_label,
    client_signer_label: brand.client_signer_label,
    footer_contact: brand.footer_contact,
    paper: brand.paper,
    ink: brand.ink,
    muted: brand.muted,
    line: brand.line,
    accent: brand.accent,
    accent_secondary: brand.accent_secondary,
    background: brand.background,
    radius_px: brand.radius_px,
    default_currency: brand.default_currency,
    validity_days: brand.validity_days,
    default_outcome: brand.default_outcome,
    default_commercial_notes: brand.default_commercial_notes,
    default_validity_notes: brand.default_validity_notes,
    default_milestones: brand.default_milestones.map((line) => ({ ...line })),
  };
}

export function toBrandRequest(values: BrandFormValues): BrandCreateRequest {
  return {
    ...values,
    name: values.name.trim(),
    tagline: values.tagline.trim(),
    mark: values.mark.trim(),
    number_prefix: values.number_prefix.trim().toUpperCase(),
    signer_label: values.signer_label.trim(),
    client_signer_label: values.client_signer_label.trim(),
    footer_contact: values.footer_contact.trim(),
    paper: values.paper.toUpperCase(),
    ink: values.ink.toUpperCase(),
    muted: values.muted.toUpperCase(),
    line: values.line.toUpperCase(),
    accent: values.accent.toUpperCase(),
    accent_secondary: values.accent_secondary.toUpperCase(),
    background: values.background.toUpperCase(),
    default_currency: values.default_currency.trim().toUpperCase(),
    default_outcome: values.default_outcome.trim(),
    default_commercial_notes: values.default_commercial_notes.trim(),
    default_validity_notes: values.default_validity_notes.trim(),
    default_milestones: values.default_milestones.map((line) => ({
      title: line.title.trim(),
      description: line.description.trim(),
    })),
  };
}

const SAMPLE_SHARES = [20, 45, 35, 25, 25, 25];
const SAMPLE_TOTAL_MINOR = 1_000_000;

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + (Number.isFinite(days) ? days : 30));
  return date.toISOString().slice(0, 10);
}

/** What a proposal in this brand looks like, with a sample client and prices. */
export function sampleDocument(
  values: BrandFormValues,
  language: ProposalLanguage,
  today: string,
  sample: { clientCompany: string; title: string },
): ProposalDocumentData {
  const brand: BrandFields = {
    ...values,
    number_prefix: values.number_prefix.toUpperCase(),
    default_currency: values.default_currency.toUpperCase(),
  };
  return {
    brand,
    language,
    number: `${brand.number_prefix || "Q"}-${today.slice(0, 4)}-001`,
    title: sample.title,
    client_company: sample.clientCompany,
    client_contact_name: null,
    client_email: "client@example.com",
    client_location: null,
    currency: brand.default_currency || "USD",
    issue_date: today,
    valid_until: addDays(today, values.validity_days),
    outcome: values.default_outcome,
    milestones: values.default_milestones.map((line, index) => ({
      title: line.title,
      description: line.description,
      amount_minor: ((SAMPLE_SHARES[index] ?? 10) * SAMPLE_TOTAL_MINOR) / 100,
    })),
    commercial_notes: values.default_commercial_notes,
    validity_notes: values.default_validity_notes,
    sender_contact: values.footer_contact,
  };
}

/** Reads an uploaded logo into a data URL, or explains why it was refused. */
export function readLogo(file: File): Promise<{ dataUrl: string } | { error: "type" | "size" | "read" }> {
  if (!(LOGO_TYPES as readonly string[]).includes(file.type)) {
    return Promise.resolve({ error: "type" });
  }
  if (file.size > MAX_LOGO_BYTES) return Promise.resolve({ error: "size" });
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () =>
      resolve(typeof reader.result === "string" ? { dataUrl: reader.result } : { error: "read" });
    reader.onerror = () => resolve({ error: "read" });
    reader.readAsDataURL(file);
  });
}
