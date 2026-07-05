import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import axios from 'axios'

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) || 'http://localhost:8000'

interface SearchBarProps {
  onJobStarted: (jobId: string) => void
  onError: (msg: string) => void
}

interface SpeechWindow extends Window {
  SpeechRecognition?: new () => SpeechRecognitionLike
  webkitSpeechRecognition?: new () => SpeechRecognitionLike
}

interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  onresult:
    | ((event: {
        results: {
          length: number
          [i: number]: { 0: { transcript: string }; isFinal: boolean }
        }
      }) => void)
    | null
  onerror: (() => void) | null
  onend: (() => void) | null
}

function getSpeechCtor(): (new () => SpeechRecognitionLike) | null {
  const w = window as SpeechWindow
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function SearchBar({ onJobStarted, onError }: SearchBarProps) {
  const { t, i18n } = useTranslation()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const recRef = useRef<SpeechRecognitionLike | null>(null)
  const speechSupported = getSpeechCtor() !== null

  async function handleSubmit() {
    if (!query.trim() || loading) return
    setLoading(true)
    try {
      const { data } = await axios.post<{ job_id: string; status: string }>(
        `${API_BASE}/api/v2/search`,
        { query: query.trim(), lang: i18n.language as 'ar' | 'en', auto_detect: false }
      )
      onJobStarted(data.job_id)
    } catch {
      onError(t('errors.search_failed'))
    } finally {
      setLoading(false)
    }
  }

  function toggleVoice() {
    const Ctor = getSpeechCtor()
    if (!Ctor) return
    if (recRef.current) {
      recRef.current.stop()
      recRef.current = null
      setListening(false)
      return
    }
    const rec = new Ctor()
    rec.lang = i18n.language === 'ar' ? 'ar-SA' : 'en-US'
    rec.continuous = false
    rec.interimResults = false
    rec.onresult = (e) => {
      let transcript = ''
      for (let i = 0; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript
      }
      if (transcript.trim()) setQuery((prev) => (prev ? `${prev} ${transcript}` : transcript))
    }
    rec.onerror = () => {
      recRef.current = null
      setListening(false)
    }
    rec.onend = () => {
      recRef.current = null
      setListening(false)
    }
    recRef.current = rec
    setListening(true)
    rec.start()
  }

  return (
    <div data-testid="search-bar" style={{ display: 'flex', gap: '8px', width: '100%' }}>
      <input
        data-testid="search-input"
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('search.placeholder')}
        onKeyDown={(e) => e.key === 'Enter' && void handleSubmit()}
        disabled={loading}
        style={{
          flex: 1,
          background: 'var(--bg-card)',
          border: '1px solid var(--border-glass)',
          borderRadius: '8px',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-body)',
          fontSize: '1rem',
          outline: 'none',
          padding: '12px 16px',
        }}
      />
      {speechSupported && (
        <button
          onClick={toggleVoice}
          aria-label={listening ? t('search.voice_listening') : t('search.voice_hint')}
          data-testid="mic-button"
          style={{
            background: listening ? 'var(--accent-cyan)' : 'var(--bg-card)',
            border: '1px solid var(--border-glass)',
            borderRadius: '8px',
            color: listening ? '#000' : 'var(--text-primary)',
            cursor: 'pointer',
            padding: '12px 14px',
          }}
        >
          🎤
        </button>
      )}
      <button
        onClick={() => void handleSubmit()}
        disabled={loading || !query.trim()}
        data-testid="search-button"
        style={{
          background: 'var(--accent-cyan)',
          border: 'none',
          borderRadius: '8px',
          color: '#000',
          cursor: loading || !query.trim() ? 'not-allowed' : 'pointer',
          fontFamily: 'var(--font-body)',
          fontSize: '1rem',
          fontWeight: 500,
          opacity: loading || !query.trim() ? 0.6 : 1,
          padding: '12px 24px',
          whiteSpace: 'nowrap',
        }}
      >
        {loading ? '…' : t('search.button')}
      </button>
    </div>
  )
}
