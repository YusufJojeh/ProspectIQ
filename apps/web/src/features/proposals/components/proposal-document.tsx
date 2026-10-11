import { useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

import type { BrandFields, ProposalLanguage } from "@/types/proposals";

import { documentLabels, formatDocumentDate } from "../document-labels";
import { formatMinor, formatMoney } from "../money";
import "./proposal-document.css";

export interface DocumentMilestone {
  title: string;
  description: string;
  amount_minor: number | null;
}

/** Everything the printed page shows; the editor feeds it unsaved values. */
export interface ProposalDocumentData {
  brand: BrandFields;
  language: ProposalLanguage;
  number: string;
  title: string;
  client_company: string;
  client_contact_name: string | null;
  client_email: string | null;
  client_location: string | null;
  currency: string;
  issue_date: string;
  valid_until: string;
  outcome: string;
  milestones: DocumentMilestone[];
  commercial_notes: string;
  validity_notes: string;
  sender_contact: string;
}

/** Same rule as the API: the deposit is the first milestone. */
export function documentTotals(milestones: DocumentMilestone[]) {
  const amounts = milestones.map((line) => line.amount_minor ?? 0);
  const total = amounts.reduce((sum, value) => sum + value, 0);
  const deposit = amounts[0] ?? 0;
  return { total, deposit, remaining: total - deposit };
}

function sharePct(amount: number | null, total: number): string {
  if (amount === null || total <= 0) return "—";
  return `${Math.round((amount * 1000) / total) / 10}%`;
}

/** Brand tokens as the CSS variables the stylesheet reads. */
export function documentStyle(brand: BrandFields): CSSProperties {
  return {
    "--pq-paper": brand.paper,
    "--pq-ink": brand.ink,
    "--pq-muted": brand.muted,
    "--pq-line": brand.line,
    "--pq-accent": brand.accent,
    "--pq-accent-2": brand.accent_secondary,
    "--pq-bg": brand.background,
    "--pq-radius": `${brand.radius_px}px`,
  } as CSSProperties;
}

export function documentClassName(brand: BrandFields, printable: boolean): string {
  return `pq-doc${brand.font_style === "serif" ? " pq-serif" : ""}${printable ? " pq-print-root" : ""}`;
}

/** The letterhead every client document starts with: logo or mark, name, document type. */
export function DocumentBrandbar({ brand, docType, code }: { brand: BrandFields; docType: string; code: string }) {
  const markClass =
    brand.mark_shape === "hex" ? "pq-mark-hex" : brand.mark_shape === "square" ? "pq-mark-square" : "pq-mark-circle";
  return (
    <>
      <div className="pq-brandbar">
        <div className="pq-lockup">
          {brand.logo_data_url ? (
            <img className="pq-logo" src={brand.logo_data_url} alt="" />
          ) : (
            <div className={`pq-mark ${markClass}`}>
              <span>{brand.mark}</span>
            </div>
          )}
          <div className="pq-wordmark" dir="ltr">
            {brand.name}
            <small>{brand.tagline}</small>
          </div>
        </div>
        <div className="pq-doc-code">
          {docType}
          <br />
          <span dir="ltr">{code}</span>
        </div>
      </div>
      <div className="pq-accent-line" />
    </>
  );
}

export function ProposalDocument({ data, printable = false }: { data: ProposalDocumentData; printable?: boolean }) {
  const labels = documentLabels(data.language);
  const { brand } = data;
  const totals = documentTotals(data.milestones);
  const attnParts = [data.client_contact_name, data.client_location].filter(
    (part): part is string => Boolean(part && part.trim()),
  );

  return (
    <article
      className={documentClassName(brand, printable)}
      style={documentStyle(brand)}
      dir={data.language === "ar" ? "rtl" : "ltr"}
      lang={data.language}
      aria-label={`${labels.docType} ${data.number}`}
    >
      <DocumentBrandbar brand={brand} docType={labels.docType} code={data.number} />

      <div className="pq-grid-2 pq-grid-head pq-section">
        <div>
          <div className="pq-eyebrow">{labels.preparedFor}</div>
          <h2>{data.client_company}</h2>
          <p className="pq-muted">
            {attnParts.length > 0 ? `${labels.attn} ${attnParts.join(" · ")}` : null}
            {attnParts.length > 0 && data.client_email ? <br /> : null}
            {data.client_email ? <span dir="ltr">{data.client_email}</span> : null}
          </p>
        </div>
        <div className="pq-kv">
          <b>{labels.date}</b>
          <span>{formatDocumentDate(data.issue_date, data.language)}</span>
          <b>{labels.validUntil}</b>
          <span>{formatDocumentDate(data.valid_until, data.language)}</span>
          <b>{labels.currency}</b>
          <span>{data.currency}</span>
          <b>{labels.project}</b>
          <span>{data.title}</span>
        </div>
      </div>

      <div className="pq-section">
        <h3>{labels.outcome}</h3>
        <p>{data.outcome}</p>
      </div>

      <div className="pq-section pq-tight">
        <h3>{labels.milestones}</h3>
        <table className="pq-table">
          <thead>
            <tr>
              <th style={{ width: "56%" }}>{labels.milestone}</th>
              <th>{labels.share}</th>
              <th className="pq-num">{labels.amount}</th>
            </tr>
          </thead>
          <tbody>
            {data.milestones.map((line, index) => (
              <tr key={index}>
                <td>
                  <b>
                    {String(index + 1).padStart(2, "0")} · {line.title}
                  </b>
                  {line.description ? <div className="pq-small pq-muted">{line.description}</div> : null}
                </td>
                <td className="pq-mono">{sharePct(line.amount_minor, totals.total)}</td>
                <td className="pq-num">
                  {line.amount_minor === null ? (
                    <span className="pq-unpriced">{labels.unpriced}</span>
                  ) : (
                    formatMinor(line.amount_minor)
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="pq-totals">
          <div className="pq-row">
            <span>{labels.deposit}</span>
            <strong dir="ltr">{formatMoney(data.currency, totals.deposit)}</strong>
          </div>
          <div className="pq-row">
            <span>{labels.remaining}</span>
            <strong dir="ltr">{formatMoney(data.currency, totals.remaining)}</strong>
          </div>
          <div className="pq-row pq-grand">
            <span>{labels.total}</span>
            <strong dir="ltr">{formatMoney(data.currency, totals.total)}</strong>
          </div>
        </div>
      </div>

      <div className="pq-grid-2 pq-section">
        <div>
          <h3>{labels.commercialNotes}</h3>
          <p className="pq-small">{data.commercial_notes}</p>
        </div>
        <div>
          <h3>{labels.validity}</h3>
          <p className="pq-small">{data.validity_notes}</p>
        </div>
      </div>

      <div className="pq-signatures">
        <div>
          <div className="pq-signature" />
          <p className="pq-micro pq-muted">
            {brand.signer_label} · {labels.dateSuffix}
          </p>
        </div>
        <div>
          <div className="pq-signature" />
          <p className="pq-micro pq-muted">{brand.client_signer_label}</p>
        </div>
      </div>

      <div className="pq-spacer" />
      <div className="pq-footer" dir="ltr">
        <span>
          {brand.name.toUpperCase()} / {labels.footerKind}
        </span>
        <span>{data.sender_contact}</span>
        <span>{data.number}</span>
      </div>
    </article>
  );
}

export function ScaledProposalDocument({
  data,
  printable = false,
}: {
  data: ProposalDocumentData;
  printable?: boolean;
}) {
  return (
    <ScaledPage>
      <ProposalDocument data={data} printable={printable} />
    </ScaledPage>
  );
}

/** Scales any fixed-width A4 client document down to its container. */
export function ScaledPage({ children }: { children: ReactNode }) {
  const frameRef = useRef<HTMLDivElement>(null);
  const pageRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [height, setHeight] = useState<number | undefined>(undefined);

  useLayoutEffect(() => {
    const frame = frameRef.current;
    const page = pageRef.current;
    if (!frame || !page) return;
    const update = () => {
      const next = Math.min(1, frame.clientWidth / page.offsetWidth);
      setScale(next);
      setHeight(page.offsetHeight * next);
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(frame);
    observer.observe(page);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={frameRef} className="pq-scaler-frame" style={{ height }}>
      <div ref={pageRef} className="pq-scaler" style={{ transform: `scale(${scale})` }}>
        <div className="overflow-hidden rounded-md shadow-lg ring-1 ring-black/5">
          {children}
        </div>
      </div>
    </div>
  );
}
