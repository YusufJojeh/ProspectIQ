import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { I18nextProvider } from 'react-i18next'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import axios from 'axios'
import { SearchBar } from '../components/SearchBar'
import en from '../i18n/en.json'
import ar from '../i18n/ar.json'

vi.mock('axios')
const mockedAxios = vi.mocked(axios, true)

const testI18n = i18n.createInstance()
testI18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  resources: { en: { translation: en }, ar: { translation: ar } },
  interpolation: { escapeValue: false },
})

afterEach(() => cleanup())

describe('SearchBar', () => {
  const onJobStarted = vi.fn()
  const onError = vi.fn()

  beforeEach(() => {
    onJobStarted.mockClear()
    onError.mockClear()
  })

  function renderBar() {
    return render(
      <I18nextProvider i18n={testI18n}>
        <SearchBar onJobStarted={onJobStarted} onError={onError} />
      </I18nextProvider>,
    )
  }

  it('renders with placeholder text', () => {
    renderBar()
    expect(screen.getByTestId('search-input')).toHaveAttribute('placeholder', en.search.placeholder)
  })

  it('renders the search button', () => {
    renderBar()
    expect(screen.getByTestId('search-button')).toBeInTheDocument()
  })

  it('search button is disabled when input is empty', () => {
    renderBar()
    expect(screen.getByTestId('search-button')).toBeDisabled()
  })

  it('search button is enabled when input has text', () => {
    renderBar()
    fireEvent.change(screen.getByTestId('search-input'), {
      target: { value: 'dentists in Dubai' },
    })
    expect(screen.getByTestId('search-button')).not.toBeDisabled()
  })

  it('calls API and invokes onJobStarted on success', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({ data: { job_id: 'job_abc123', status: 'queued' } })

    renderBar()
    fireEvent.change(screen.getByTestId('search-input'), {
      target: { value: 'dentists in Dubai' },
    })
    fireEvent.click(screen.getByTestId('search-button'))

    await waitFor(() => expect(onJobStarted).toHaveBeenCalledWith('job_abc123'))
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/v2/search'),
      expect.objectContaining({ query: 'dentists in Dubai' }),
    )
  })

  it('calls onError when API fails', async () => {
    mockedAxios.post = vi.fn().mockRejectedValue(new Error('network'))

    renderBar()
    fireEvent.change(screen.getByTestId('search-input'), {
      target: { value: 'dentists in Dubai' },
    })
    fireEvent.click(screen.getByTestId('search-button'))

    await waitFor(() => expect(onError).toHaveBeenCalledWith(en.errors.search_failed))
  })

  it('submits on Enter key press', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({ data: { job_id: 'job_enter', status: 'queued' } })

    renderBar()
    const input = screen.getByTestId('search-input')
    fireEvent.change(input, { target: { value: 'clinics in Riyadh' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    await waitFor(() => expect(onJobStarted).toHaveBeenCalledWith('job_enter'))
  })
})
