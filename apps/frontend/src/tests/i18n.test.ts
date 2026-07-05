import { describe, expect, it } from 'vitest'
import en from '../i18n/en.json'
import ar from '../i18n/ar.json'

type JsonRecord = Record<string, unknown>

function flatKeys(obj: JsonRecord, prefix = ''): string[] {
  const keys: string[] = []
  for (const [key, val] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (val !== null && typeof val === 'object' && !Array.isArray(val)) {
      keys.push(...flatKeys(val as JsonRecord, fullKey))
    } else {
      keys.push(fullKey)
    }
  }
  return keys
}

describe('i18n key parity', () => {
  const enKeys = flatKeys(en as JsonRecord)
  const arKeys = flatKeys(ar as JsonRecord)

  it('every en.json key exists in ar.json', () => {
    const missing = enKeys.filter((k) => !arKeys.includes(k))
    expect(missing, `Missing AR keys: ${missing.join(', ')}`).toHaveLength(0)
  })

  it('every ar.json key exists in en.json', () => {
    const extra = arKeys.filter((k) => !enKeys.includes(k))
    expect(extra, `Extra AR keys not in EN: ${extra.join(', ')}`).toHaveLength(0)
  })

  it('both locales define at least 10 keys', () => {
    expect(enKeys.length).toBeGreaterThanOrEqual(10)
    expect(arKeys.length).toBeGreaterThanOrEqual(10)
  })
})
