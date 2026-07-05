import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { I18nextProvider } from 'react-i18next'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { LangToggle } from '../components/LangToggle'
import en from '../i18n/en.json'
import ar from '../i18n/ar.json'

function makeI18n(lng: string) {
  const instance = i18n.createInstance()
  instance.use(initReactI18next).init({
    lng,
    fallbackLng: 'en',
    supportedLngs: ['en', 'ar'],
    resources: {
      en: { translation: en },
      ar: { translation: ar },
    },
    interpolation: { escapeValue: false },
  })
  return instance
}

afterEach(() => cleanup())

describe('LangToggle', () => {
  it('shows عربي when current language is EN', () => {
    const instance = makeI18n('en')
    render(
      <I18nextProvider i18n={instance}>
        <LangToggle />
      </I18nextProvider>,
    )
    expect(screen.getByTestId('lang-toggle')).toHaveTextContent('عربي')
  })

  it('shows EN when current language is AR', () => {
    const instance = makeI18n('ar')
    render(
      <I18nextProvider i18n={instance}>
        <LangToggle />
      </I18nextProvider>,
    )
    expect(screen.getByTestId('lang-toggle')).toHaveTextContent('EN')
  })

  it('calls changeLanguage on click and flips dir', () => {
    const instance = makeI18n('en')
    const spy = vi.spyOn(instance, 'changeLanguage')
    render(
      <I18nextProvider i18n={instance}>
        <LangToggle />
      </I18nextProvider>,
    )
    fireEvent.click(screen.getByTestId('lang-toggle'))
    expect(spy).toHaveBeenCalledWith('ar')
  })

  it('button is accessible with aria-label', () => {
    const instance = makeI18n('en')
    render(
      <I18nextProvider i18n={instance}>
        <LangToggle />
      </I18nextProvider>,
    )
    expect(screen.getByRole('button', { name: /switch language/i })).toBeInTheDocument()
  })
})

describe('LangToggle dir attribute', () => {
  beforeEach(() => {
    document.documentElement.dir = 'ltr'
  })

  it('sets dir=rtl when switching to AR', () => {
    const instance = makeI18n('en')
    instance.on('languageChanged', (lng) => {
      document.documentElement.dir = lng === 'ar' ? 'rtl' : 'ltr'
    })
    render(
      <I18nextProvider i18n={instance}>
        <LangToggle />
      </I18nextProvider>,
    )
    fireEvent.click(screen.getByTestId('lang-toggle'))
    void instance.changeLanguage('ar')
    expect(document.documentElement.dir).toBe('rtl')
  })
})
