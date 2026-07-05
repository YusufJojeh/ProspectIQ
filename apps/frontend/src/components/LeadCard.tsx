import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface Lead {
  company: string
  contact_name: string | null
  email: string | null
  email_confidence: number | null
  linkedin_url: string | null
  industry: string | null
  employee_count: number | null
  lead_score: number | null
  ai_opener: string | null
  logo_url: string | null
}

function scoreColor(score: number): string {
  if (score >= 70) return 'var(--score-high)'
  if (score >= 40) return 'var(--score-mid)'
  return 'var(--score-low)'
}

function ScoreRing({ score }: { score: number }) {
  const r = 20
  const circ = 2 * Math.PI * r
  const dash = circ * (score / 100)
  const color = scoreColor(score)

  return (
    <svg width="56" height="56" viewBox="0 0 56 56" aria-label={`Score: ${score}`}>
      <circle cx="28" cy="28" r={r} fill="none" stroke="var(--border-glass)" strokeWidth="4" />
      <circle
        cx="28"
        cy="28"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 28 28)"
      />
      <text x="28" y="33" textAnchor="middle" fill={color} fontSize="10" fontWeight="bold">
        {Math.round(score)}
      </text>
    </svg>
  )
}

export function LeadCard({ lead }: { lead: Lead }) {
  const { t } = useTranslation()
  const [openerOpen, setOpenerOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const favicon = lead.logo_url ?? (lead.company ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(lead.company)}&sz=64` : null)

  async function copyEmail() {
    if (!lead.email) return
    try {
      await navigator.clipboard.writeText(lead.email)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      // clipboard unavailable
    }
  }

  return (
    <article
      data-testid="lead-card"
      style={{
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        background: 'var(--bg-card)',
        border: '1px solid var(--border-glass)',
        borderRadius: 'var(--radius-card)',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        padding: '20px',
      }}
    >
      <div style={{ alignItems: 'center', display: 'flex', gap: '12px' }}>
        {favicon && (
          <img
            src={favicon}
            alt={lead.company}
            width={32}
            height={32}
            style={{ borderRadius: '6px', objectFit: 'contain' }}
            onError={(e) => {
              ;(e.currentTarget as HTMLImageElement).style.display = 'none'
            }}
          />
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <p
            style={{
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-display)',
              fontSize: '1rem',
              fontWeight: 700,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {lead.company}
          </p>
          {lead.industry && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{lead.industry}</p>
          )}
        </div>
        {lead.lead_score !== null && <ScoreRing score={lead.lead_score} />}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        {lead.email ? (
          <button
            onClick={() => void copyEmail()}
            data-testid="copy-email-button"
            style={{
              background: 'var(--border-glass)',
              border: 'none',
              borderRadius: '6px',
              color: copied ? 'var(--score-high)' : 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '0.8rem',
              padding: '6px 12px',
            }}
          >
            {copied ? t('lead.copied') : t('lead.copy_email')}
          </button>
        ) : (
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{t('lead.no_email')}</span>
        )}

        {lead.linkedin_url && (
          <a
            href={lead.linkedin_url}
            target="_blank"
            rel="noreferrer noopener"
            data-testid="linkedin-link"
            style={{
              background: 'var(--border-glass)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontSize: '0.8rem',
              padding: '6px 12px',
              textDecoration: 'none',
            }}
          >
            {t('lead.open_linkedin')}
          </a>
        )}
      </div>

      {lead.ai_opener && (
        <div>
          <button
            onClick={() => setOpenerOpen((o) => !o)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--accent-cyan)',
              cursor: 'pointer',
              fontSize: '0.8rem',
              padding: 0,
            }}
          >
            {t('lead.ai_opener')} {openerOpen ? '▲' : '▼'}
          </button>
          {openerOpen && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
              {lead.ai_opener}
            </p>
          )}
        </div>
      )}
    </article>
  )
}
