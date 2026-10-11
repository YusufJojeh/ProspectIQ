import type { AuditBenchmark, AuditEvidence, AuditFinding, BrandFields, ProposalLanguage } from "@/types/proposals";

import { auditLabels, findingText, opportunityCount, ownFigures } from "../audit-labels";
import { formatDocumentDate } from "../document-labels";
import { DocumentBrandbar, documentClassName, documentStyle } from "./proposal-document";
import "./audit-document.css";

/** Everything the printed audit shows; the page feeds it the rep's choices. */
export interface AuditDocumentData {
  brand: BrandFields;
  language: ProposalLanguage;
  companyName: string;
  category: string | null;
  city: string | null;
  websiteUrl: string | null;
  generatedOn: string;
  findings: AuditFinding[];
  benchmark: AuditBenchmark | null;
  evidence: AuditEvidence[];
  note: string;
  nextStep: string;
}

function auditCode(companyName: string, date: string): string {
  const initials = companyName
    .split(/\s+/)
    .map((word) => word.replace(/[^\p{L}\p{N}]/gu, "").charAt(0))
    .join("")
    .toUpperCase()
    .slice(0, 4);
  return `PA-${initials || "X"}-${date.replaceAll("-", "")}`;
}

function formatNumber(language: ProposalLanguage, value: number, digits = 0): string {
  return new Intl.NumberFormat(language === "ar" ? "ar" : "en", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function AuditDocument({ data, printable = false }: { data: AuditDocumentData; printable?: boolean }) {
  const labels = auditLabels(data.language);
  const { brand, language } = data;
  const code = auditCode(data.companyName, data.generatedOn);
  const opportunities = opportunityCount(data.findings);
  const own = ownFigures(data.findings);
  const dash = "—";

  return (
    <article
      className={`${documentClassName(brand, printable)} pq-audit`}
      style={documentStyle(brand)}
      dir={language === "ar" ? "rtl" : "ltr"}
      lang={language}
      aria-label={`${labels.docType} ${data.companyName}`}
    >
      <DocumentBrandbar brand={brand} docType={labels.docType} code={code} />

      <div className="pq-grid-2 pq-grid-head pq-section">
        <div>
          <div className="pq-eyebrow">{labels.preparedFor}</div>
          <h2>{data.companyName}</h2>
          <p className="pq-muted">{labels.summaryIntro}</p>
        </div>
        <div className="pq-kv">
          <b>{labels.date}</b>
          <span>{formatDocumentDate(data.generatedOn, language)}</span>
          {data.category ? (
            <>
              <b>{labels.category}</b>
              <span>{data.category}</span>
            </>
          ) : null}
          {data.city ? (
            <>
              <b>{labels.location}</b>
              <span>{data.city}</span>
            </>
          ) : null}
          {data.websiteUrl ? (
            <>
              <b>{labels.website}</b>
              <span dir="ltr" className="pq-break">
                {data.websiteUrl.replace(/^https?:\/\//, "").replace(/\/$/, "")}
              </span>
            </>
          ) : null}
        </div>
      </div>

      <div className="pq-audit-summary pq-section">
        <span className="pq-audit-count">{formatNumber(language, opportunities)}</span>
        <strong>{opportunities > 0 ? labels.summaryOpportunities(opportunities) : labels.summaryStrong}</strong>
      </div>

      {data.findings.length > 0 ? (
        <div className="pq-section pq-tight">
          <h3>{labels.checksTitle}</h3>
          <ul className="pq-audit-findings">
            {data.findings.map((finding) => {
              const text = findingText(finding, language);
              return (
                <li key={finding.key} className={`pq-audit-finding pq-audit-${finding.status}`}>
                  <span className="pq-audit-pill">{labels.status[finding.status]}</span>
                  <div>
                    <b>{text.title}</b>
                    <p className="pq-small pq-muted">{text.detail}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {data.benchmark ? (
        <div className="pq-section pq-tight">
          <h3>{labels.benchmarkTitle(data.benchmark.peer_count)}</h3>
          <table className="pq-table">
            <thead>
              <tr>
                <th style={{ width: "40%" }} />
                <th className="pq-num">{labels.benchmarkRating}</th>
                <th className="pq-num">{labels.benchmarkReviews}</th>
                <th className="pq-num">{labels.benchmarkWebsite}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <b>{labels.benchmarkYou}</b>
                </td>
                <td className="pq-num">{own.rating === null ? dash : `${formatNumber(language, own.rating, 1)}★`}</td>
                <td className="pq-num">{own.reviews === null ? dash : formatNumber(language, own.reviews)}</td>
                <td className="pq-num">{own.website ? labels.yes : labels.no}</td>
              </tr>
              <tr>
                <td>{labels.benchmarkMedian}</td>
                <td className="pq-num">
                  {data.benchmark.median_rating === null
                    ? dash
                    : `${formatNumber(language, data.benchmark.median_rating, 1)}★`}
                </td>
                <td className="pq-num">{formatNumber(language, data.benchmark.median_reviews)}</td>
                <td className="pq-num">{`${formatNumber(language, data.benchmark.website_pct)}%`}</td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : null}

      {data.evidence.length > 0 ? (
        <div className="pq-section pq-tight">
          <h3>{labels.evidenceTitle}</h3>
          <ul className="pq-audit-evidence">
            {data.evidence.map((item, index) => (
              <li key={index}>
                <p className="pq-small">{item.text}</p>
                {item.source_url ? (
                  <span className="pq-micro pq-muted pq-break" dir="ltr">
                    {labels.source}: {item.source_url}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="pq-grid-2 pq-section">
        {data.note.trim() ? (
          <div>
            <h3>{labels.noteTitle}</h3>
            <p className="pq-small">{data.note}</p>
          </div>
        ) : (
          <div />
        )}
        <div className="pq-audit-cta">
          <h3>{labels.nextStepTitle}</h3>
          <p className="pq-small">{data.nextStep.trim() || labels.nextStepDefault}</p>
          {brand.footer_contact ? (
            <p className="pq-small" dir="ltr">
              <b>{brand.footer_contact}</b>
            </p>
          ) : null}
        </div>
      </div>

      <div className="pq-spacer" />
      <p className="pq-micro pq-muted pq-audit-method">{labels.method(formatDocumentDate(data.generatedOn, language))}</p>
      <div className="pq-footer" dir="ltr">
        <span>
          {brand.name.toUpperCase()} / {labels.footerKind}
        </span>
        <span>{brand.footer_contact}</span>
        <span>{code}</span>
      </div>
    </article>
  );
}
