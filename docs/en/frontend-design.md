# Frontend Design Specification

> 🌐 [中文](../20-前端设计规范.md) | **English**

This document is the single source of truth for GoldMind's frontend **visual language and UI copy**.
Read it before changing the frontend interface; for what the product does see `docs/00-产品方向.md`;
for commands and directories see `README.md`.

> Status: this specification landed with the **frontend rewrite** on 2026-10-03 — the stack moved from
> React to **Vue 3 + TypeScript + Pinia**, the visual language moved from "light research brief" to
> **Apple macOS / HIG**, and the directory is now grouped by feature. From now on, any new interface
> must first have its rules added here, then be written in code.

---

## 1. Character

GoldMind's interface is a **financial research brief** that looks like a native macOS app, not an AI showcase board:

- It reads like a research report: conclusion first, evidence after; numbers can be checked and sources traced.
- Quiet: no decorative gradients, no glow, no stacked glassmorphism, no colored badges, no exclamatory copy.
- Layered: hierarchy is built from **surfaces, hairlines, corner radii and very light shadows** (the macOS
  way), not from cards inside cards.

**The only deliberate emphasis is the sidebar's daily quote block and each section's "one-line conclusion".**
Everything else stays restrained.

---

## 2. Design Tokens

Defined in `app/src/styles/tokens.css`; components may only reference tokens and must **not** write new hex
colors (`app/src/__tests__/guards/designTokens.test.ts` enforces this in the gate). `app/src/lib/tokens.ts`
keeps a runtime fallback for SVG, and `lib/__tests__/tokens.test.ts` fails if the two drift apart.

### Surfaces and lines

| Token | Value | Purpose |
|---|---|---|
| `--bg` | `#F2F2F7` | Window background |
| `--surface` | `#FFFFFF` | Content surface: cards, tables, panels |
| `--surface-2` | `#FBFBFD` | Secondary surface: table headers, footer, bands |
| `--surface-sunken` | `#ECECF0` | Sunken surface: segmented-control track |
| `--fill-quaternary` | `rgba(120,120,128,.08)` | Hover / selected fill |
| `--separator` | `#D8D8DE` | Hairline (1px dividers, table lines, grid lines) |

### Text and semantic colors

| Token | Value | Contrast on white | Purpose |
|---|---|---|---|
| `--text` | `#1D1D1F` | 16.7:1 | Headings and body text |
| `--text-secondary` | `#6E6E73` | 5.1:1 | Secondary information (time, source, notes) |
| `--text-tertiary` | `#6E6E73` | 5.1:1 | Same value as secondary — Apple's lighter `#8E8E93` is only 3.3:1, below the 4.5:1 floor; hierarchy is expressed with weight and size instead |
| `--accent` | `#0071E3` | 4.6:1 | Apple blue: links, selected tab, primary button |
| `--gold` | `#A67C00` | 4.5:1 | The **only** accent color for the gold price and key numbers |
| `--up` | `#C8102E` | 6.2:1 | Up (red) |
| `--down` | `#1D7A3E` | 5.4:1 | Down (green) |
| `--warn` | `#8A5300` | 6.3:1 | Worth noticing |
| `--danger` | `#B3261E` | 6.6:1 | Failure, gap years |

Semantic color rules:

- Price direction **must** be expressed by both ▲▼ and the words up/down; color only reinforces it and never
  carries the meaning alone.
- Red for up, green for down, matching Chinese investors' reading habit.
- Every foreground/background pair is measured against **4.5:1**; update the contrast column above when changing a color.
- "Accumulating" is a neutral fact (a new series is still short); it must **not** use the error/gap color.
  "Gap year" is the anomaly and uses the error style.

### Geometry and shadows

| Token | Value | Purpose |
|---|---|---|
| `--radius-sm` | `6px` | Buttons, inputs, tags |
| `--radius` | `8px` | Cards, panels, table containers |
| `--radius-lg` | `10px` | Sidebar, sheets |
| `--radius-pill` | `999px` | Pill tags, nav items |
| `--shadow-1` | `0 1px 2px rgba(0,0,0,.04), 0 1px 1px rgba(0,0,0,.03)` | Cards, table containers |
| `--shadow-2` | `0 8px 24px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04)` | Overlays: tooltips, skip link |

**There are only two shadow levels and they are never mixed within a level.** Hard constraints:
**no decorative gradients, no glow, no colored badges, no stacked `filter: blur`**; the sidebar's
`backdrop-filter` is the only permitted blur (see section 4).

### Type and layout

- System stack only: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif`.
  Zero downloads, zero new assets. **No serif stack** — headings and body share one family and are layered
  by weight, size and letter spacing.
- All numbers use `font-variant-numeric: tabular-nums`; prices and percentages are right-aligned.
- Sizes (Apple scale): 11 / 12 / 13 / 15 / 17 / 20 / 22 / 28 / 34 / 40.
- Body line height 1.6, heading line height 1.25; body measure ≤ 68ch; paragraphs are left-aligned.
- Dates and times only ever show fields returned by the backend; never derive "today" in the browser
  (see `docs/ARCHITECTURE.md` section 7).
- **Numbers go into tables**: multiple values for one entity (stats, factors, monitor, backtest, source status)
  must be laid out as a table, not strung into a sentence with commas; only a "one-line conclusion" may put two
  or three key numbers into prose.

---

## 3. Directory and Components

The frontend is **Vue 3 single-file components + Pinia**, with two HTML entries (`index.html` for the dashboard,
`research.html` for the research page) and **no client-side router** — the relative link `./research.html` just works.

```
app/src/
├── styles/{tokens.css,base.css}    Design tokens + base styles and semantic classes (single source)
├── testids.ts                      Selector contract (see section 7)
├── entries/{dashboard,research}.ts Two entries: install Pinia, import styles, mount
├── services/api.ts                 HTTP client and response types
├── stores/{market,freshness,aiConfig}.ts   Pinia stores
├── composables/{useAsyncBlock,useFreshnessBlock}.ts
├── lib/{format,placeholder,apiError,tokens}.ts
├── components/                     Shared components (including charts/)
├── layout/{AppSidebar,FooterBar}.vue
├── views/dashboard/                The eight dashboard sections + quant/ and data/ subcomponents
└── views/research/                 The eight research-page sections
```

### Shared components

| Component | Responsibility | Constraint |
|---|---|---|
| `AppSidebar` | Left sidebar: wordmark, nav, and (dashboard only) today's brief and data freshness | `variant` picks dashboard vs research; the whole column is sticky (`pageStructure.test.ts` requires exactly one `<nav>` on the page, so both entries share it); the **research page must carry a back button**, and the wordmark links home on both |
| `SectionBlock` | Section container: anchor, title, one-line note, actions | Title left-aligned; the `verdict` slot holds the "one-line conclusion" |
| `PanelBlock` | Card / panel: title plus top-right meta | Same level uses `--shadow-1` only; nested panels use `plain` to drop the shadow |
| `DataTable` | Generic table: column defs, row key, empty state, fixed source column | Horizontal scroll on narrow screens; cells prefer a same-named scoped slot |
| `TabsNav` | Segmented control + ARIA tablist | **`panelId` is required**: multiple tab groups on one page must not collide on ids |
| `Disclosure` | One level of disclosure (native `<details>`) | **Never nest two levels** |
| `StateBlock` | loading / analyzing / unavailable | `role="status"`; unavailable must give a reason and a next step |
| `RefreshButton` | Manually trigger analysis or fetch | Copy is "重新分析" / "重新抓取" / "抓取最新消息"; the busy label follows the action; the disabled state stays visible |
| `QuoteBlock` | Quote: name, value, change, source | Tabular numerals; change shows both ▲▼ and a word |
| `MetadataBlock` | Generation info (cache / sources / method / time) | Backend fields only, never derived |
| `FactorList` | Factor entries, each one disclosure | Native `<details>`, keyboard accessible |
| `InstitutionTable` | Institution views table | Includes prediction date and staleness note; horizontal scroll on narrow screens |
| `StrategyColumns` | Three strategy tiers side by side | Stacks to one column on narrow screens |
| `charts/{AreaChart,DualAxisLineChart}` | Hand-rolled SVG charts | No blinking last point, no entrance animation, no gradients; the tooltip only appears on pointer entry; **must clear `figure`'s default margin** (1em 40px, which otherwise overflows the container on narrow screens) |
| `SignOff` | Analysis byline | Model name read from `/health`; writes "model unknown" when unavailable |

### Layout primitives (`styles/base.css`)

| Primitive | Purpose | Key constraint |
|---|---|---|
| `.app-shell` | Two-column shell: `sidebar + minmax(0, 1fr)` | Fills the viewport when wide; one column at `≤ 960px` |
| `.app-shell__content` | Right-hand column (content and footer share its width) | `min-width: 0`, or tables widen the whole page |
| `.app-main` | Content area | `min-width: 0`; keeps `--shell-gap` / `--shell-pad` breathing room |
| `.wrap` / `.wrap--fill` | Measure container; the `--fill` variant stretches with the content column | `.wrap` only for single-column cases |
| Grid children `min-width: 0` | Children of `.app-shell`/`.grid-2`/`.grid-3`/`.stack`/`.metrics` | **Required**: the default `min-width: auto` lets long paragraphs, tables and charts widen their track, which shows up as a horizontally scrolling page |
| `.table-scroll` | Horizontal scroll container for tables | It needs `min-width: 0; max-width: 100%` itself, or "scroll inside the table" turns into "scroll the whole page" |

### Data flow

```
Section component ──useAsyncBlock──► services/api.ts ──► backend
   │                                     ▲
   └─useFreshnessBlock──► stores/freshness ──► sidebar freshness
Quote polling ──stores/market (30s, paused while hidden)──► market / drivers sections
```

- `useAsyncBlock(fetcher, {fallback, timeout})`: first load and "re-analyse" track separate state, and every
  failure goes through `describeApiError`. **Timeouts must have their own copy** — analysis calls hit an LLM,
  and "try again later" is a different remedy from "we could not get a result".
- `stores/market`: the single source for quote data — 30-second polling (paused while the tab is hidden, one
  immediate catch-up on return), a 5-second cache window, and in-flight de-duplication per URL.
- Sections **never render the freshness bar themselves**: they register with `stores/freshness` and the sidebar
  renders it (one fact, one source).

---

## 4. Layout and Reading Order

**The whole page is a two-column shell (`.app-shell`): a left sidebar plus a content column.**

```
┌───────────────────┬──────────────────────────────────────────────┐
│ sidebar .toolbar  │ content .app-main (takes the rest, fills the  │
│  · wordmark       │                    whole page)               │
│  · anchor nav     │                                              │
│  · today's brief  │  conclusion → market → drivers → messages     │
│  · data freshness │  → quant → strategy → data & methods          │
│  (sticky column)  │  footer .footer (same width, also fills)      │
└───────────────────┴──────────────────────────────────────────────┘
```

- The sidebar is a fixed `--sidebar-width` (300px), **`position: sticky` as a whole column** and independently
  scrollable; its background is one step deeper than the content surface (`--sidebar-bg`) with a hairline on its
  right edge.
- **Getting back**: the research page is a separate entry (`research.html`) with no client-side router, so returning
  to the dashboard can only be a plain link. The research sidebar therefore carries an explicit **back button**
  (`a.toolbar__back`, "‹ 返回看板", pointing at `./index.html`), and on **both** entries the wordmark itself links
  home (the macOS convention). Returning deserves two entry points: leaving "看板" as just another nav item lost
  people (`ResearchPage.test.ts` guards this).
- The content column is `grid-template-columns: minmax(0, 1fr)` and takes every remaining pixel — the body text is
  **no longer centred and narrowed to 1180px**. Readability is guaranteed by each section's own `--measure` (68ch)
  line-length cap instead of by squeezing the whole page, so tables and charts fit on one screen on a wide display.
- `--shell-max` (2400px) is only a backstop on ultra-wide displays, so a 4K monitor does not stretch a paragraph
  into a 200-character line.
- **Below `--bp-narrow` (960px) it collapses to a single column**: the sidebar becomes a bar at the top of the page
  (nav goes horizontal, freshness becomes a multi-column grid) and the content takes the full row. The breakpoint
  lives in a media query (CSS variables cannot be used in media conditions), so the 960px in `base.css` must stay in
  sync with `--bp-narrow` in `tokens.css`.
- The sidebar keeps the class name `.toolbar` (both `scripts/capture_screenshots.mjs` and
  `scripts/verify_layout.mjs` locate it by that name) — but it is a **column**, not a bar.

**Dashboard (`app/src/views/dashboard/DashboardPage.vue`) has exactly one entry point, top to bottom, in a fixed order:**

1. Sidebar `AppSidebar` (`variant="dashboard"`): wordmark + anchor nav (Today's conclusion / Market / Drivers /
   Messages / Quant prediction / Strategy / Data & methods / Research) + today's brief + data freshness
2. Today's conclusion `#conclusion`
3. Market `#market`
4. Drivers `#drivers` (bullish `#drivers-bullish` / bearish `#drivers-bearish` / institutions `#institutions`) —
   the model's reading of the day's facts
5. Messages `#messages` (a first-class section since 2026-10-03: high-authority raw news, top 10 per window.
   It used to live inside "Drivers" with no sidebar entry of its own — raw facts and the reading of them are now
   two sections, each reachable on its own)
6. Quant prediction `#quant` (decision horizons → fair-value decomposition → monitor signals → backtest → the four factor categories)
7. Investment strategy `#strategy`
8. Data & methods `#data-methods` (sync report → source availability → bootstrap progress → config hot reload →
   service status → basis legend)
9. Footer `FooterBar` (data sources / analysis model / one shared disclaimer)

**Research page (`app/src/views/research/ResearchPage.vue`) has a fixed order:**
sidebar `AppSidebar` (`variant="research"`, adding a link back to the dashboard and the report generation time) →
version & verdict `#verdict` → forward holdout `#forward` (including the Beta posterior and CRPS) → coverage
`#coverage` → calibration diagnostics `#diagnostics` → regimes & candidates `#regimes` → factor breakdown
`#factors` → benchmark candidates `#benchmarks` → sync report `#sync`.

**Sidebar look**: a translucent background plus `backdrop-filter: saturate(180%) blur(20px)`; under
`@supports not (backdrop-filter: …)` it falls back to an opaque `--sidebar-bg`. Today's brief is stacked vertically
inside it: the headline number uses `--text-2xl`, bold and tinted `--gold`; the change gets its own line with
"▲ + percentage + up/down"; the basis and source collapse into a small meta line.

**Hard readability rules** (every section must satisfy them):

- The first line of a section is a "one-line conclusion + key numbers"; details go into **at most one** level of
  disclosure. Two nested levels are not allowed (`pageStructure.test.ts` enforces this).
- Data that has a source or an as-of must have fixed "source" and "as of" columns, filled per row, so readers never
  have to guess. Missing values are "—"; columns are never dropped.
- Every field must have a slot; showing "—" or a degraded explanation is better than hiding a field (see section 8).
- Color only reinforces; meaning must be carried by ▲▼ or by words.
- Order is priority: the most important conclusion goes on top; readers should not have to read the method before
  the conclusion.

**Data freshness**: listed block by block **vertically** in the sidebar — the as-of or analysis time and state
(fresh / analyzing / stale / unavailable / pending) for `market / dollar index / bullish factors / bearish factors /
messages / institution views / quant prediction / investment strategy / today's conclusion` — plus a top-level
summary. Blocks without a time show "time unknown" rather than substituting the browser clock.

**Layout self-check**: `cd app && node scripts/verify_layout.mjs` (needs the real stack running). Unit tests run in
happy-dom, which has **no layout engine**, so it cannot see "the whole page scrolls horizontally" (this round hit
that twice: a chart that never cleared `figure`'s default 40px margin, and grid children missing `min-width: 0`).
The script measures in a real browser at 1440×900 and 390×844: no horizontal overflow (offending elements are named),
two columns filling the viewport and a single column when narrow, a sticky sidebar with its hairline, live design
tokens, no decorative gradients/glow, reachable anchors, and body/secondary text contrast ≥ 4.5:1.

---

## 5. Section Semantics

**Quant prediction (`QuantSection`) block order** (top to bottom):

1. Conclusion line — model version, available factor count, as-of, and the one-year-horizon headline;
2. **Decision horizons** — five horizon tabs (1 day / 1 week / 1 month / 1 quarter / 1 year): direction (the
   calibrated expected-return drift; exactly zero reads "flat"), probability up, base and target price, the three
   scenario ranges with trigger/invalidation conditions, and per-factor contributions. The 250-day direction may be
   `not_published`; the page then shows `direction_reason` verbatim and **must not** draw a fake arrow;
3. **Fair-value decomposition** — market vs fair value, the four blocks and their drivers, fit R² and sample size;
4. **Monitor signals (weekly table)** — participating signals vs "watch only":
   - **participating**: enter the composite score and carry a direction (bull / bear / neutral);
   - **watch only**: informational series (USDCNY, CNY gold price, CFTC open interest, GVZ, gold/silver ratio,
     copper/gold ratio, positioning ratio, GPR, message intensity) get a value and a rule note but no direction.
5. **Backtest** — this model side by side with the baselines (always long / momentum / coin flip), CRPS score and
   skill, the Beta posterior, and the regime walk-forward (per-regime hit rate, both baselines and the reason);
   insufficient samples state the reason;
6. **The four factor categories** — per-factor table (including the coverage profile and publication lag).

Quant-specific rules: per-source states such as "not due" live inside the folded "source status" area rather than
taking up the main layout; any unavailable block gives a reason instead of numbers; long/short signals may only come
from the deterministic rules in `backend/app/services/quant/monitor.py` — the UI never makes its own call. Scenario
trigger/invalidation conditions must be checkable against the factor table and the 200-day moving average; the UI
does not compute a second set of numbers. Benchmark choices and roll notes must be shown verbatim, unembellished.

**Messages (`MessagesPanel`) rules**: each of the three windows takes its top 10, and one event may appear in several
windows. The expanded area gives the summary, scoring signals, event tags and same-story links; links that go through
an aggregator are marked "via aggregator" (`via_aggregator`). The top meta line shows the last fetch time, and a
manual fetch appends this run's report (ok sources / new items / failed sources / translated items). Empty window and
empty database are different: an empty window gets one sentence, an empty database gets a `StateBlock` with the
backend's reason and a retry path.

**Showing the Chinese translation (2026-10-03)**: the source pool is all English, so every item carries a Chinese
title and a two-to-three sentence Chinese brief **in its collapsed state** — a reader should not have to expand each
row to learn what happened today.

- **The Chinese is additive, not a replacement**: the English title always stays visible (the small line under the
  Chinese one), the English summary stays in the expanded area, and AI output carries an "AI 译" tag plus a
  provenance line (model, generation time, caliber). Readers can check every item instead of having to trust it.
- **Translation status has its own line**: on/off, model, pending count, reason. The reason only exists when there
  really are untranslated items that cannot be translated right now (switched off / LLM unconfigured / daily budget
  exhausted / last parse failed); when everything is translated the page does not wave a scary "unavailable" at you.
- **No Chinese is improvised**: without a translation the card shows the English title plus "Chinese translation
  unavailable (reason)". A dictionary, a template or the model's own impression must never be used to fake it
  (`AGENTS.md` red line 1). The frontend never translates, reorders or scores anything itself.
- **The banned-words list still applies**: the translation must not be described as "real-time translation" or
  "accurate translation" (see section 6).

**Gold price refresh time (2026-10-03)**: six places show the international gold price — the sidebar brief, the market
section and its quote block, "current price" in today's conclusion, the degraded strategy snapshot, the quant "base
price", and the fair-value "market price". **Every one of them must also give that price's own as-of, basis and
source**:

- The timestamp comes from **that price's own** field (`stats.price_as_of` / `summary.price_as_of` /
  `advice.snapshot.as_of` / `predictions.as_of` / `fair_value.as_of`) — never from the browser clock and never from
  page load time (the rule: time only flows from backend fields).
- When the as-of is missing the page says "gold price refresh time unknown (not returned by the backend)" — inventing
  a "just now" is worse than admitting there is none.
- The wording, the missing-value sentence and the field-level selectors live in exactly one component
  (`components/GoldPriceAsOf.vue`), referenced by all six places, so the phrasing cannot drift apart.
- Institutional targets and model-predicted prices are **not** the current gold price and are out of scope for this
  rule (their dates live in their own tables).

**Research page rules**: the verdict only counts independent bets in the forward holdout; while it is still short, the
state reads "not yet decidable" together with how many trading days are missing, and **must not** be written as
"failed the bar". The historical holdout column must be labelled as "already seen, recorded only". The data window
(start, end, trading days, years) is prominently shown at the top of the page.

---

## 6. UI Copy

**Forbidden words** (must never appear in the interface):

`Agent`, `multi-agent`, `AI-driven`, `ReAct`, `RAG`, `deep learning`, `live scraping` (as a capability claim), plus
Sparkles / Bot / Brain style "AI decoration" icons and 🚀✨🤖 emoji.

Reason: the implementation is a single-turn LLM call (see `docs/00-产品方向.md` section 3); these words are either
untrue or purely decorative. `app/src/__tests__/guards/forbiddenCopy.test.ts` renders every section and scans the
visible text, and `app/e2e/dashboard.spec.ts` scans the whole page again in a real browser.

**Glossary** (the words the interface uses):

| Situation | Wording |
|---|---|
| The two directions of an analysis | bullish factors / bearish factors |
| Institution target-price block | institution views |
| Strategy block | investment strategy |
| Conclusion block | today's conclusion |
| Data unavailable | data unavailable (with a reason) |
| Backend has started analysing | analysing (and stating that this is placeholder content) |
| Not enough input to analyse | insufficient data (say what is missing; no strategy, only market stats) |
| Analysis generation time | analysis time |
| Quote source | data source |
| Direction withheld | not published (with a reason; no arrow) |
| A new series is still short | accumulating (not a gap) |
| A year with gaps | gap year |
| The verdict window has too few bets | not yet decidable (with how many are missing) |

**Byline**: every analysis block ends with
`generated by {provider} {model} · analysis time {generated_at} · for reference only`;
when the model name cannot be read, write "model unknown (/health did not return it)" rather than hardcoding a model.

**Footer**: the data-sources column lists only real sources (Tencent Finance, Sina Finance, RSS news sources); the
model column follows the byline rule above and notes that "institution views take each institution's most recent
verifiable forecast and may be stale (the prediction date is shown in the table)". The disclaimer stays.

**Bottom line**: never fabricate data. When a source is unavailable, show "data unavailable" rather than using a
built-in constant, a default, or a model's impression to produce institution target prices, central-bank purchases or
gold price levels (see `docs/00-产品方向.md` section 5).

---

## 7. Test Selector Contract (TESTIDS)

The single source is `app/src/testids.ts`, which exports a frozen `TESTIDS`:

- **Structural selectors** (`TESTIDS.app` / `sectionQuant` / `quantFairValue` / `researchVerdict` …): used by e2e and
  the screenshot script to locate whole regions; names use "block or panel" semantics.
- **Field selectors**: `fieldTestId(path)` = `` `field-${path}` ``, with dotted "response type.field name" paths
  (`stats.price_basis`, `quant.factors.coverage.sparse_years`, `accuracy.regimes.pre.accuracy`). Nested components
  (`research`, `health`) are expanded recursively inside `TESTIDS.field`; only leaves are directly queryable strings.
- **Components, tests and scripts share the same strings**: vitest and Playwright import this file directly;
  `app/scripts/capture_screenshots.mjs` is `.mjs` and cannot import TS, so it repeats the same literals and must be
  kept in sync (which is also why that script checks each block for real content).
- **Never** hand-write `field-` strings or bare `data-testid` values in tests; always go through `TESTIDS` /
  `fieldTestId()`.

**Guards in the gate** (`app/src/__tests__/guards/` plus each section's `__tests__/`):

| Guard | What it protects | Does breaking it go red? |
|---|---|---|
| `views/dashboard/__tests__/fieldCoverage.test.ts` | Mounts every section with all-non-empty fixtures and asserts **every leaf** of `TESTIDS.field` is in the DOM | Yes (measured: removing one slot turns it red) |
| `__tests__/guards/forbiddenCopy.test.ts` | Visible text of all rendered sections contains no forbidden capability claim | Yes (measured: adding "Agent" to a button label turns it red) |
| `__tests__/guards/pageStructure.test.ts` | One h1, skip-link target exists, one each of header/nav/main/footer, nav anchors resolve, reading order, unique ids, tabs carry `aria-selected`, buttons have accessible names, no nested disclosures | Yes (measured: two tabpanels sharing ids turns it red) |
| `__tests__/guards/designTokens.test.ts` | Components and styles contain no hardcoded hex colors / `white` / `black` | Yes |
| `lib/__tests__/tokens.test.ts` | The fallbacks in `lib/tokens.ts` match the declarations in `tokens.css` | Yes |

**New response field → add a `TESTIDS.field` entry → add the slot → extend the fixtures**, or the guard goes red.

**e2e layers**:

- `app/e2e/`: the default layer (`npm run test:e2e`), fully offline — fake LLM + seeded SQLite + preview proxy;
- `app/e2e-live/`: the real-stack layer, triggered by `E2E_LLM=real npx playwright test e2e-live`; without
  `E2E_LLM=real` the whole group is `test.skip()` and the default run is unaffected. The real-stack layer asserts that
  the main blocks are non-empty, that refresh closes the loop (after `POST /api/gold/quant/refresh` the content updates
  with no error state), and that no unavailable block remains.
- **Screenshot script**: `node scripts/capture_screenshots.mjs` first polls `/health`'s bootstrap (it only starts
  shooting once that is done / disabled / skipped or every phase has settled), then checks each block for
  "non-empty + no empty-state marker"; if any block fails it writes **no image** and exits non-zero. Fifteen fixed
  file names (in page reading order): `dashboard / market / price-trend / news-analysis-up / news-analysis-down /
  institutional-views / messages / investment-advice / quant-fair-value / quant-monitor / quant-accuracy /
  quant-prediction / research-verdict / research-forward-window / research-overview`.
  `SCREENSHOT_ONLY=<name substring>` re-shoots just those.

---

## 8. Field → Display Location

The table below covers the fields added or emphasised in 2.0.2; every other field must also have a slot, which the
per-field assertions in `fieldCoverage.test.ts` guarantee. The path column is the `data-testid` of `field-{path}`.

| Field (path) | Display location |
|---|---|
| `stats.price_basis` / `price_basis_label` / `price_as_of` | Market → market snapshot (all fields) table, "price basis / basis note / basis time" columns; sidebar brief and the New York gold quote meta |
| `correlation.gold_basis` / `gold_basis_label` / `gold_source` | Market → correlation table, per-row column (gold basis) |
| `correlation.dollar_basis` / `dollar_basis_label` / `dollar_source` | Market → correlation table, per-row column (dollar basis) |
| `correlation.as_of`, `daily.basis` / `basis_label` / `source` / `as_of` | Market → correlation / daily tables, per-row source and as-of columns |
| `dollar.*` (price / previous_close / change / change_percent / open / high / low / updated_at / date / source) | Market → dollar-index quote block and snapshot table; the quote block states source and data time |
| Basis legend (`gold_basis_label` / `dollar_basis_label` notes) | Data & methods → basis legend (`data-legend`) |
| `sources.rows.*` (channel, channel_label, source_key, status, status_label, stale, age_hours, started_at, finished_at, items, error) | Data & methods → source availability table, one row per channel's latest attempt |
| `sources.summary.*`, `sources.generated_at` | Data & methods → source availability summary sentence and generation time |
| `health.bootstrap.*` (enabled, status, ready, step.index, step.total, error, started_at, finished_at, migrations) | Data & methods → bootstrap progress conclusion line and meta (status shows disabled / skipped / failed verbatim) |
| `health.bootstrap.phases.*` | Data & methods → bootstrap progress → phase table, one row per phase |
| `health.bootstrap.gaps.*` (gold_prices, dollar_index, gold_news, news_digest, quant) | Data & methods → bootstrap progress → data gap table, one row each |
| `health.config_watch.*` | Data & methods → config hot reload (file name and key names only, never a value) |
| `health.status` / `version` / `timestamp`, `health.services.*` | Data & methods → service status table (keys appear only as "configured or not", plus the endpoint) |
| `quant.sync.*` | Data & methods → sync report (per-source detail lives in the quant section's folded area and is not repeated) |
| `predictions.direction_status` / `direction_reason` | Quant → decision horizons → prediction line: `not_published` shows "not published + reason" with no arrow |
| `predictions.price_basis.*` | Quant → decision horizons → prediction base-price basis line |
| `quant.factors.publication_lag_days` | Quant → four factor categories, "publication lag" column |
| `quant.factors.coverage.*` | Quant → four factor categories → factor detail row: `coverage first — last · N obs · Y years`; `sparse_years` shows "gap year"; `accumulating` shows "accumulating (series still short, not a gap)"; `year_counts` folds away one level |
| `digest.items.*` (including `title_zh`, `brief_zh`, `translated`, `translation_model`, `translated_at`, `via_aggregator`, `event_tags`, `event_labels`, `signals`, `related.*`) | Messages → each card and its expanded detail, field by field (Chinese title and brief while collapsed; translation provenance and the English original in the expanded area) |
| `digest.fetch.*` (including `translated`, `translation_reason`) | Messages → last fetch report (folded) and the refresh report after a manual fetch |
| `digest.translation.*` | Messages → the translation status line: on/off, model, pending count, reason |
| `accuracy.metrics.*` (including CRPS, independent bets, `down_calls` / `down_call_edge_vs_up`, `expected_cap_rate`) | Quant → backtest → skill table, row by row |
| `accuracy.regimes.pre.*` / `post.*` | Quant → backtest → regime walk-forward table, per regime and column |
| Beta posterior (`research.horizons.forward_posterior.*`) | Research → forward holdout → Beta posterior and CRPS table |
| `research.benchmark.*` / `alternatives.*` | Research → benchmark candidates: default benchmark, candidates, roll notes and unavailability reasons shown verbatim |
| `research.data_window.*`, `research.holdout_start` / `active_holdout_start` | Research → version & verdict / coverage (source and data-window columns) |
| Remaining research fields (`research.periods.*`, `horizons.*`, `factors.*`, `reliability.*`, `regimes.*`, `sync.*`) | Research → the corresponding tables, column by column; guaranteed by `fieldCoverage.test.ts` |
| Institution fields (`institutions.*`) | Drivers → institution views table, column by column (the prediction-date column adds "stale by N days" beyond 30 days) |
| Strategy fields (`advice.*`) | Drivers → three strategy tiers and the risk warning; when data is insufficient only the price snapshot (`advice.snapshot.*`, including the snapshot price's own `as_of` / `basis_label` / `source`) is shown |
| `summary.*` | Today's conclusion: conclusion line + metric row + folded evidence + target-price reference table + generation info; `summary.price_as_of` / `price_basis_label` / `price_source` sit on the same line as "current price" |
| Gold price timestamps (`predictions.base_price_as_of`, `fair_value.market_price_as_of`) | Quant → decision horizons "base price" and fair-value "market price", each carrying its own refresh time |

---

## 9. Motion, Accessibility and Print

- Motion only ever responds to a person's action (refreshing, hover, expanding); there are no automatic entrance
  animations, and `prefers-reduced-motion` turns everything off. Duration tokens: `--dur-fast` 150ms, `--dur` 220ms.
- Semantic tags: `header` / `nav` / `main` / `footer`; one h1 per page; a skip link straight to the main content.
- Keyboard focus is visible (`box-shadow: 0 0 0 3px rgba(0,113,227,.35)`); interactive elements must be native
  `<button>` / `<a>` / `<details>` — `div[onclick]` is forbidden.
- Tablists follow ARIA behaviour: ← → move between tabs (auto-activating), Home / End jump to the ends, and only the
  current tab is in the tab sequence (roving tabindex); `id` / `aria-controls` carry an instance prefix.
- Print: hide nav and action buttons, drop background colors, avoid page breaks inside tables and charts.
