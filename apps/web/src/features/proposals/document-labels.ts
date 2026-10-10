import type { ProposalLanguage } from "@/types/proposals";

/**
 * Labels printed on the client-facing document. They follow the proposal's
 * own language, not the salesperson's UI language: an English-speaking rep
 * can prepare an Arabic quotation and vice versa.
 */
export interface DocumentLabels {
  docType: string;
  preparedFor: string;
  attn: string;
  date: string;
  validUntil: string;
  currency: string;
  project: string;
  outcome: string;
  milestones: string;
  milestone: string;
  share: string;
  amount: string;
  deposit: string;
  remaining: string;
  total: string;
  commercialNotes: string;
  validity: string;
  dateSuffix: string;
  footerKind: string;
  unpriced: string;
}

const EN: DocumentLabels = {
  docType: "PROPOSAL / QUOTATION",
  preparedFor: "PREPARED FOR",
  attn: "Attn.",
  date: "Date",
  validUntil: "Valid until",
  currency: "Currency",
  project: "Project",
  outcome: "Outcome",
  milestones: "Milestones & commercial structure",
  milestone: "Milestone",
  share: "Share",
  amount: "Amount",
  deposit: "Deposit to commence",
  remaining: "Remaining milestones",
  total: "Project total",
  commercialNotes: "Commercial notes",
  validity: "Validity",
  dateSuffix: "date",
  footerKind: "QUOTATION",
  unpriced: "To be priced",
};

const AR: DocumentLabels = {
  docType: "عرض فني ومالي",
  preparedFor: "مُعدّ لـ",
  attn: "عناية",
  date: "التاريخ",
  validUntil: "صالح حتى",
  currency: "العملة",
  project: "المشروع",
  outcome: "النتيجة المتوقعة",
  milestones: "المراحل والهيكل المالي",
  milestone: "المرحلة",
  share: "النسبة",
  amount: "المبلغ",
  deposit: "الدفعة المقدمة للبدء",
  remaining: "المراحل المتبقية",
  total: "إجمالي المشروع",
  commercialNotes: "ملاحظات تجارية",
  validity: "الصلاحية",
  dateSuffix: "التاريخ",
  footerKind: "عرض سعر",
  unpriced: "بانتظار التسعير",
};

export function documentLabels(language: ProposalLanguage): DocumentLabels {
  return language === "ar" ? AR : EN;
}

/** "19 Sep 2026" / Arabic month names, from an ISO date, without timezone drift. */
export function formatDocumentDate(isoDate: string, language: ProposalLanguage): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  if (!year || !month || !day) return isoDate;
  const date = new Date(Date.UTC(year, month - 1, day));
  return new Intl.DateTimeFormat(language === "ar" ? "ar" : "en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export interface CoverEmailInput {
  language: ProposalLanguage;
  number: string;
  title: string;
  clientCompany: string;
  contactName: string | null;
  total: string;
  validUntil: string;
  senderName: string;
}

/** A short cover note to paste into the email the PDF is attached to. */
export function coverEmail(input: CoverEmailInput): { subject: string; body: string } {
  const validUntil = formatDocumentDate(input.validUntil, input.language);
  if (input.language === "ar") {
    const greeting = input.contactName ? `مرحباً ${input.contactName}،` : "مرحباً،";
    return {
      subject: `عرض سعر ${input.number} — ${input.title}`,
      body: [
        greeting,
        "",
        `مرفق عرض السعر ${input.number} لمشروع «${input.title}» الخاص بـ ${input.clientCompany}.`,
        `إجمالي المشروع ${input.total}، والعرض صالح حتى ${validUntil}.`,
        "",
        "يسعدني ترتيب مكالمة قصيرة لمراجعة النطاق والمراحل والإجابة عن أي أسئلة.",
        "",
        "مع التحية،",
        input.senderName,
      ].join("\n"),
    };
  }
  const greeting = input.contactName ? `Hi ${input.contactName},` : "Hello,";
  return {
    subject: `Proposal ${input.number} — ${input.title}`,
    body: [
      greeting,
      "",
      `Please find attached proposal ${input.number} for ${input.title} at ${input.clientCompany}.`,
      `The project total is ${input.total}, and the quotation is valid until ${validUntil}.`,
      "",
      "Happy to walk through the scope, milestones and next steps on a short call.",
      "",
      "Best regards,",
      input.senderName,
    ].join("\n"),
  };
}
