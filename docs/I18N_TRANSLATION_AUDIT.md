# I18N Translation Audit — ProspectIQ / LeadScope AI

Date: 2026-05-20

---

## Scope

This audit covers the two locale files used by the React frontend:

- `apps/web/src/locales/en.json` (English — source of truth)
- `apps/web/src/locales/ar.json` (Arabic — RTL target)

The i18n stack is **i18next + react-i18next** with browser language detection,
localStorage persistence, and a manual language toggle.

---

## Key Parity

| Metric | Value |
| --- | --- |
| Total keys (EN) | 1 259 |
| Total keys (AR) | 1 259 |
| Keys in EN missing from AR | **0** |
| Keys in AR missing from EN | **0** |

Structural parity is **100 %**. Every key path in EN has a corresponding
entry in AR, and vice versa.

---

## Bugs Found and Fixed

### 1. Encoding corruption — `??` instead of `في`

Two values contained `??` where the Arabic preposition **في** ("in") should
have appeared. This was likely caused by a copy/paste from a terminal or
editor that could not decode the UTF-8 Arabic character.

| Key | Before | After |
| --- | --- | --- |
| `searches.jobCardSummary` | `{{businessType}} ?? {{city}}` | `{{businessType}} في {{city}}` |
| `searches.jobTitlePattern` | `{{businessType}} ?? {{city}}` | `{{businessType}} في {{city}}` |

### 2. Untranslated English strings in AR file

Two values in the `team` section were left as English text instead of Arabic.

| Key | Before (English) | After (Arabic) |
| --- | --- | --- |
| `team.usersTitle` | `Team users` | `مستخدمو الفريق` |
| `team.usersDescription` | `Manage users inside the current workspace only.` | `إدارة المستخدمين ضمن مساحة العمل الحالية فقط.` |

### 3. Semantic mismatches — wrong intended meaning

Six values had literal, inconsistent, or completely wrong Arabic translations
that did not match the English source intent.

| Key | Issue | Fix |
| --- | --- | --- |
| `billing.subscriptionDescription` | AR said "Current SaaS plan. Plan changes require owner permissions." but EN says it's simulated billing only | Changed to "فوترة SaaS تجريبية فقط. لا يوجد معالج دفع حقيقي أو شحن مباشر مفعّل." |
| `outreach.toneOptionsSummary` | AR said "Keep a professional tone depending on context" but EN is a list of tones | Changed to "رسمي، ودّي، استشاري، عرض مختصر" |
| `errors.search_jobs.*` (3 keys) | Used "وظيفة البحث" (job function) instead of "مهمة البحث" (search task) — inconsistent with rest of file | Changed to "مهمة البحث" |
| `errors.outreach.not_found` | Used "الاتصال" (call) instead of "التواصل" (outreach) | Changed to "مسودة التواصل" |
| `errors.leads.bulk_operation_partial` | Awkward "لم يتمكن من" (could not) | Changed to "تعذّر" (consistent with error pattern) |
| `landing.features.cards[0].title` | Used English "spreadsheet" inside Arabic text | Changed to "جداول بيانات" |

---

## Quality Assessment

### Arabic translation quality

The Arabic translations are **professional SaaS-quality**. They use correct
Modern Standard Arabic with appropriate technical terminology throughout:

- UI verbs use the correct imperative/active forms (e.g. أنشئ، حذف، تعديل)
- Business terms are idiomatic (عملاء محتملون، مساحة العمل، لوحة التحكم)
- Placeholders and interpolation variables (`{{count}}`, `{{name}}`, etc.)
  are preserved correctly in all 1 259 keys
- Plural forms use Arabic-appropriate phrasing
- RTL-aware punctuation and formatting are correct

### Intentionally English values (13 items)

These values remain in English by design — they are proper nouns, brand
names, plan tier names, placeholder examples, or technical identifiers:

| Category | Examples |
| --- | --- |
| Email/name placeholders | `you@company.com`, `Avery North`, `avery@northbeam.com` |
| Brand name | `LeadScope AI` |
| Plan tier names | `Starter`, `Growth`, `Enterprise` |
| Compliance label | `SOC 2 \| Type II` |
| Technical identifiers | `us-west`, `isolated-account`, `Series B` |

### Proper nouns in Arabic strings (24 items)

24 Arabic values contain English proper nouns (LeadScope, SerpAPI, OpenAI,
FastAPI, Google, LinkedIn, Northbeam, Brightwave) or technical terms
(markdown, Series B). These are correct — brand names and technical terms
should remain in their original language within Arabic text.

---

## No Hardcoded Text Found

A scan of the frontend source for hardcoded user-facing strings outside the
i18n system found no issues. All visible text is routed through `useTranslation()`.

---

## Recommendations

1. **No action needed on translations.** The four bugs above have been fixed.
2. **Add a CI key-parity check.** A simple Node script comparing
   `Object.keys()` recursively between `en.json` and `ar.json` would catch
   drift before it ships.
3. **Consider ICU MessageFormat for plurals.** Arabic has six plural forms
   (zero, one, two, few, many, other). The current translations handle this
   with phrasing rather than ICU rules, which works but may need revisiting
   if the app adds count-heavy features.
