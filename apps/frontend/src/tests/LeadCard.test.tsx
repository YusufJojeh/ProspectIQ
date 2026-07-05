import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { I18nextProvider } from 'react-i18next'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { LeadCard, type Lead } from '../components/LeadCard'
import en from '../i18n/en.json'
import ar from '../i18n/ar.json'

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...rest }: React.HTMLAttributes<HTMLDivElement>) => <div {...rest}>{children}</div>,
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

const testI18n = i18n.createInstance()
testI18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  resources: { en: { translation: en }, ar: { translation: ar } },
  interpolation: { escapeValue: false },
})

afterEach(() => cleanup())

function renderCard(lead: Partial<Lead> = {}) {
  const fullLead: Lead = {
    company: 'Acme Dental',
    contact_name: null,
    email: 'hello@acme.example',
    email_confidence: 0.8,
    linkedin_url: 'https://linkedin.com/company/acme',
    industry: 'Dentist',
    employee_count: 12,
    lead_score: 82,
    ai_opener: 'Strong local trust with clear growth opportunities.',
    logo_url: null,
    ...lead,
  }
  return render(
    <I18nextProvider i18n={testI18n}>
      <LeadCard lead={fullLead} />
    </I18nextProvider>,
  )
}

describe('LeadCard', () => {
  it('renders company name', () => {
    renderCard()
    expect(screen.getByText('Acme Dental')).toBeInTheDocument()
  })

  it('renders industry when available', () => {
    renderCard()
    expect(screen.getByText('Dentist')).toBeInTheDocument()
  })

  it('renders copy email button when email exists', () => {
    renderCard()
    expect(screen.getByTestId('copy-email-button')).toBeInTheDocument()
  })

  it('shows no-email text when email is null', () => {
    renderCard({ email: null })
    expect(screen.getByText(en.lead.no_email)).toBeInTheDocument()
    expect(screen.queryByTestId('copy-email-button')).toBeNull()
  })

  it('renders LinkedIn link when url is provided', () => {
    renderCard()
    const link = screen.getByTestId('linkedin-link')
    expect(link).toHaveAttribute('href', 'https://linkedin.com/company/acme')
  })

  it('does not render LinkedIn link when url is null', () => {
    renderCard({ linkedin_url: null })
    expect(screen.queryByTestId('linkedin-link')).toBeNull()
  })

  it('renders score ring with correct aria-label', () => {
    renderCard({ lead_score: 75 })
    expect(screen.getByLabelText(/score/i)).toBeInTheDocument()
  })

  it('renders score ring with green color for score ≥ 70', () => {
    const { container } = renderCard({ lead_score: 85 })
    const svg = container.querySelector('svg[aria-label]')
    const strokeCircle = svg?.querySelectorAll('circle')[1]
    expect(strokeCircle?.getAttribute('stroke')).toBe('var(--score-high)')
  })

  it('renders score ring with amber color for 40 ≤ score < 70', () => {
    const { container } = renderCard({ lead_score: 55 })
    const svg = container.querySelector('svg[aria-label]')
    const strokeCircle = svg?.querySelectorAll('circle')[1]
    expect(strokeCircle?.getAttribute('stroke')).toBe('var(--score-mid)')
  })

  it('renders score ring with red color for score < 40', () => {
    const { container } = renderCard({ lead_score: 25 })
    const svg = container.querySelector('svg[aria-label]')
    const strokeCircle = svg?.querySelectorAll('circle')[1]
    expect(strokeCircle?.getAttribute('stroke')).toBe('var(--score-low)')
  })

  it('hides ai opener by default and shows on click', () => {
    renderCard()
    expect(screen.queryByText('Strong local trust with clear growth opportunities.')).toBeNull()
    fireEvent.click(screen.getByText(/suggested opener/i))
    expect(screen.getByText('Strong local trust with clear growth opportunities.')).toBeInTheDocument()
  })
})
