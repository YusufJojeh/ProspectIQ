import { useTranslation } from 'react-i18next'

export function LangToggle() {
  const { i18n, t } = useTranslation()
  const isAr = i18n.language === 'ar'

  function toggle() {
    const next = isAr ? 'en' : 'ar'
    i18n.changeLanguage(next)
    try {
      localStorage.setItem('piq-frontend-lang', next)
    } catch {
      // localStorage unavailable
    }
  }

  return (
    <button
      onClick={toggle}
      aria-label="Switch language"
      data-testid="lang-toggle"
      style={{
        background: 'transparent',
        border: `1px solid var(--border-glass)`,
        borderRadius: '6px',
        color: 'var(--text-primary)',
        cursor: 'pointer',
        fontFamily: 'var(--font-body)',
        fontSize: '0.875rem',
        fontWeight: 500,
        padding: '6px 14px',
        transition: 'border-color var(--transition-fast)',
      }}
    >
      {isAr ? t('lang.en') : t('lang.ar')}
    </button>
  )
}
