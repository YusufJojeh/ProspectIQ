import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion, AnimatePresence } from 'framer-motion'

const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) || 'http://localhost:8000'

type Stage = 'searching' | 'enriching' | 'scoring' | 'done' | null

interface StreamEvent {
  stage: Stage
  progress: number
  message?: string
}

interface ProgressStreamProps {
  jobId: string
  onDone: () => void
}

const STAGE_ICONS: Record<NonNullable<Stage>, string> = {
  searching: '🔍',
  enriching: '📊',
  scoring: '🤖',
  done: '✅',
}

export function ProgressStream({ jobId, onDone }: ProgressStreamProps) {
  const { t } = useTranslation()
  const [stage, setStage] = useState<Stage>('searching')
  const [progress, setProgress] = useState(0)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/v2/stream/${jobId}`)
    esRef.current = es

    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data as string) as StreamEvent
        setStage(data.stage)
        setProgress(data.progress)
        if (data.stage === 'done') {
          es.close()
          onDone()
        }
      } catch {
        // ignore malformed events
      }
    }

    es.onerror = () => {
      es.close()
    }

    return () => {
      es.close()
    }
  }, [jobId, onDone])

  const statusKey = stage ?? 'searching'
  const label = t(`status.${statusKey}`)
  const icon = STAGE_ICONS[statusKey as NonNullable<Stage>] ?? '🔍'

  return (
    <div
      data-testid="progress-stream"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-glass)',
        borderRadius: 'var(--radius-card)',
        padding: '24px',
        textAlign: 'center',
      }}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={statusKey}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.25 }}
        >
          <div style={{ fontSize: '2rem', marginBottom: '12px' }}>{icon}</div>
          <p style={{ color: 'var(--text-primary)', fontSize: '1rem', marginBottom: '16px' }}>
            {label}
          </p>
        </motion.div>
      </AnimatePresence>

      <div
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        style={{
          background: 'var(--border-glass)',
          borderRadius: '999px',
          height: '6px',
          overflow: 'hidden',
        }}
      >
        <motion.div
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4 }}
          style={{
            background: 'var(--accent-cyan)',
            borderRadius: '999px',
            height: '100%',
          }}
        />
      </div>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '8px' }}>
        {progress}%
      </p>
    </div>
  )
}
