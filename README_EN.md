<p align="center">
  <img src="docs\images\6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>An AI Data Analysis Engine for the International Gold Market</strong><br>
  <em>面向国际黄金市场的 AI 数据分析引擎</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0.0-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/released-2026--10--01-success?style=flat-square" alt="Release date">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/SQLite-zero--config--repro-003B57?style=flat-square&logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <a href="./README.md">中文</a> | <strong>English</strong>
</p>

---

<!-- ⬇️⬇️⬇️ 2.0 release banner: the next three lines are this release's "big type" block; update them together when changing versions ⬇️⬇️⬇️ -->

<h1 align="center">🎉 GoldMind 2.0 is here</h1>

<h2 align="center">GoldMind 2.0 已发布</h2>

<p align="center">
  <img src="https://img.shields.io/badge/release-v2.0.0-FFD700?style=for-the-badge" alt="v2.0.0">
  <img src="https://img.shields.io/badge/released-2026--10--01-2EA043?style=for-the-badge" alt="2026-10-01">
</p>

<p align="center">
  <strong>Every number on the page now comes from one calibrated distribution.</strong><br>
  <em>每一个数字都出自同一份经过校准的概率分布。</em><br><br>
  📋 <a href="./CHANGELOG.md">Changelog (中文)</a> ·
  🌍 <a href="./CHANGELOG_EN.md">Changelog (EN)</a> ·
  🚀 <a href="https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.0">GitHub Release v2.0.0</a>
</p>

<!-- ⬆️⬆️⬆️ End of the 2.0 release banner ⬆️⬆️⬆️ -->

---

## 🆕 What 2.0 Brings

2.0 is not a reskin — it fixes an old rule that would **silently swallow real data**, and converges
"prediction" from a set of numbers that each said their own thing into one backtestable, checkable
distribution that can state its own limitations.

| Change | Before | 2.0 |
|---|---|---|
| Institutional views | Only news "published within 24 hours" counted; on a day with no new research note, all four institutions turned into "none" | Each institution now gets its **most recent verifiable prediction** (with prediction date and source), with a configurable 30-day scan window; an empty result **never overwrites** an existing real record |
| Prediction convention | Direction, probability, target price and interval each computed their own way | Direction = sign(μ), probability = Φ(μ/σ), target price = base price×(1+μ), interval = μ±1.2816σ, three scenarios = quantiles of N(μ, σ²) — **all derived from one and the same distribution** |
| Interval width | Normal quantiles, systematically too narrow at long horizons | Calibrated to the **empirical quantiles of walk-forward prediction errors**; coverage shown side by side with "always long / momentum / coin flip" |
| Documentation | Mostly Chinese; the API reference was hand-written and had drifted from the implementation | Chinese and English **versions**; `docs/API.md` and `docs/en/api.md` are generated from the same route table, and drift turns the gate red directly |
| Verifiability | Data had no "as-of date" | Every factor carries a source and a data-as-of date; every prediction row carries a prediction date and a staleness in days, and when something cannot be fetched it says plainly "unavailable + reason" |

---

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-quant-strategy">Quant Strategy</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-common-commands">Common Commands</a> •
  <a href="#-directory-layout">Directory Layout</a> •
  <a href="#-documentation-map">Documentation Map</a> •
  <a href="#-honest-scope">Honest Scope</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## ⚡ Overview

**GoldMind** is a gold market analysis dashboard: it automatically collects the gold price and the
dollar index, uses a large language model to generate a bullish/bearish contrast, institutional
views, investment strategies and a market summary from recent news, and uses a quant engine to
predict, from four classes of drivers (monetary policy and rates / hedging and credit /
supply-demand structure / market and technicals), the direction, target price and scenarios over
1 / 5 / 20 / 60 / 250 trading days (intraday–1 week, 1–3 months, 6–18 months) — all from one
calibrated distribution, with the uncalibrated factor bias listed on its own row — presented as a
single-page **light research brief**: six sections (Market / Bullish vs Bearish / Institutional
Views / Investment Strategy / Quant Prediction / Conclusion), all left-aligned, with no gradients,
no shadows and no card grid; numbers live in tables, rising is red and falling is green, and the
direction always carries both a sign and a word. There is also a separate **research page** (`/research.html`): it lays out the pre-registered candidates × horizons evaluation, coverage and skill scores on the page, **including the conclusions that did not clear the line**.

The LLM provider is **not hardcoded**: any OpenAI-compatible endpoint (OpenAI / DeepSeek /
Qwen / Kimi / a local Ollama / Xiaomi MiMo …) works — just set `LLM_BASE_URL` /
`LLM_API_KEY` / `LLM_MODEL` in `backend/.env`, and every LLM client is constructed through
`backend/app/services/llm_provider.py`. When any one of the three is missing the project counts
as "unconfigured": each section honestly shows "temporarily unavailable" and no built-in
content is used as a fallback.

> You only need to: open the page
> GoldMind returns: today's gold price, the dollar index, and a bullish/bearish analysis and
> strategy suggestions generated from recent news, plus a backtestable quant prediction.

> 📌 Product boundaries and known limitations are in [`docs/00-产品方向.md`](docs/00-产品方向.md).
> **Capabilities marked "planned" in that document are not implemented yet — do not treat them as existing features.**

### 🧩 The Actual Analysis Chain

```
Market data ──► SQLite ──┐
RSS news ───► SQLite ────┼──► assemble prompt ──► llm.invoke() ──► parse JSON ──► cache ──► frontend dashboard
                        │
                        └──► (optional) plugin-style web_search (LLM_SEARCH_ENABLED, off by default)

Public data sources ──► factor store ──► rolling z-score ──► per-horizon weighted composite ──► one calibrated distribution ──► quant prediction
(Treasury / NY Fed / CFTC /                                                                     │
 Yahoo / RSS, all key-less)                                                                     └──► walk-forward backtest + coverage
```

| Analysis service | Input | Output |
|---|---|---|
| Bullish factors | Last 24h news + gold price | 5 bullish factors |
| Bearish factors | Last 24h news + gold price | 5 bearish factors |
| Institutional views | Last 30 days of news + (search) | The four institutions' most recent verifiable predictions (with date and source) |
| Investment advice | Market state + bullish/bearish factors + institutional views | Three strategy tiers: conservative / balanced / opportunity |
| Market summary | All of the above | Core logic, risks, overall judgement |

---

## 🌟 Our Vision

**GoldMind** is committed to building — through the joint effort of the community — a **genuinely usable AI Agent platform for international gold market data analysis and price prediction**.

Through technological innovation, we hope to:

- 📉 **Reduce information gaps** - let every investor access professional-grade market analysis
- 🛡️ **Strengthen risk resilience** - provide multi-dimensional risk assessment and early warnings
- 💡 **Practical investment advice** - give actionable investment strategies based on data and logic

> 🤝 **We look forward to your participation!** Whether it is code contributions, feature suggestions or usage feedback, it will become an important force in driving the project forward.

If this project has been helpful or inspiring to you, a ⭐ **Star** is the best affirmation we could ask for!

---

## 📸 System Showcase

### Masthead and Market
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/dashboard.jpeg" alt="Masthead and market" width="800">
</p>

### Trend and Key Data
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/price-chart.jpeg" alt="Price trend and key data" width="800">
</p>

### Bullish vs Bearish
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-up.jpeg" alt="Bullish factors" width="400">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-down.jpeg" alt="Bearish factors" width="400">
</p>

> The two sides fetch and refresh independently; one side failing does not affect the other.
> On the day the screenshot was taken the model returned only 2 bearish factors that had news
> support — the prompt explicitly says "give fewer rather than inventing any to fill a quota";
> when not a single one can be found the page honestly shows "temporarily unavailable", and
> "re-analyse" retries it. It never shows built-in copy.

### Institutional Views
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/institutional-views.jpeg" alt="Institutional views" width="800">
</p>

> Web search is off by default (`LLM_SEARCH_ENABLED=false`): it uses MiMo's plugin-style
> `web_search` tool, not a generic OpenAI capability, and the endpoint must have it enabled
> first, otherwise the call returns
> `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`
> (verified in practice; reproduce it with `backend/scripts/smoke_llm.py`). When it is off the
> section falls back to the news window, extracts each institution's **most recent verifiable**
> prediction, and lists under "prediction date" the date that prediction was last verified,
> labelling anything older than 30 days as "stale N days". "None" appears only when not a single
> one can be found, and **an empty target price never overwrites an existing real record in the
> database**.
> When the screenshot was taken the 30-day news window held no verifiable institutional target
> price, so all four institutions honestly show "no recent prediction".

### Investment Strategy
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/investment-advice.jpeg" alt="Investment strategy" width="800">
</p>

> The three tiers come from one LLM call, and the output budget is controlled by
> `LLM_MAX_TOKENS` (default 8192). A budget that is too small truncates this large JSON and
> parsing fails — the page then honestly shows "temporarily unavailable" rather than a built-in
> strategy; when parsing fails the backend log records `finish_reason` and token usage for the
> next investigation.

### Quant Prediction
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/quant-prediction.jpeg" alt="Quant prediction: direction, probability and scenarios across five horizons" width="800">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/quant-fair-value.jpeg" alt="Fair value decomposition" width="800">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/quant-monitor.jpeg" alt="Monitor dashboard (weekly table)" width="800">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/quant-accuracy.jpeg" alt="Backtest hit rate against benchmarks" width="800">
</p>

> The quant engine calls no LLM: all 14 factors come from free public data sources. A factor or
> indicator that cannot be fetched is labelled "unavailable" with its reason, and fewer than three
> usable factors means "prediction unavailable" outright. When the screenshot was taken 12/14
> factors were usable; direction, probability, target price and the three scenarios all derive from
> the same calibrated distribution (see "Quant Strategy").

### Conclusion
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/market-summary.jpeg" alt="Market summary" width="800">
</p>

---

## 📐 Quant Strategy

This section explains **how "the four classes of factors that affect the international gold price" become the numbers on the page**, and **where those numbers go wrong**. The factor list, weights, direction priors and freshness caps are defined in one place only, `backend/app/services/quant/definitions.py`, and this section does not copy a second version — if the numbers here disagree with the code, the code wins.

### 1. Four Layers of Drivers and 14 Factors

The framework is a four-layer classification of "the main factors that affect the international gold price":

| Layer | Real-world counterpart | Factors | The question this layer answers |
|---|---|---|---|
| Monetary policy and rates | Real rates, policy path, the dollar | 4 | Is the opportunity cost of holding gold rising or falling? |
| Hedging and credit | Volatility, credit stress, geopolitical conflict | 3 | What is the market afraid of? Where is money hiding? |
| Supply-demand structure | Central-bank gold buying, speculative positioning, ETF creation/redemption | 3 | Who is actually buying, and how much? |
| Market and technicals | Momentum, seasonality, substitutes, risk appetite | 4 | What does price's own inertia say? |

Full definitions of the 14 factors (direction prior `+1` = the factor rising is bullish for gold, `-1` = rising is bearish):

| Factor | Layer | Unit | Source | Prior | Weights 1d/1w/1m/1q/1y | Freshness cap |
|---|---|---|---|---|---|---|
| 10-year US real yield | Monetary policy and rates | % | US Treasury (TIPS real yield curve) | −1 | 0.25 / 0.5 / 1.0 / 1.0 / 0.8 | 7 days |
| Market-implied policy expectations | Monetary policy and rates | % | US Treasury (2-year) − New York Fed (EFFR) | −1 | 0.2 / 0.4 / 1.0 / 0.8 / 0.6 | 7 days |
| 10-year inflation expectations | Monetary policy and rates | % | US Treasury (nominal − real yield) | +1 | 0.1 / 0.2 / 0.5 / 0.5 / 0.4 | 7 days |
| Dollar index | Monetary policy and rates | points | Yahoo Finance (DX-Y.NYB) | −1 | 0.3 / 0.5 / 0.9 / 0.7 / 0.5 | 7 days |
| VIX volatility index | Hedging and credit | points | Yahoo Finance (^VIX) | +1 | 0.6 / 0.5 / 0.4 / 0.3 / 0.2 | 7 days |
| Credit-market risk appetite | Hedging and credit | % (20-day) | Yahoo Finance (HYG/IEF ratio) | −1 | 0.5 / 0.4 / 0.3 / 0.2 / 0.2 | 7 days |
| Geopolitical risk intensity | Hedging and credit | % (share of news) | This system's RSS corpus (keyword-intensity proxy) | +1 | 0.5 / 0.5 / 0.4 / 0.3 / 0.3 | 3 days |
| Central-bank gold buying (China official reserves) | Supply-demand structure | 10k oz | Sina Finance macro data (PBoC official reserve assets) | +1 | 0.2 / 0.4 / 0.7 / 1.0 / 1.0 | 62 days |
| COMEX speculative net long | Supply-demand structure | contracts | CFTC Commitments of Traders (contract code 088691) | +1 | 0.8 / 0.7 / 0.4 / 0.3 / 0.2 | 14 days |
| Gold ETF shares (GLD) | Supply-demand structure | shares | Yahoo Finance (accumulated since collection began) | +1 | 0.3 / 0.4 / 0.5 / 0.7 / 0.8 | 7 days |
| Gold trend momentum | Market and technicals | % (60-day) | Yahoo Finance (GC=F close) | +1 | 1.0 / 1.0 / 0.4 / 0.3 / 0.2 | 7 days |
| Seasonality (historical average for the current month) | Market and technicals | % (historical average) | Own price series (same month in previous years only) | +1 | 0.2 / 0.3 / 0.2 / 0.2 / 0.2 | 7 days |
| Bitcoin (digital-gold narrative) | Market and technicals | points | Yahoo Finance (BTC-USD) | −1 | 0.2 / 0.2 / 0.2 / 0.2 / 0.3 | 7 days |
| Equity risk appetite | Market and technicals | points | Yahoo Finance (SPY) | −1 | 0.5 / 0.4 / 0.3 / 0.2 / 0.2 | 7 days |

Direction priors come from economic reasoning and **are not guaranteed to hold** — the backtest reports each factor's standalone hit rate and IC, and when a direction runs opposite to reality the page still shows it as it is.

### 2. Five Horizons and Their "Dominant Layers"

The first step of the methodology is to **pick the time horizon first, then the variables** — the same factors carry different weights at different horizons:

| Horizon | Label | Real-world period | Dominant layer | Notes |
|---|---|---|---|---|
| 1 trading day | 1 day | intraday–1 week | Market and technicals → supply-demand structure | Flows, technicals and positioning crowding dominate; macro fundamentals carry the least weight |
| 5 trading days | 1 week | intraday–1 week | Market and technicals → hedging and credit | One week of flows and event pulses dominates; macro is still second |
| 20 trading days | 1 month | 1–3 months | Monetary policy and rates → supply-demand structure | Policy expectations, economic data and the dollar dominate |
| 60 trading days | 1 quarter | 1–3 months | Monetary policy and rates → supply-demand structure | Policy path and demand structure carry equal weight |
| 250 trading days | 1 year | 6–18 months | Supply-demand structure → monetary policy and rates | The real-rate cycle, the rate-cut path and the central-bank buying trend dominate |

This is also why each of the 14 factors carries a five-dimensional weight vector rather than one global weight — using "central-bank gold buying" to explain tomorrow's gold price, or "VIX" to explain next year's, both get the horizon backwards.

### 3. One Calibrated Distribution, From Which Every Output Derives

The factor-composite `score` is an **uncalibrated** input — it appears only in the factor table and the "factor bias (uncalibrated)" row. Every conclusion on the page comes from the same exit, `engine.build_prediction_frame`:

```
μ    = α + β · score              Expanding-window OLS; sample pairs satisfy s + h ≤ t
σ    = std(r_s − μ_s | s+h ≤ t) × q80( |r_s − μ_s| / (1.2816 · σ_s) )
                                  Standard deviation of the walk-forward prediction error, then the
                                  width is calibrated to the error's empirical quantile
p_up = Φ(μ / σ)                   Upside probability
Target price = base price × (1 + μ)   Base price = COMEX front-month futures daily close (gold_close)
80% interval = μ ± 1.2816σ
Three scenarios = quantiles of N(μ, σ²)   Base [q25, q75] / Bull top 25% / Bear bottom 25%
Direction = sign(μ)               Exactly 0 is recorded as "flat"
```

Model version **`quant-v4`**. Four hard conventions:

1. **No look-ahead.** Rolling statistics and regression samples are all `shift`ed to before t; data sources published only after the gold close (the Treasury yield curve, the New York Fed EFFR, CFTC positioning) are shifted wholesale by one business day. Guard: `backend/tests/unit/quant/test_no_lookahead.py` — turn the data after t into garbage values, and the signal at t must remain bit-for-bit identical.
2. **No falling back to "expected unchanged".** When a horizon has fewer than 60 regression samples, the whole horizon returns "unavailable + reason"; it does not substitute the sign of the score for the direction, nor pretend μ = 0. When there are fewer than 60 realised errors, σ falls back to the "expanding standard deviation of realised h-day returns", still using past data only.
3. **Missing factors are renormalised over the remaining weights**, not treated as 0; fewer than 3 usable factors means the "prediction is unavailable" outright.
4. **Time flows in one time zone only** (`app.utils.timeutil`, default `Asia/Shanghai`).

### 4. The Four-Layer Decomposition of Fair Value

`decompose.py` uses walk-forward expanding-window OLS:

```
log gold price ~ real rate + log dollar index + log central bank reserves + VIX
```

to split the gold price into **macro anchor + demand premium + risk premium + sentiment residual**. The display convention is written in one place only, `decompose.py`: the demand and risk premiums multiply in a chain (the risk premium takes "anchor + demand premium" as its base), so that both "anchor + demand premium + risk premium = fair value" and "the three blocks + sentiment residual = market price" hold by construction. The regression coefficients at time t use only realised samples with `s ≤ t−1`; when fewer than 120 samples exist or any regressor is missing, it returns "unavailable + reason". Deviation = market price / fair value − 1.

> With this, "is it expensive right now" stops being a feeling — it becomes "the market price is so many percentage points above or below the model's fair value, and of that, how much comes from demand, how much from risk, and how much is sentiment".

### 5. Trigger and Invalidation Conditions of the Scenarios

The three scenarios are not written off the top of anyone's head: Base takes the middle 50% of the distribution (q25–q75), Bull and Bear take the top and bottom 25% each, so the three probabilities always sum to 100%. Each scenario also carries **trigger conditions** and **invalidation conditions** — generated from that horizon's **heaviest factor** and the **200-day moving average**, they are sentences you can check line by line on the page, not adjectives. When σ is non-positive, the base price is missing or no factors are usable, it returns "unavailable + reason" without blocking the main prediction output.

### 6. Backtest Conventions and the Three Benchmarks

The backtest (`backtest.py`) is **walk-forward**: every historical point uses only the data available at that time, it scores the **calibrated direction** (`sign(μ)`), and it is always shown side by side with three benchmarks:

| Benchmark | Meaning |
|---|---|
| Always long | Ignores every signal and guesses up every day |
| Momentum | Extrapolates the recent trend |
| Coin flip | 50% |

Three more items are listed separately: the record of the **uncalibrated score direction** (`metrics.score_direction_accuracy`, which answers "does calibration actually add anything"), the **actual coverage of the nominal 80% interval** (`metrics.interval_coverage_80`), and the **per-segment results** split at 2022-01-01 (`metrics.regimes`); per-factor hit rate and IC are also listed one by one, and when a segment has too few samples it gives only the sample count and the reason — no padding the numbers.

**Measured coverage and hit rates (recomputed 2026-10-02, same source as the page):**

| Horizon | 1 day | 1 week | 1 month | 1 quarter | 1 year |
|---|---|---|---|---|---|
| Holdout (from 2023-10-02) direction hit rate | 56.3% | 62.2% | 68.2% | 83.3% | 100% |
| Holdout "always long" | 56.3% | 62.2% | 68.2% | 83.3% | 100% |
| Development-period direction hit rate | 52.2% | 54.0% | 53.5% | 57.5% | 63.1% |
| Holdout actual coverage of the 80% interval | 78.9% | 77.6% | 73.2% | 61.2% | 24.1% |

The nominal value is 80%. **The 1-year coverage is still below the plan's ≥70% acceptance line (24.1%)** and heads the next round's agenda — see Section 10, "Known limitations". In the holdout the model's direction matches "always long" day by day (+0.0pp; gold trended up one way after 2023-10): this round did not swap the model for a new version that has no evidence behind it. The verdict process is in Section 7.

### 7. Research Bench and Pre-registration: Improvements Must Clear the Holdout First

"The backtest looks good" is not evidence — pick parameters repeatedly on the same data and you will always find a pretty curve. So every improvement is **registered first and tested second**: the candidate list, the selection rules and the pass lines are frozen before the experiment starts (`docs/specs/2026-10-02-量化策略提升路线图.md`, section 6.1; the rules live in one place, `backend/app/services/quant/preregistered.py`). The experiment tool is `backend/scripts/quant_lab.py`, and the page is the "Research" page (`app/research.html` ← `GET /api/gold/quant/research`).

**Verdict on 2026-10-02: 17 candidates × 5 horizons, not one passed.**

| Candidate family | Count | Holdout result |
|---|---|---|
| Baseline B0 (the live convention) | 1 | Ties "always long" (+0.0pp); Brier skill score negative |
| Drift trio D1 / D3 / D5 | 3 | None passed |
| Compositing quartet S1–S4 | 4 | None passed |
| Distribution quartet P1–P4 | 4 | Wider intervals raise coverage (P3 normal, 100%) but do not improve direction or Brier skill |
| Factor-set quartet F1–F4 | 4 | None passed |
| Ensemble E0 | 1 | None passed |

By the pre-registered rules we **keep `quant-v4`** and label it "no statistical edge" on the research page and in the bench output. The full results (per-horizon numbers and failure reasons for every candidate) are in `docs/specs/2026-10-02-研究台报告.md`; reproduce with `python scripts/quant_lab.py` (about 0.0s from cache, about 6s for a full recompute).

> The honest conclusion of this round: the real gain is that **the evaluation is now trustworthy** — complete data (a 20-year backfill), one significance toolkit (HAC / DM / Brier skill / block bootstrap), reproducible conclusions — not a replacement model with no evidence behind it. Next round's candidates must be pre-registered again (write the list, then look at the holdout).

### 8. Monitoring Dashboard: The 16-Row Gauge

`monitor.py` covers **16 rows** of metrics; each row gives frequency, source, current value, signal (bullish / bearish / neutral / info) and data-as-of date. The signal rules are deterministic thresholds, centralised in `_rule` in one place; FX rates, the CNY gold price and open interest are **informational** indicators (`signal = null`) and are not forced into bull/bear; rows with no data or too little history honestly return "unavailable + reason".

Each row's update frequency follows its own data source (daily / weekly / monthly), not a uniform refresh:

| Frequency | Indicators |
|---|---|
| Daily | 10-year US real yield, breakeven inflation, dollar index (DXY), market-implied policy expectations, GLD shares, Shanghai gold premium, VIX, credit preference (HYG/IEF), gold price vs 200-day moving average, USDCNY, CNY gold price reference, US Treasury TGA balance, New York Fed RRP |
| Weekly | CFTC net long (crowding), COMEX gold open interest |
| Monthly | Central-bank gold reserves |

> The dashboard is a "gauge for you to read", not a scoring item — five of its series, `usdcny` / `cny_gold` / `tga` / `rrp` / `cftc_oi`, are stored in the same table as the factors but **do not participate** in signal composition.

### 9. Data Sources and Freshness

- **All free, no keys required**: the US Treasury yield curve and Fiscal Data (TGA), the New York Fed RRP and EFFR, CFTC Commitments of Traders, Yahoo Finance (DXY / GC=F / GLD / SPY / BTC-USD / ^VIX / HYG / IEF / CNY=X), Sina Finance (PBoC official reserves), and this system's own RSS corpus.
- **Throttled per source**: the syncer gives each source its own 6h–24h throttle window and fetches incrementally; one source failing does not affect the others, and the failure reason goes into the sync report and is shown on the page.
- **A freshness cap per factor** (last column of the table above): the 7-day cap for daily factors covers long holidays, and the 62-day cap for monthly ones covers publication delays. A factor past its cap is marked "**stale**" and excluded from the composite, instead of padding with the old value.
- **The first backfill covers 10 years**, after which only increments are fetched; `factor_observations` has a unique constraint on `(factor_key, obs_date)`, so repeated fetches are idempotent.

### 10. Known Limitations (Stated Here Without Varnish)

1. **The 1-year horizon's drift term is systematically low.** The holdout starting 2023-10 is a one-way gold rally: μ systematically underestimated the gains, and the actual coverage of the 250-day 80% interval is down to **24.1%**, while widening the interval cannot repair a directional bias. This is the number-one target for the next round (none of this round's 17 candidates cleared the pre-registered line). The page shows coverage side by side with "always long / momentum", leaving the judgement to you.
2. **The Shanghai gold premium is unavailable.** The Shanghai Gold Exchange's AU9999 has no public key-less API and cannot be fetched in practice; the row honestly shows "unavailable + reason" and does not invent numbers.
3. **Web search is off by default.** It uses MiMo's plugin-style `web_search` tool, not a generic OpenAI capability; when the endpoint has not enabled it, it returns
   `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false` (reproducible in practice). To enable it: `LLM_SEARCH_ENABLED=true` with the plugin enabled on the endpoint side; while it is off, institutional views fall back to the RSS news window and make no pointless requests.
4. **Geopolitical risk intensity is a corpus proxy metric** (the share of related reports in recent news), not the official GPR index.
5. **No auth, no multi-tenancy.** All endpoints are publicly accessible, including `POST .../refresh`, which triggers paid LLM calls.
6. **No informational edge in the holdout direction.** Over the holdout starting 2023-10-02, all five horizons match "always long" day by day (+0.0pp) and the Brier skill score is negative — see the pre-registered verdict in Section 7 and `docs/specs/2026-10-02-研究台报告.md`.
7. **It is not a trading system.** It does not place orders, does not connect to brokers and does not custody funds; all output carries a disclaimer.
---

## 🚀 Quick Start

### Prerequisites

| Tool | Version required | Purpose | Install check |
|------|----------|------|----------|
| Node.js | ≥22.22.2 (or 24.15+/26+) | Frontend runtime, includes npm. The floor comes from the strictest dependency in the lockfile (jsdom `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0`); Node 22.2.0 still runs, but Vite prints a version warning | `node -v` |
| Python | 3.11 - 3.12 | Backend runtime | `python --version` |
| SQLite | Built into Python | Data storage: a single file, `backend/goldmind.db` — **zero install, zero configuration** | No check needed |
| Google Chrome | Any recent version | The frontend end-to-end tests reuse the Chrome already installed on the machine and do **not** download Playwright's bundled browser | Open Chrome → `chrome://version` |

### Local Development (the documented path: SQLite, zero configuration)

#### 1. Configure Environment Variables

```bash
# Copy the example configuration file
cd backend
cp .env.example .env

# Edit the .env file and fill in the required API keys
```

**Required environment variables:**

```bash
# ============================================
# Database configuration (SQLite by default — nothing to install)
# ============================================
# Leave DATABASE_URL unset = use backend/goldmind.db (a single-file SQLite database);
# no database server to install.
# This one is the **single source of truth**: the backend application, init_db.py,
# seed_data.py and scripts/*.py all read it from here.
# Override it explicitly only when you want MySQL (optional; not exercised in this repository):
# DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/gold_analysis

# ============================================
# LLM access (any OpenAI-compatible endpoint; all three must be set)
# ============================================
# No provider is hardcoded — switching to any of these (or self-hosted / local Ollama)
# only changes these three lines:
#   OpenAI        LLM_BASE_URL=https://api.openai.com/v1
#                 LLM_MODEL=gpt-4o-mini
#   DeepSeek      LLM_BASE_URL=https://api.deepseek.com/v1
#                 LLM_MODEL=deepseek-chat
#   Qwen          LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
#                 LLM_MODEL=qwen-plus
#   Kimi          LLM_BASE_URL=https://api.moonshot.cn/v1
#                 LLM_MODEL=moonshot-v1-8k
#   Ollama (local) LLM_BASE_URL=http://localhost:11434/v1
#                 LLM_MODEL=qwen2.5:14b
#   Xiaomi MiMo    LLM_BASE_URL=https://api.xiaomimimo.com/v1
#                 LLM_MODEL=mimo-v2.6-flash
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
# Display-only provider label shown in the UI footer; may be left empty
LLM_PROVIDER=
```

**Optional environment variables** (full list in [`backend/.env.example`](backend/.env.example)):

| Variable | Default | Effect |
|---|---|---|
| `INSTITUTION_NEWS_LOOKBACK_DAYS` | `30` | Window (days) in which institutional views scan the news. Within the window it takes each institution's **most recent verifiable** prediction, which may be the older item |
| `DEBUG` | `false` | Only affects uvicorn's `--reload`; set it to `true` in `.env` for local hot reload |
| `LOG_LEVEL` | `INFO` | Log level |
| `CACHE_DIR` | `backend/cache` | On-disk directory for the file half of the two-level cache |
| `NEWS_RSS_SOURCES` | Built-in defaults | Format: `name\|URL,name\|URL` |
| `LLM_MAX_TOKENS` | `8192` | Per-call output token cap; the reasoning model's thinking and its answer share this budget. Too small and a large JSON such as the three strategy tiers is truncated and fails to parse |
| `LLM_SEARCH_ENABLED` | `false` | Whether to enable the plugin-style web search (MiMo `web_search`); the endpoint must have it enabled first |
| `LLM_SEARCH_MODEL` / `LLM_SEARCH_BASE_URL` / `LLM_SEARCH_API_KEY` | follows the reasoning config | Fill in only when search uses a separate model / endpoint / key |
| `LLM_TRUST_ENV` | `false` | Whether httpx reads the host's proxy environment variables; set to `true` when reaching the LLM endpoint through a proxy |
| `GOLDMIND_TEST_DATABASE_URL` | Unset | Test runs only: run the same suite against a different database (in-memory SQLite by default; only needed when you really want to verify MySQL) |
| `SCHEDULER_TIMEZONE` | `Asia/Shanghai` | **The project's only time-zone convention**; scheduled tasks and "today" are all computed in it |

#### 2. Install Dependencies

**Backend dependencies:**

```bash
cd backend

# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Versions are pinned** (`==`, not `>=`), pinned to the versions the tests actually ran against.
> A loose range means `pip install` can pull a new major version with breaking changes at any time,
> and the problem only surfaces at deployment. The frontend is the same — `package-lock.json` is
> committed, so use `npm ci`, not `npm install`.

**Frontend dependencies:**

```bash
cd app

# Install dependencies (use ci, not install: strictly follow the lockfile, reproducible)
npm ci
```

#### 3. Initialise the Database (SQLite, zero configuration)

```bash
cd backend

# Create the tables and seed historical data from 2025 to today (needs network access to public data sources)
python init_db.py

# Create the tables only, no fetching: takes seconds and works offline
SKIP_SEED=1 python init_db.py
```

**About data initialisation:**

`init_db.py` automatically does the following:
1. Creates the SQLite file `backend/goldmind.db` (if missing) and all table structures
2. **Automatically fetches and seeds historical data** (1 January 2025 to today)
   - Gold price data: open, high, low, close
   - Dollar index data: open, high, low, close

**Data source priority (domestic first):**
- Gold data: Sina Finance → Eastmoney → Yahoo Finance
- Dollar index: Eastmoney → Yahoo Finance

> 💡 **Tip**: the script tries multiple data sources automatically, so that users in mainland China can fetch data successfully too. If every source fails, you can run `python seed_data.py` later to retry.

**Skip data seeding (create the table structures only):**
```bash
SKIP_SEED=1 python init_db.py
```

**Seed data manually:**
```bash
# If seeding was skipped during initialisation, or you need to update the data
python seed_data.py
```

**Upgrading an old database** (the database already exists and you are moving it to 2.0):

```bash
cd backend

# Institutional views: add the as_of_date / source columns and copy real predictions from the old
# alias rows into the canonical rows (add-only, never delete)
python scripts/migrate_institution_views.py --dry-run   # dry-run is the default; see what it would do first
python scripts/migrate_institution_views.py --apply
# Roll back (drop the two columns; existing data rows are untouched)
python scripts/migrate_institution_views.py --drop-columns --yes

# Quant factor engine: upgrade to the structure with factor_observations / model_evaluations
# (idempotent, add-only)
python scripts/migrate_quant.py --dry-run
python scripts/migrate_quant.py
```

#### 4. Start the Services

Frontend and backend each take one terminal — the repository has **no** `start_all.ps1`
one-click script:

```bash
# Terminal 1: backend (in the backend directory)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: frontend (in the app directory)
npm run dev
```

> You can also skip the second terminal and start only the frontend: when the backend is not
> running the page honestly reports "API unavailable" and shows no built-in numbers.

**What to expect on a cold start (the first time you open the page):**

- The five analysis sections **will not have content immediately**: with no cache they return an
  empty result first and run one analysis in the background (the page says "AI analysis in
  progress; the first load may take 1-2 minutes") and it appears once done; you can also click
  each section's "re-analyse / re-fetch" to trigger it manually.
- The quant prediction needs a multi-year factor backfill on first run; it only turns from
  "unavailable" into numbers after fetching finishes, and is incremental afterwards.
- The page polls the market endpoint every 10 seconds; the default rate limit is 60 requests
  per minute (6 per minute for LLM endpoints), which normal browsing will not hit.

**Service addresses:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### Optional: MySQL / Docker (not exercised in this repository)

This README's quick start, gate commands and CI **run on SQLite only** — that is the only reproduction path the repository actually tests. Two optional MySQL / container assets are kept for people who really need them, but they are **not guaranteed to work out of the box in the current version**:

- `docker-compose.yml` + `backend/schema.sql`: a three-container setup (mysql / backend / frontend). On first start MySQL creates the tables from `schema.sql`, and compose injects the backend container's `DATABASE_URL`.
- Using a local MySQL: write
  `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/gold_analysis` in `backend/.env`,
  then run `python init_db.py` (the MySQL path creates the database first and then executes `schema.sql`).

> ⚠️ Neither path has been through the same gate as this round's SQLite default, and the behavioural differences (ENUM storage, case-insensitive string comparison, transaction semantics) are known. Before relying on them, run
> `GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" python -m pytest`
> to confirm the baseline.
---

## 🧪 Common Commands

**The single source of truth for the gate commands.** After changing code they must all run green (the rules are in [`AGENTS.md`](AGENTS.md)).

### Backend

```bash
cd backend

# Install dependencies (first time)
pip install -r requirements.txt -r requirements-dev.txt

# Configuration self-check (read-only: no DB, no network; failures come with fix commands, exit 0/1)
python scripts/verify_setup.py

# Tests — the full gate
python -m pytest

# Run one layer at a time
python -m pytest tests/unit          # unit: no database or network
python -m pytest tests/integration   # integration: in-memory SQLite + fake LLM
python -m pytest tests/e2e           # end-to-end: the whole chain in real usage order

# Optional: run the same suite under the MySQL dialect (**only when you really want to verify
# MySQL**; SQLite is the default and the CI convention). The two differ on enum storage, JSON
# columns and case-insensitive string comparison. It must point at a **separate test database**:
# the suite truncates every table.
GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" \
    python -m pytest

# Static check: compile everything
python -m compileall -q app

# Whether the API docs (Chinese and English) agree with the route table
python scripts/gen_api_doc.py --check     # exit code 1 when out of sync
python scripts/gen_api_doc.py             # regenerate docs/API.md and docs/en/api.md

# Database initialisation (SQLite: create tables + seed history; the file is created automatically)
python init_db.py
SKIP_SEED=1 python init_db.py        # create the tables only, no seeding (works offline)

# Repair enum values in an old database (idempotent; only affects databases created by early
# versions of schema.sql)
python scripts/fix_enum_columns.py --dry-run
python scripts/fix_enum_columns.py

# Institutional views: add as_of_date / source and copy real predictions into the canonical rows
# (idempotent; **never deletes any row**)
python scripts/migrate_institution_views.py --dry-run
python scripts/migrate_institution_views.py --apply
# Roll back (drop the two columns; existing data rows are untouched)
python scripts/migrate_institution_views.py --drop-columns --yes

# Quant factor engine: upgrade an old database to the structure with factor_observations /
# model_evaluations (idempotent, add-only)
python scripts/migrate_quant.py --dry-run    # see what it would do first
python scripts/migrate_quant.py
# Roll back (drop the two new tables and the quant columns of predictions; existing data untouched)
python scripts/migrate_quant.py --drop --yes

# Run one round of factor fetching manually (first run backfills 10 years; increments after that)
python -c "from app.database import SessionLocal; from app.services.quant.sync import run_sync; db=SessionLocal(); print(run_sync(db, force=True).to_dict()); db.close()"

# Quant research bench: full evaluation of pre-registered candidates × horizons (reads the
# cache by default; --refresh recomputes everything)
python scripts/quant_lab.py
python scripts/quant_lab.py --refresh
```

### Frontend

```bash
cd app

# Install dependencies
npm ci

# Build + type check — the full gate
npm run build

# Static check
npm run lint

# Unit + integration tests (vitest + Testing Library)
npm test

# Browser end-to-end tests (Playwright) — requires npm run build first
npm run test:e2e

# Local development
npm run dev
```

### Browser End-to-End Tests

`npm run test:e2e` really brings up three services and then visits them with a real browser:

1. A fake LLM service (`backend/scripts/dev_mock_llm.py`, OpenAI-protocol compatible, consumes no quota)
2. The real backend (uvicorn + SQLite, with data prepared by `backend/scripts/dev_seed_sqlite.py`)
3. The build output (`vite preview`, proxying `/api` through to the backend)

It reuses the Chrome already installed on the machine and does **not** download Playwright's bundled browser. If your Python is not on `PATH`, point `E2E_PYTHON` at the interpreter:

```powershell
$env:E2E_PYTHON = "path\to\python.exe"
cd app
npm run build
npm run test:e2e
```

> The end-to-end tests use a separate database and cache directory (`backend/e2e.db`, `backend/e2e-cache/`) and will not touch your development data; both are already ignored by `.gitignore`.

### End-to-End Smoke Test (Real LLM Calls)

```bash
cd backend
python scripts/smoke_llm.py
```

> ⚠️ Requires `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` to be configured in `backend/.env`,
> and it really consumes quota. The script first probes authentication, `max_tokens` and
> Chinese JSON output; the web-search probe only runs when `LLM_SEARCH_ENABLED=true`
> (skipped by default). Results are written to `backend/scripts/smoke_llm_result.json`
> (already ignored by `.gitignore`).

### Continuous Integration (GitHub Actions)

The default branch only accepts green merges: `.github/workflows/ci.yml` runs three
parallel jobs on every PR and every push to `main`, using exactly the gate commands
listed above —

| Job | What it runs | Environment |
|---|---|---|
| `Backend (pytest)` | `python -m pytest` | Python 3.11 + in-memory SQLite (MySQL is not needed) |
| `Frontend (lint + test + build)` | `npm run lint` / `npm test` / `npm run build` | Node 22 |
| `Browser E2E (Playwright)` | `npm run test:e2e` | Python 3.11 + Node 22 + Chromium + mock LLM |

In CI the browser end-to-end job passes `E2E_BROWSER=chromium` to
`app/playwright.config.ts` and installs the browser with
`npx playwright install --with-deps chromium`; locally the variable is left unset
and the already-installed Chrome is reused.

Dependency updates are handled by `.github/dependabot.yml`: pip / npm / github-actions
each open a small number of PRs every week, and **nothing is auto-merged** — every PR
still has to pass the three jobs above, and a human decides when to merge.

> Branch protection (required checks, mandatory PRs) is a GitHub repository setting,
> not version-controlled code, so it must be enabled manually under
> Settings → Branches. Once the workflow has completed successfully at least once,
> mark the three checks as required.

### Troubleshooting

- **httpx reports `Invalid port: ':1]'` or `Missing dependencies for SOCKS support`** — the machine has a system proxy set (`ALL_PROXY` / `HTTP_PROXY` etc.), or `NO_PROXY` contains `[::1]`, and httpx cannot parse those values. Clear them before running tests:

  ```powershell
  $env:ALL_PROXY=''; $env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:NO_PROXY=''
  ```

- **Tests report `no such table`** — the tests use in-memory SQLite, so this should not happen; if it does, check whether the fixtures in `backend/tests/conftest.py` were bypassed.
---

## 🗂️ Directory Layout

```
GoldMind/
├── app/                          # Frontend (React 19 + TypeScript + Tailwind)
│   ├── src/
│   │   ├── sections/            # Six page sections + their tests
│   │   ├── research/            # The "Research" page: the full pre-registered evaluation
│   │   ├── components/          # Reusable components (including the prediction-date column of institutional views)
│   │   ├── layout/              # Masthead / footer
│   │   ├── services/            # API client and type definitions (api.ts)
│   │   └── test/                # Test fixtures
│   └── package.json
├── backend/                      # Backend (FastAPI + SQLAlchemy; a single SQLite file by default)
│   ├── app/
│   │   ├── services/            # Business logic
│   │   │   ├── llm_provider.py                     # **The only entry point for LLM calls**
│   │   │   ├── institution_prediction_service.py   # Institutional views (including the institution registry)
│   │   │   └── quant/                              # Quant engine: sources / derive / storage /
│   │   │                                           #   sync / engine / decompose / scenarios /
│   │   │                                           #   backtest / monitor / service /
│   │   │                                           #   stats / preregistered
│   │   ├── routers/             # API routes
│   │   ├── models/ schemas/     # Data models and response contracts
│   │   ├── tasks/ scheduler.py  # Scheduled tasks (including the single time-zone convention)
│   │   └── utils/timeutil.py    # **The only source of "now" and "today"**
│   ├── scripts/                 # Migration scripts, doc generator, smoke and dev tools
│   ├── tests/                   # unit / integration / e2e
│   ├── schema.sql               # MySQL (optional path) DDL; SQLite uses the models' create_all
│   ├── goldmind.db              # Default SQLite database (created at runtime, gitignored)
│   └── requirements*.txt
├── docs/                         # Chinese documentation
│   ├── en/                      # English mirrors (one-to-one with the Chinese versions)
│   ├── specs/                   # Specs and plans for each round of changes (process records)
│   ├── 00-产品方向.md · 10-密钥与隐私.md · 20-前端设计规范.md
│   ├── ARCHITECTURE.md · API.md
│   └── images/screenshots/
├── .github/
│   ├── workflows/ci.yml          # CI gates: backend / frontend / browser E2E
│   └── dependabot.yml            # Dependency update bot
├── AGENTS.md                     # How to work: rules, gates, process
├── CHANGELOG.md / CHANGELOG_EN.md
├── CONTRIBUTING.md / CONTRIBUTING_EN.md
├── README.md / README_EN.md
└── docker-compose.yml            # Optional path (not exercised in this repository)
```

---

## 🗺️ Documentation Map

The single mapping table for "changing what → read which file". The Chinese and English versions mirror each other: Chinese is the authoritative version, and English is the same content.

| Document | English | What it covers | When to read it |
|---|---|---|---|
| [`AGENTS.md`](AGENTS.md) | — (stays Chinese) | How to work: rules, gates, process | Must-read before starting work |
| [`docs/00-产品方向.md`](docs/00-产品方向.md) | [`docs/en/product-direction.md`](docs/en/product-direction.md) | What the product should do; **current vs planned** | Before changing requirements or adding features |
| [`README.md`](README.md) | [`README_EN.md`](README_EN.md) | Directories, commands, configuration (this file) | When looking for a command / config |
| [`docs/10-密钥与隐私.md`](docs/10-密钥与隐私.md) | [`docs/en/secrets-and-privacy.md`](docs/en/secrets-and-privacy.md) | Secret rules and the handling of the historical leak | Before touching configuration / secrets |
| [`docs/20-前端设计规范.md`](docs/20-前端设计规范.md) | [`docs/en/frontend-design.md`](docs/en/frontend-design.md) | Frontend visual language: tokens, typography, components, UI copy rules | Before changing the frontend UI |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | [`docs/en/architecture.md`](docs/en/architecture.md) | Architecture design (Section 11 is the quant engine) | Before changing system structure |
| [`docs/API.md`](docs/API.md) | [`docs/en/api.md`](docs/en/api.md) | API specification (**both generated from the route table**) | Before changing an endpoint |
| [`CHANGELOG.md`](CHANGELOG.md) | [`CHANGELOG_EN.md`](CHANGELOG_EN.md) | What changed in each version | Before upgrading |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | [`CONTRIBUTING_EN.md`](CONTRIBUTING_EN.md) | Contribution process | Before opening a PR |
| [`docs/specs/`](docs/specs/) | — (stays Chinese) | Specs and plans for each round of changes (process records, not a second authority); this round's quant work is in `2026-10-02-量化策略提升路线图.md` + `2026-10-02-研究台报告.md` | When tracing a decision from a past round |

> 📌 `docs/API.md` and `docs/en/api.md` **are not hand-written** — they are generated from the FastAPI route table by `backend/scripts/gen_api_doc.py`, and `backend/tests/integration/test_api_doc.py` checks that both stay consistent with the implementation. After changing an endpoint, run `cd backend && python scripts/gen_api_doc.py` to regenerate them.
---

## 🔄 Workflow

1. **Data collection**: Tencent Finance real-time gold price and Sina Finance ICE dollar index; historical backfill supports three sources — Sina / Eastmoney / Yahoo; news is fetched via RSS
2. **Persistence**: gold prices, the dollar index and news are written to SQLite (a single file by default; `DATABASE_URL` can switch to MySQL)
3. **Analysis**: 5 analysis services each assemble a prompt → call the LLM once (the endpoint is chosen by `LLM_*`) → parse the JSON
4. **Quant**: public data sources → factor store → rolling z → per-horizon weights → one calibrated distribution → walk-forward backtest
5. **Cache**: results are written into a two-level cache of memory + JSON files (TTL 2 hours), shared across restarts and processes
6. **Display**: the frontend polls the market endpoint every 10 seconds, and analysis results are fetched on demand

---

## 🤖 Analysis Services

Early documents described these 5 services as a "LangChain Agent", which does not match the implementation. They are **independent single-turn LLM calls**: they do not communicate with each other or share state, and are linked only indirectly through the cache and the database. Every client is constructed through `backend/app/services/llm_provider.py`.

| Service | Code location | Input | Output |
|---|---|---|---|
| Bullish factors | `app/services/bullish_factor_service.py` | Last 24h news + gold price | 5 bullish factors + summary |
| Bearish factors | `app/services/bearish_factor_service.py` | Last 24h news + gold price | 5 bearish factors + summary |
| Institutional views | `app/services/institution_prediction_service.py` | Last 30 days of news + web search | The four institutions' most recent verifiable predictions (with date and source) |
| Investment advice | `app/services/investment_advice_service.py` | Market state + bullish/bearish factors + institutional views | Three strategy tiers + risk notes |
| Market summary | `app/services/market_summary_service.py` | All of the above | Core logic + risks + overall judgement |

**Model**: decided by `LLM_MODEL` in `backend/.env` (and the provider likewise — see the environment variables under "Local Development"). The model name shown in the page footer comes from `/health`'s `ai_config` and is not hardcoded in the code.

**Degradation behaviour**: when a data source or web search is unavailable, any service returns an explicit "unavailable" state and falls back to the database / RSS content; it does **not** fabricate data.

When the frontend cannot get data, it **shows "temporarily unavailable" and explains why**, and puts up no built-in numbers or conclusions of any kind. This used to be only a line in the docs: each section actually carried its own hard-coded fallback data (gold price 2823, institutional target prices 5400/5000/4500/2700, a 14-point price series, …), and rendered them as real content whenever an endpoint failed. Those constants have all been deleted, and a test now pins down that "no built-in copy may appear on failure".

**Removed**: the early `backend/app/agents/` package (`BaseAgent` / `MarketAnalyzerAgent` / `NewsAnalyzerAgent`) was never instantiated anywhere and has been removed.

---

## ⚠️ Honest Scope

This section is for anyone who formed expectations after reading the project description in the README. The following capabilities **do not exist** — please do not read this project through them:

| Rumoured capability | Reality |
|---|---|
| Multi-agent collaboration | 4 **independent single-turn LLM calls**, not agent collaboration: assemble a prompt → `llm.invoke(prompt)` → parse the JSON. No tool-calling loop, no inter-agent communication |
| RAG / vector retrieval | No vector store, no embeddings, no retrieval step. Historical prices and news are pasted straight into the prompt as context |
| ReAct reasoning loop | Not implemented; there is no Thought / Action / Observation loop |
| Real-time web search | Off by default (`LLM_SEARCH_ENABLED=false`). It uses MiMo's plugin-style `web_search`, not a generic OpenAI capability; when the endpoint has not enabled it, the call returns `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`, and the project falls back to the RSS news window |
| Sentiment analysis | The `sentiment` field is always `NEUTRAL`, only to keep the API shape stable; the page does not show sentiment conclusions |
| Redis / message bus / WebSocket / K8s / WAF / auth middleware | None of them. The cache is two-level: memory + JSON files |
| Trade execution | No brokers, no orders, no custody of funds |

**"A section sometimes shows temporarily unavailable" is designed behaviour, not a bug**: the reasoning model's thinking and its answer share `LLM_MAX_TOKENS` (default 8192). A budget that is too small truncates a large JSON such as the three strategy tiers and parsing fails, so per the hard rule it returns empty content — and the page honestly shows "investment strategy temporarily unavailable" rather than presenting a fabricated strategy (older versions hardcoded 4096, which is why this section stayed empty). On top of that, the endpoint has its own content filter and occasionally returns `finish_reason=content_filter` (the body is "The request was rejected because it was considered high risk"): the backend retries once automatically, and if it is still rejected the section honestly shows "temporarily unavailable" — press "re-analyse" to retry. When parsing fails, the log records `finish_reason` and token usage for the next investigation.

**Why so wordy**: this project's core promise is "**no fabrication**". When a data source or web search is unavailable, it returns "unavailable" with a reason, rather than letting the model generate institutional target prices, central-bank purchase volumes or gold price levels from its impressions. Better the page shows "data unavailable".

---

## 🤝 Contributing

We welcome contributions of all kinds! See our [contributing guide](./CONTRIBUTING.md) ([English](./CONTRIBUTING_EN.md)) to learn how to get involved.

### Contributors

<a href="https://github.com/JasonBuildAI/GoldMind/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=JasonBuildAI/GoldMind" alt="Contributors" />
</a>

---

## 📄 License

This project is open source under the [MIT License](./LICENSE).

---

## 🙏 Acknowledgements

- Any OpenAI-compatible LLM endpoint (during development this project used [Xiaomi MiMo](https://platform.xiaomimimo.com/)) - large language model and web-search capabilities
- [FastAPI](https://fastapi.tiangolo.com/) - high-performance web framework
- [React](https://react.dev/) - frontend UI framework
- The US Treasury, the New York Fed, CFTC, Yahoo Finance and Sina Finance - free, key-less public data sources

---

## 📧 Contact the Author

If you have any questions, suggestions or ideas for collaboration, you are welcome to reach us through:

- 🐛 **Questions and suggestions**: please open a [GitHub Issue](https://github.com/JasonBuildAI/GoldMind/issues)

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/JasonBuildAI">JasonBuildAI</a></sub>
</p>
