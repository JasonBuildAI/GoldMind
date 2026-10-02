# Frontend Design Specification

> 🌐 [中文](../20-前端设计规范.md) | **English**

This document is the single source of truth for GoldMind's frontend **visual language and UI copy**. Read it before changing the frontend interface;
for what the product does see `docs/00-产品方向.md`; for commands and directories see `README.md`.

> Status: this specification landed with the frontend presentation-layer refactor on 2026-09-30. From now on, any new interface must first have its rules added here, then be written in code.

---

## 1. Character

GoldMind's interface is a **financial research brief**, not an AI showcase board:

- It reads like a research report: conclusion first, evidence after; numbers can be checked and sources traced.
- Quiet: no gradients, no glow, no glassmorphism, no decorative icons and no exclamatory copy.
- Structured: hierarchy is built from hairlines, whitespace and type sizes, not from cards, shadows and colored badges.

**The only deliberate emphasis is the masthead's daily quote block** (large serif numerals + change + data source and time).
Everything else stays restrained.

---

## 2. Design Tokens

Defined in `app/src/styles/tokens.css`; components may only reference tokens and must not write new hex colors.

| Token | Value | Purpose |
|---|---|---|
| `--paper` | `#F6F6F3` | Page background |
| `--surface` | `#FFFFFF` | Table and panel background |
| `--ink` | `#17191B` | Headings and body text |
| `--ink-muted` | `#5C6166` | Secondary information (time, source, notes) |
| `--rule` | `#D9DAD4` | 1px dividers, table lines, grid lines |
| `--gold` | `#8A6A12` | The only accent color for the gold price and key numbers (white-background contrast ≈5.1:1) |
| `--up` | `#B4232A` | Up (red) |
| `--down` | `#16653C` | Down (green) |

Semantic color rules:

- The direction of a price move **must be conveyed by both** ▲▼ and "up/down" text; color only reinforces it and never carries the meaning alone.
- Red for up, green for down, matching Chinese investors' reading habits.

Hard constraints: no gradients, no shadows, no blur; border radius 0–2px; `backdrop-filter` is forbidden.

---

## 3. Fonts and Typography

- Headings and numerals: `Georgia, "Songti SC", "Noto Serif CJK SC", SimSun, serif`
- Body and UI: `-apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", Arial, sans-serif`
- All numerals use `font-variant-numeric: tabular-nums`; prices and percentage changes are right-aligned.
- Type sizes: 12 / 13 / 15 / 17 / 20 / 26 / 34; body line-height 1.75, heading line-height 1.25.
- Body line width ≤ 68ch; paragraphs are left-aligned and body text is not centered.
- Dates and times only display fields returned by the backend; never derive "today" locally (see Section 7 of `docs/ARCHITECTURE.md`).

---

## 4. Layout

- Page structure: masthead (wordmark + anchor navigation + data source and time) → seven sections (Market / Bullish vs Bearish / Institutions /
  Messages / Strategy / Quant Prediction / Conclusion) → footer (data sources, model notes, disclaimer).
- Maximum width 1180px, everything left-aligned; sections are separated by a single `--rule` hairline.
- One h2 per section, one h3 per panel inside a section; no numbering decoration such as 01/02/03.
- Narrow screens: multi-column layouts collapse to one column, tables scroll horizontally inside their container; minimum supported width 360px.

---

## 5. Components

| Component | Responsibility | Constraints |
|---|---|---|
| `Section` | Section container: anchor, title, one-line description, action area | Left-aligned title; a hairline along the top edge |
| `StateBlock` | Three states: loading / analyzing / unavailable | `role="status"`; when unavailable it must give the reason and the next step |
| `RefreshButton` | Manually trigger analysis or a crawl | Copy: "Re-analyze" / "Re-fetch" / "Fetch the latest messages", with the running label following the action ("Analyzing…" / "Fetching…"); the disabled state stays visible |
| `Quote` | Quote: name, value, change, source | Values in serif numerals; the change shows both ▲▼ and text |
| `FactorList` | Factor entries with expandable key points | Uses native `<details>`; keyboard-accessible |
| `InstitutionTable` | Institutional views table | Horizontal scroll on narrow screens; the header never scrolls out of view |
| `Messages` | Message board: tabs for the 24h / 7d / 30d windows, each entry expandable | Scores and ordering come entirely from the backend's deterministic scoring; the frontend never re-ranks or recomputes; overlapping windows are by design; original-article links open in a new window (`target="_blank"` + `rel="noreferrer noopener"`); when nothing is available it shows only "unavailable + reason" and never built-in messages |
| `StrategyColumns` | Three-tier strategy comparison | Stacks into a single column on narrow screens |
| `Quant` | Quant prediction: conclusion / fair-value decomposition / monitoring dashboard / backtest hit rate / four-category factor tables | Every factor must show its data as-of date and source; when unavailable, give the reason; fields that cannot be computed show "—" and are never filled with defaults |

**Block order on the quant prediction page (`Quant`)** (top to bottom, as of 2026-10-01):

1. Prediction conclusion — five horizon tabs (1 day / 1 week / 1 month / 1 quarter / 1 year); each horizon gives the direction (the calibrated expected-return
   drift, with exactly 0 recorded as "flat"), the upside probability, the base price and target price, three-scenario ranges with trigger / invalidation conditions, and per-factor contributions,
   plus a separate row "factor bias (uncalibrated)" = the composite score, for comparison only;
2. Fair-value decomposition — market price vs fair value, the four components (macro anchor / demand structure / risk premium / sentiment residual) and the fit R²;
3. Monitoring dashboard (weekly table) — each row gives the metric, frequency, source, latest value, change, data as-of, signal and rule description;
4. Backtest hit rate — this model (the calibrated drift direction) side by side with three benchmarks, with the uncalibrated factor bias on its own row,
   plus the actual coverage of the 80% nominal interval and the pre/post-2022 split;
5. Four categories of drivers — per-factor tables.

Rules specific to the quant page: any block that is unavailable only gives the reason and shows no numbers; bullish/bearish signals may only come from the deterministic
rules in the backend `backend/app/services/quant/monitor.py`, and the interface does not make its own judgement;
informational metrics (USDCNY, CNY gold price, COMEX open interest) only give values, not directions.
Scenario trigger / invalidation conditions must be verifiable against the factor table and the 200-day moving average; the interface does not compute a second set of numbers.

Message board (`Messages`) conventions: each of the three windows takes its own top 10, so the same
event may appear in several windows; the expanded area gives the summary, the scoring signals and
same-story links; the top meta line shows the last crawl time, and a manual crawl appends the fetch
report (sources ok / new items / failed sources). An empty window and an empty database are shown
separately: one sentence for an empty window, and a `StateBlock` with the backend reason and retry
path for an empty database.

---

## 6. UI Copy

**Banned words** (never appear in the interface):

`Agent`, `multi-agent`, `intelligence-driven`, `ReAct`, `RAG`, `deep learning`, `real-time scraping` (as a capability claim),
and "AI decoration" icons such as Sparkles / Bot / Brain, plus emoji such as 🚀✨🤖.

Rationale: the current implementation is a single-turn LLM call (see Section 3 of `docs/00-产品方向.md`); these words are either untrue or purely decorative.

**Glossary** (unified wording in the interface):

| Scenario | Wording |
|---|---|
| The two directions of an analysis result | Bullish factors / Bearish factors |
| Institutional price-target block | Institutional views |
| Strategy block | Investment strategy |
| Conclusion block | Market summary |
| Data cannot be fetched | Data unavailable (with the reason) |
| The backend has started analyzing | Analyzing (with a note that this is placeholder content) |
| Analysis generation time | Analysis time |
| Quote source | Data source |

**Byline**: annotate the bottom of every analysis block with
`Generated by {provider} {model} · Analysis time {generated_at} · For reference only`;
when the model name cannot be read, write "Model unknown (/health returned nothing)"; do not hard-code the model name.

**Footer**: the data-source column lists only real sources (Tencent Finance, Sina Finance, RSS news sources); the model column follows the byline rule above, and note
"Institutional views take each institution's most recent verifiable prediction and may be stale (the table shows the prediction date)"; keep the disclaimer.

**Bottom line**: do not fabricate data. When a data source is unavailable, prefer showing "data unavailable"; never use built-in constants, default values or
the model's impressions to generate concrete numbers such as institutional price targets, central-bank gold purchases or gold price levels (see Section 5 of `docs/00-产品方向.md`).

---

## 7. Motion, Accessibility and Print

- Motion is only used to respond to human action (e.g. refreshing), never auto-playing entrance animations; everything is disabled under `prefers-reduced-motion`.
- Semantic tags: `header` / `nav` / `main` / `footer`; one h1 per page; a skip link straight to the main content.
- Keyboard focus is visible (2px ink outline); interactive elements must be native elements such as `<button>` / `<a>` / `<details>`.
- Print: hide navigation and action buttons, remove background colors, avoid page breaks inside tables and chart blocks.
