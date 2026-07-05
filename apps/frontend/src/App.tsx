import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import axios from 'axios'
import './i18n/index'
import './styles/tokens.css'
import { LangToggle } from './components/LangToggle'
import { SearchBar } from './components/SearchBar'
import { ProgressStream } from './components/ProgressStream'
import { LeadGrid } from './components/LeadGrid'
import { ExportBar } from './components/ExportBar'
import type { Lead } from './components/LeadCard'

const API_BASE =
  (typeof import.meta !== 'undefined' && (import.meta as ImportMeta & { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL) ||
  'http://localhost:8000'

type AppState = 'idle' | 'loading' | 'streaming' | 'results' | 'error'

interface V2ResultsPage {
  items: Lead[]
  page: number
  per_page: number
  total: number
}

function App() {
  const { t } = useTranslation()
  const [appState, setAppState] = useState<AppState>('idle')
  const [jobId, setJobId] = useState<string | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [error, setError] = useState<string | null>(null)

  function handleJobStarted(id: string) {
    setJobId(id)
    setLeads([])
    setError(null)
    setAppState('streaming')
  }

  function handleSearchError(msg: string) {
    setError(msg)
    setAppState('error')
  }

  async function handleStreamDone() {
    if (!jobId) return
    try {
      const { data } = await axios.get<V2ResultsPage>(
        `${API_BASE}/api/v2/results/${jobId}?page=1&per_page=100`,
      )
      setLeads(data.items)
      setAppState(data.items.length > 0 ? 'results' : 'error')
      if (data.items.length === 0) setError(t('errors.no_results'))
    } catch {
      setError(t('errors.search_failed'))
      setAppState('error')
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', paddingBottom: '80px' }}>
      <header
        style={{
          alignItems: 'center',
          borderBottom: '1px solid var(--border-glass)',
          display: 'flex',
          justifyContent: 'flex-end',
          padding: '16px 24px',
        }}
      >
        <LangToggle />
      </header>

      <main
        style={{
          flex: 1,
          margin: '0 auto',
          maxWidth: '900px',
          padding: '48px 24px',
          width: '100%',
        }}
      >
        <h1
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-display)',
            fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
            fontWeight: 800,
            marginBottom: '32px',
            textAlign: 'center',
          }}
        >
          ProspectIQ
        </h1>

        {(appState === 'idle' || appState === 'error') && (
          <SearchBar onJobStarted={handleJobStarted} onError={handleSearchError} />
        )}

        {error && (
          <p style={{ color: 'var(--score-low)', marginTop: '16px', textAlign: 'center' }}>
            {error}
          </p>
        )}

        {appState === 'streaming' && jobId && (
          <div style={{ marginTop: '32px' }}>
            <ProgressStream jobId={jobId} onDone={() => void handleStreamDone()} />
          </div>
        )}

        {appState === 'results' && leads.length > 0 && (
          <div style={{ marginTop: '32px' }}>
            <LeadGrid leads={leads} />
          </div>
        )}
      </main>

      {appState === 'results' && jobId && leads.length > 0 && (
        <ExportBar jobId={jobId} leads={leads} />
      )}
    </div>
  )
}

export default App
