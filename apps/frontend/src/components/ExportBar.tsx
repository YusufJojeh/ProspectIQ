import { useTranslation } from 'react-i18next'
import axios from 'axios'
import type { Lead } from './LeadCard'

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) || 'http://localhost:8000'

interface ExportBarProps {
  jobId: string
  leads: Lead[]
  token?: string
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function ExportBar({ jobId, leads, token }: ExportBarProps) {
  const { t } = useTranslation()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}

  async function exportFile(fmt: 'csv' | 'json') {
    try {
      const { data } = await axios.get<Blob>(
        `${API_BASE}/api/v2/export/${jobId}?format=${fmt}`,
        { headers, responseType: 'blob' }
      )
      download(data, `prospectiq-leads.${fmt}`)
    } catch {
      // silently fail — user can retry
    }
  }

  function copyAllEmails() {
    const emails = leads.map((l) => l.email).filter(Boolean).join('\n')
    if (emails) void navigator.clipboard.writeText(emails)
  }

  return (
    <div
      data-testid="export-bar"
      style={{
        alignItems: 'center',
        background: 'rgba(8, 12, 26, 0.92)',
        backdropFilter: 'blur(12px)',
        borderTop: '1px solid var(--border-glass)',
        bottom: 0,
        display: 'flex',
        flexWrap: 'wrap',
        gap: '12px',
        justifyContent: 'space-between',
        left: 0,
        padding: '16px 24px',
        position: 'sticky',
        right: 0,
        zIndex: 100,
      }}
    >
      <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
        {t('export.count', { count: leads.length })}
      </span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        <button
          onClick={() => void exportFile('csv')}
          data-testid="export-csv"
          style={{ background: 'var(--border-glass)', border: 'none', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.875rem', padding: '8px 16px' }}
        >
          {t('export.csv')}
        </button>
        <button
          onClick={() => void exportFile('json')}
          data-testid="export-json"
          style={{ background: 'var(--border-glass)', border: 'none', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.875rem', padding: '8px 16px' }}
        >
          {t('export.json')}
        </button>
        <button
          onClick={copyAllEmails}
          data-testid="copy-all-emails"
          style={{ background: 'var(--accent-cyan)', border: 'none', borderRadius: '6px', color: '#000', cursor: 'pointer', fontSize: '0.875rem', fontWeight: 500, padding: '8px 16px' }}
        >
          {t('export.copy_all')}
        </button>
      </div>
    </div>
  )
}
