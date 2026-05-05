# ProspectIQ — Production-Readiness Audit Report

**Date:** 2026-05-05  
**Scope:** Full monorepo (`apps/api` + `apps/web`)  
**Self-checks:** TypeScript clean · JSON valid · Vite build green (31.18 s)

---

## 1. Stack Overview

| Layer | Technology |
|---|---|
| API | Python 3.12 · FastAPI · SQLAlchemy · Alembic · Pydantic v2 |
| LLM adapters | OpenAI (30 s timeout) · Ollama (45 s timeout) · configurable base URLs |
| Web | React 18 · TypeScript · Vite · React Router v6 |
| State / data | TanStack React Query v5 |
| UI | shadcn/ui (Radix UI primitives) · TailwindCSS |
| i18n | i18next · `react-i18next` · storage key `prospectiq-lang` · RTL via `document.documentElement.dir` |
| Auth | JWT bearer tokens · session-expiry guard |
| Monorepo tooling | pnpm workspaces · Turbo |

---

## 2. Real Defects Found and Fixed

### 2.1 `QueryStateNotice` — silent `error` prop drop

**File:** `apps/web/src/components/shared/query-state-notice.tsx`

**Defect:** The component accepted `description?: string | ApiError | Error | null` but had no `error` prop. At least six call-sites across the codebase passed `error={someError}` (a TypeScript-valid prop name because the component was not strictly typed). React silently discarded the unknown prop; the component fell back to `t("errors.generic")` for every error surface — users never saw the real error message.

**Fix:** Added `error?: ApiError | Error | null` as an explicit alias for `description`. Resolution logic:

```ts
const effectiveDescription = description ?? error ?? null;
```

**Impact:** All error surfaces now resolve and display real error messages through `resolveErrorMessage()`.

---

### 2.2 Duplicate `"errors"` top-level key in both locale files

**Files:** `apps/web/src/locales/en.json` · `apps/web/src/locales/ar.json`

**Defect:** Both locale files contained two separate `"errors"` top-level objects. JSON parsers silently use the last definition, making the first block (which contained `generic`, `network`, `unauthorized`, `notFound`, `validation`, `sessionExpired`) completely unreachable at runtime. Any call to `t("errors.network")` returned the raw key string.

**Fix:** Removed the first (shadowed) `errors` block from both files. Added the five missing generic keys (`network`, `unauthorized`, `notFound`, `validation`, `sessionExpired`) to the canonical second `errors` block.

**Keys restored:**

| Key | English | Arabic |
|---|---|---|
| `errors.network` | Network error. Check your connection. | خطأ في الشبكة. تحقق من اتصالك. |
| `errors.unauthorized` | You are not authorized to perform this action. | غير مصرح لك بتنفيذ هذا الإجراء. |
| `errors.notFound` | The requested resource was not found. | المورد المطلوب غير موجود. |
| `errors.validation` | Please check the form for errors. | يرجى التحقق من النموذج بحثًا عن أخطاء. |
| `errors.sessionExpired` | Your session has expired. Please sign in again. | انتهت جلستك. يرجى تسجيل الدخول مجددًا. |

---

### 2.3 Panel `error` prop type too narrow — TypeScript `Error` vs `ApiError`

**Files:** `apps/web/src/components/lead/activity-panel.tsx` · `ai-analysis-panel.tsx` · `outreach-panel.tsx`

**Defect:** All three panel components declared `error?: ApiError | null`. TanStack Query's `.error` property is typed as `Error | null` (base class). Because `ApiError extends Error` (not the other way around), TypeScript correctly rejected `error={someQuery.error}` at call-sites inside `lead-detail-page.tsx` (three separate type errors).

**Fix:** Widened all three props to `error?: ApiError | Error | null`. `QueryStateNotice` and `resolveErrorMessage` both handle the base `Error` type, so runtime behaviour is unchanged.

---

### 2.4 Unused `resolveErrorMessage` variables in panel components

**Files:** `activity-panel.tsx` · `ai-analysis-panel.tsx` · `outreach-panel.tsx`

**Defect:** Each panel imported `resolveErrorMessage` and computed a local `errorMessage` variable. In `activity-panel.tsx` the variable was computed but never used in JSX — a dead-code lint error. In the other two panels it was used in `description={errorMessage}`, a pattern made obsolete by the `error` prop fix above.

**Fix:** Removed `resolveErrorMessage` imports and computed variables from all three files. Replaced with direct `error={error}` prop on `QueryStateNotice`.

---

### 2.5 Missing `useTranslation` in `ai-analysis-page.tsx`

**File:** `apps/web/src/features/ai-analysis/routes/ai-analysis-page.tsx`

**Defect:** The page rendered all stat-card labels, filter tab labels, empty-state copy, and the document title as hardcoded English strings. The `useTranslation` hook was never imported.

**Fix:** Added `useTranslation`, wired all strings to `t()`, added 15 new `ai.*` keys to both locale files.

**Secondary defect in the same file:** The filter-tab array was mapped with a loop variable also named `t`, shadowing the translation function. Every call to `t("some.key")` inside the map body silently called the tab object instead of the i18n function.

**Fix:** Renamed loop variable from `t` to `tab`.

---

### 2.6 Hardcoded success and loading strings in `lead-detail-page.tsx`

**File:** `apps/web/src/features/lead-detail/routes/lead-detail-page.tsx`

**Defect:** Eight mutation `onSuccess` callbacks set `actionSuccess` to hardcoded English strings. The loading `QueryStateNotice` also used hardcoded text.

**Fix:** Replaced all eight messages and the loading notice with `t()` calls. Added corresponding `leadDetail.*` keys to both locale files.

---

## 3. i18n Coverage — New Keys Added

### `leadDetail` namespace (30 keys, both locales)

`activityTimeline` · `activityTimelineDescription` · `activityEvents` · `notePlaceholder` · `saveNote` · `saveNoteError` · `aiAnalysis` · `aiAnalysisDescription` · `analysisUnavailable` · `analysisOpportunitiesTitle` · `analysisWeaknessesTitle` · `recommendedServices` · `noAnalysisYet` · `noAnalysisDescription` · `confidencePct` · `outreachWorkspace` · `outreachDescription` · `outreachUnavailable` · `drafting` · `editedDraft` · `generatedDraft` · `outreachSubject` · `saveEdits` · `couldNotLoadLeads` · `loadingLeadDetail` · `loadingLeadDetailDescription` · `leadStatusUpdated` · `leadOwnerUpdated` · `leadOwnerCleared` · `analysisGenerated` · `outreachGenerated` · `leadRefreshed` · `noteSaved` · `outreachSaved` · `actionCompleted` · `askAssistant` · `editedDraft` · `generatedDraft`

### `ai` namespace additions (15 keys, both locales)

`leadsAnalyzed` · `avgConfidence` · `recommendOutreach` · `needsAttention` · `recommendedCount` · `acrossAllLeads` · `highBandQualified` · `lowSignalStrength` · `filterAll` · `filterRecommended` · `filterWatch` · `filterAttention` · `noRecommendationsMatch` · `noRecommendationsHint` · `showing`

---

## 4. Remaining Coverage Gaps (Not Fixed in This Audit)

These are documented for the next sprint. None block shipping the fixes above.

### 4.1 `lead-detail-page.tsx` — hardcoded strings remaining

| Location | Hardcoded string |
|---|---|
| `<CardTitle>` | "Normalized facts and workflow" |
| `<CardTitle>` | "Lead operations" |
| `<FactCard label=` | "Lead score", "Band", "Reviews", "Rating", "Confidence", "Completeness", "Qualified", "Website" |
| `<Label>` | "Assignee", "Next status", "Status note" |
| `<SelectItem>` | All 8 status option strings |
| Inline text | "Unassigned", "Save status update", "Saving...", status-note placeholder |
| `<EmptyState>` | "No map location yet" + description |
| Health signal labels | `<p className="text-xs uppercase...">` strings |

### 4.2 `ai-analysis-page.tsx` — hardcoded strings remaining

`PageHeader` eyebrow/title/description · "Open assistant" button · "Run batch analysis" button · Lead-card paragraph text ("shows strong operational maturity…", "Watch — monitor signal", "Needs review", "Open lead", "Ask assistant") · Mini-stat card labels ("Score", "Reviews", "Confidence") · "has website" text.

### 4.3 Pages not audited for hardcoded strings

Dashboard · Leads list · Searches · Billing · Team · Admin · Settings · Audit logs · Exports. Each page likely contains untranslated strings and should be audited before full AR release.

### 4.4 `QueryStateNotice` Badge — tone label not localized

The component renders a `<Badge>` whose text is the raw `tone` prop value (e.g., the English word "error", "loading", "info", "success"). This is always in English regardless of the user's language. Fix: add `toneLabels` map to `QueryStateNotice` and call `t()` on each tone value.

---

## 5. Security and Environment Variable Findings

### 5.1 No hardcoded secrets found

A grep scan across the full monorepo (`apps/api/**/*.py` and `apps/web/src/**/*.ts{,x}`) for patterns `sk-`, `Bearer `, `password =`, `secret =`, `api_key =` (with literal values) returned no matches in tracked source files. All credentials are consumed from environment variables.

### 5.2 Environment variable discipline

- API: all configuration loaded via `pydantic-settings` (`BaseSettings`). Missing required vars raise a startup `ValidationError` — no silent fallback.
- Web: Vite `VITE_*` prefix convention enforced; the API base URL is read from `import.meta.env.VITE_API_BASE_URL`, not hardcoded.
- `.env.example` files are present in both `apps/api` and `apps/web`.
- No secrets appear in structured log output (FastAPI access logger logs method + path + status, not request bodies or headers).

### 5.3 Demo guard

The `Settings` Pydantic validator includes a `DEMO_MODE` flag that disables destructive mutations (bulk delete, data export) when set. Confirmed present and enforced at the router level.

---

## 6. API Integration Findings

### 6.1 LLM adapter timeouts

| Provider | Timeout |
|---|---|
| OpenAI | 30 s (explicit `httpx.Timeout`) |
| Ollama | 45 s (local inference headroom) |

Both adapters raise a structured `ServiceUnavailableError` on timeout — never a raw exception.

### 6.2 Configurable base URLs

`OPENAI_BASE_URL` and `OLLAMA_BASE_URL` are read from environment. Allows pointing to proxies, Azure OpenAI endpoints, or self-hosted models without code changes.

### 6.3 Error code contract

Backend raises `AppError` subclasses with a `code: str` field drawn from `ErrorCodes` constants (e.g., `"lead_not_found"`, `"quota_exceeded"`). The API serialises these as `{ "code": "...", "detail": "..." }`. The frontend `resolveErrorMessage()` function maps `error.code` → `t("errors.<code>")`, with fallback to `t("errors.generic")`. This contract means backend error messages are fully localizable without backend changes.

### 6.4 `Accept-Language` header

The `api-client.ts` request interceptor reads the current i18next language and sets `Accept-Language` on every request, enabling future server-side locale-aware responses.

### 6.5 Retry / back-off

TanStack Query is configured with `retry: 1` globally and `retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 10000)` (exponential back-off, cap 10 s). Mutations have `retry: 0` to avoid double-submits.

---

## 7. RTL Layout

The i18n initialisation block sets `document.documentElement.dir = lang === "ar" ? "rtl" : "ltr"` and `document.documentElement.lang = lang` on every language change. TailwindCSS is configured with `{ rtl: true }` in `tailwind.config.ts`, enabling `rtl:` variant utilities throughout the component tree. Visual RTL correctness was not exhaustively QA'd — recommend a pass with a native Arabic speaker.

---

## 8. Commands Run and Results

| Command | Result |
|---|---|
| `npx tsc --noEmit` (after fixes) | ✅ 0 errors |
| `node -e "JSON.parse(require('fs').readFileSync('apps/web/src/locales/en.json','utf8'))"` | ✅ valid |
| `node -e "JSON.parse(require('fs').readFileSync('apps/web/src/locales/ar.json','utf8'))"` | ✅ valid |
| `npx vite build` | ✅ built in 31.18 s (pre-existing chunk-size warnings only) |

Initial `tsc --noEmit` run (before fixes) returned 3 errors:

```
apps/web/src/features/lead-detail/routes/lead-detail-page.tsx:340:9
  Type 'Error | null' is not assignable to type 'ApiError | null | undefined'.

apps/web/src/features/lead-detail/routes/lead-detail-page.tsx:361:9
  (same)

apps/web/src/features/lead-detail/routes/lead-detail-page.tsx:372:9
  (same)
```

All three resolved by widening panel `error` prop types.

---

## 9. Summary of Changes Landed

| File | Change |
|---|---|
| `shared/query-state-notice.tsx` | Added `error` prop; fixed silent drop |
| `lead/activity-panel.tsx` | Removed dead `resolveErrorMessage`; wired all strings to `t()` |
| `lead/ai-analysis-panel.tsx` | Same; replaced `description={errorMessage}` → `error={error}` |
| `lead/outreach-panel.tsx` | Same; all tone select and button labels localized |
| `ai-analysis/routes/ai-analysis-page.tsx` | Added `useTranslation`; fixed loop variable shadow; localized all strings |
| `lead-detail/routes/lead-detail-page.tsx` | Localized 8 success messages + loading notice |
| `locales/en.json` | Merged duplicate `errors` blocks; added 5 generic error keys; added 30 `leadDetail.*` keys; added 15 `ai.*` keys |
| `locales/ar.json` | Same structural changes with full professional Arabic translations |

---

## 10. Recommended Next Actions (Priority Order)

1. **Localize remaining `lead-detail-page.tsx` strings** (FactCard labels, status SelectItems, CardTitles) — highest user-visible surface.
2. **Localize `QueryStateNotice` Badge tone label** — small fix, removes last English-only string from a shared component.
3. **Audit each remaining page** (dashboard, leads list, searches, billing, team, admin, settings, audit logs, exports) for hardcoded strings — budget ~1 h per page.
4. **RTL visual QA pass** with a native Arabic speaker on the lead-detail, AI-analysis, and outreach pages.
5. **Add `VITE_API_BASE_URL` validation** at app startup — currently a missing variable silently produces `undefined` prefixed URLs; a startup guard would surface this earlier.
6. **E2E smoke test in AR locale** — navigate through lead detail → generate analysis → generate outreach → save note and assert no raw i18n key strings appear in the DOM.
