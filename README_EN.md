<p align="center">
  <img src="docs/images/6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>An AI Data Analysis Engine for the International Gold Market</strong><br>
  <em>面向国际黄金市场的 AI 数据分析引擎</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0.1-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/released-2026--10--02-success?style=flat-square" alt="Release date">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/SQLite-zero--config%20repro-003B57?style=flat-square&logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <strong>English documentation</strong> | <a href="./README.md">中文文档</a>
</p>

---

<!-- ⬇️⬇️⬇️ Release banner: update these lines together with the version ⬇️⬇️⬇️ -->

<h1 align="center">🎉 GoldMind 2.0.1 is here</h1>

<h2 align="center">GoldMind 2.0.1 正式发布</h2>

<p align="center">
  <img src="https://img.shields.io/badge/release-v2.0.1-FFD700?style=for-the-badge" alt="v2.0.1">
  <img src="https://img.shields.io/badge/released-2026--10--02-2EA043?style=for-the-badge" alt="2026-10-02">
</p>

<p align="center">
  <strong>Every number comes from one calibrated distribution — and every claim that failed its check stays on the page.</strong><br>
  <em>每个数字都出自同一份校准分布；每条没通过验证的结论，也照样写在页面上。</em><br><br>
  📋 <a href="./CHANGELOG_EN.md">Changelog</a> ·
  🌍 <a href="./CHANGELOG.md">更新日志</a> ·
  🚀 <a href="https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.1">GitHub Release v2.0.1</a>
</p>

<!-- ⬆️⬆️⬆️ Release banner ends ⬆️⬆️⬆️ -->

---

## 🆕 What 2.0.1 delivers

2.0.1 does not swap the model. It does three things: **fix the conventions, make the evaluation
honest, and take back claims that cannot be proven.** The live model is `quant-v7` (this round's
publication-lag fix; the `quant-v6` and older records are no longer comparable) —
the third pre-registered candidate C2 needed 60-day development coverage in [0.78, 0.82];
it landed at 0.7679, 1.2pp short, and was eliminated. The bar does not move for it.

| Area | 2.0.0 | 2.0.1 |
|---|---|---|
| Probability | `p_up = Φ(μ/σ)`, with a σ that had already been inflated for interval width — the direct mechanism behind a negative Brier skill score everywhere | `p_up = 1 − F̂(−μ/scale)`: probability, interval and scenarios all come from the same calibrated distribution F̂; direction = sign(μ) |
| Interval | Normal quantiles; and the ACI α update judged "the bet sent h days ago" with "today's row" | Asymmetric empirical quantiles + online ACI. After the misalignment fix, development coverage went 76.7% → 79.3% (20d) and 72.6% → 73.6% (60d) |
| Stale factors | Old observations were forward-filled into a fake current level | Observations past their freshness cap become NaN at composition time: no z, no score, no backtest factor count |
| Bet accounting | 754 overlapping holdout samples in the 250-day window treated as 754 pieces of evidence | Independent bets sampled at stride = h (that same stretch really holds 3 bets); insufficient samples are labelled "undecidable", not "failed" |
| Significance | iid t only | HAC (Newey–West) shown next to iid: gold/silver at 60d reads **+2.30** HAC vs **+12.70** iid — the literal meaning of "half of your significant factors are fake" |
| Sample periods | development / holdout | Four: development, historical holdout (record only), **forward holdout** (the only judging window, starting 2026-10-02), full sample |
| New information sources | — | GVZ, gold/silver ratio, copper/gold ratio, CFTC net-long share of open interest, official daily GPR — all on the monitor table, **all labelled information-only** (none cleared the gates on a 26-year panel; giving them a direction would be fabrication) |
| Reproducibility | Factor table kept only the current value | Append-only revision ledger + `--as-of` panel rebuild; every stored prediction carries the measured skill of its own horizon |

---

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-quant-strategy">Quant strategy</a> •
  <a href="#-quick-start">Quick start</a> •
  <a href="#-common-commands">Commands</a> •
  <a href="#-directory-layout">Layout</a> •
  <a href="#-documentation-map">Docs</a> •
  <a href="#-honest-statement-implementation-boundaries">Honest statement</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## ⚡ Overview

**GoldMind** is a gold-market analysis board. It collects gold prices and the dollar index,
uses an LLM to turn recent news into bullish/bearish factors, institutional views, investment
strategies and a market summary, and runs a quantitative engine over four layers of drivers
(monetary policy & rates / risk & credit / supply & demand / market & technicals) to predict
1 / 5 / 20 / 60 / 250 trading days ahead (intraday–one week, 1–3 months, 6–18 months): direction,
target price and scenarios, all derived from one calibrated distribution, with the uncalibrated
factor tilt folded into a details note. Everything is presented as a single-page **light research
briefing** — seven sections, left-aligned, no gradients, no shadows, no card kit; numbers are
tabular, red-up/green-down, and direction always carries both a symbol and words. The
"Messages" section crawls high-authority sources (central banks / wire services / industry
bodies / professional financial media), scores gold-related headlines deterministically by
importance and confidence, and takes a top 10 in each of three windows (24h / 7d / 30d). A separate
**research page** (`/research.html`) lays out the pre-registered candidate × horizon evaluation,
coverage, reliability bins and per-factor breakdown — **including the conclusions that failed**.

The LLM provider is **not hard-coded**: any OpenAI-compatible endpoint (OpenAI / DeepSeek /
Qwen / Kimi / local Ollama / Xiaomi MiMo …) works by editing `LLM_BASE_URL` / `LLM_API_KEY` /
`LLM_MODEL` in `backend/.env`. Every client is constructed through
`backend/app/services/llm_provider.py`. If any of the three is missing, the feature counts as
"not configured" and the section says so — it never falls back to built-in content.

> You only need to: open the page.
> GoldMind returns: today's gold price, the dollar index, news-based bull/bear analysis and
> strategy suggestions — plus a backtestable quantitative forecast.

> 📌 Product boundaries and known limits live in [`docs/00-产品方向.md`](docs/00-产品方向.md)
> (English mirror: [`docs/en/product-direction.md`](docs/en/product-direction.md)).
> **Anything marked "target" there is not implemented; do not read it as a shipped feature.**

### 🧩 The actual pipeline

```
Market data ──► SQLite ──┐
RSS news    ──► SQLite ──┼──► prompt ──► llm.invoke() ──► parse JSON ──► cache ──► dashboard
                         │
                         └──► (optional) plugin-style web_search (LLM_SEARCH_ENABLED, off by default)

Public sources ──► factor observations ──► rolling z ──► per-horizon weights ──► one calibrated
(Treasury / NY Fed / CFTC /     │  (current value + append-only revision ledger; --as-of rebuilds
 Yahoo / RSS, all key-free)     │   the panel as of any past day)
                                ├──► walk-forward backtest (independent bets / HAC / four periods)
                                └──► monitor dashboard (21 water-level rows, 5 of them information-only)
```

| Service | Input | Output |
|---|---|---|
| Bullish factors | last 24h news (high-authority digest + RSS, merged and deduped) + gold price | 5 bullish factors |
| Bearish factors | last 24h news (high-authority digest + RSS, merged and deduped) + gold price | 5 bearish factors |
| Institutional views | last 30 days of news (same input) + (search) | each institution's latest verifiable forecast (with date and source) |
| Investment advice | market state + factors + institutional views + the same news input | conservative / balanced / opportunity strategies |
| Market summary | all of the above | core logic, risks, overall judgement |

> The news input merges `gold_news` with the message board's high-authority items, deduplicated by
> normalised URL (message-board items win); every prompt line carries a title plus a cleaned,
> truncated summary. News, price context and the capability statement come from one shared input
> packet (`build_analysis_input`, same window, same definitions): `backend/app/services/analysis_input.py`.

---

## 🌟 Our vision

**GoldMind** aims to be a **genuinely usable AI-agent platform for international gold-market
analysis and price forecasting**, built with the community.

Through technical work we want to:

- 📉 **Reduce the information gap** — give every investor professional-grade market analysis
- 🛡️ **Strengthen risk resistance** — multi-dimensional risk assessment and warnings
- 💡 **Offer actionable advice** — strategies grounded in data and reasoning

> 🤝 **You are welcome to join!** Code, feature ideas and feedback all move the project forward.

If this project helps or inspires you, a ⭐ **Star** is the best thank-you.

---

## 📸 Screenshots

> All 14 screenshots were taken on **2026-10-02 against a real running stack** (real backend,
> real data, real LLM endpoint) by
> [`app/scripts/capture_screenshots.mjs`](app/scripts/capture_screenshots.mjs). Before saving,
> the script checks every block for substantial text and for the absence of empty-state markers;
> if any block degrades into "loading" / "unavailable", it exits with an error and **never writes
> a half-empty image**. You can reproduce them exactly (see "Common commands").

### Masthead and market data
<p align="center">
  <img src="docs/images/screenshots/dashboard.png" alt="Masthead and market data" width="800">
</p>

### Chart and key figures
<p align="center">
  <img src="docs/images/screenshots/price-chart.png" alt="Price chart and key figures" width="800">
</p>

### Bullish vs bearish factors
<p align="center">
  <img src="docs/images/screenshots/news-analysis-up.png" alt="Bullish factors" width="400">
  <img src="docs/images/screenshots/news-analysis-down.png" alt="Bearish factors" width="400">
</p>

> The two sides fetch and refresh independently; one side failing does not affect the other.
> The prompt explicitly says "rather return fewer items than pad the list with common-sense
> inventions"; when nothing can be found the page says "temporarily unavailable" and offers a
> re-run, with no built-in fallback text. Every model response then passes a deterministic
> structure check (max 5 factors / dedupe by id / allowed-id enum / best-effort numeric
> citation); a factor that fails is dropped entirely (`services/factor_validation.py`).

### Institutional views
<p align="center">
  <img src="docs/images/screenshots/institutional-views.png" alt="Institutional views" width="800">
</p>

> The only verifiable forecast that day was **Morgan Stanley: $4,000 is the support after the
> pullback, with a long-term view of $5,000 in H2 2027** (forecast date 2026-10-01, from real
> coverage inside the 30-day news window). Goldman Sachs, UBS and Citi had no verifiable target
> price in the window, so the page says "no recent forecast" — having all four say "none", or
> inventing numbers for them, are both explicitly unwanted behaviours here.
> Web search is off by default (`LLM_SEARCH_ENABLED=false`): it uses MiMo's plugin-style
> `web_search`, not a generic OpenAI capability. With the plugin disabled the endpoint returns
> `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`
> (reproducible with `backend/scripts/smoke_llm.py`).

### Investment strategy
<p align="center">
  <img src="docs/images/screenshots/investment-advice.png" alt="Investment strategy" width="620">
</p>

> The three strategies come from one LLM call; the output budget is `LLM_MAX_TOKENS`
> (default 8192, raise it for your endpoint). Too small a budget truncates the large JSON and
> parsing fails — the page then says "temporarily unavailable" instead of showing a built-in
> strategy; the backend logs `finish_reason` and token usage to make the next diagnosis easy.

### Quantitative forecast
<p align="center">
  <img src="docs/images/screenshots/quant-prediction.png" alt="Quant forecast: 1-year direction, probability and scenarios" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/quant-fair-value.png" alt="Fair-value decomposition" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/quant-monitor.png" alt="Monitor dashboard (21 rows)" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/quant-accuracy.png" alt="Backtest accuracy, baselines and coverage (1 quarter)" width="800">
</p>

> The quantitative engine calls no LLM: all 14 factors come from free public sources; missing
> factors and indicators are marked "unavailable" with a reason, and fewer than 3 usable factors
> means "forecast unavailable". On the capture day 12/14 factors were usable (geopolitical
> strength and GLD shares lacked samples); forecast and backtest share one horizon tab strip,
> so the shots above are the 1-year and 1-quarter tabs. In the monitor table the last five of the
> 21 rows are the second round's **information-only** series: GVZ, gold/silver ratio, copper/gold
> ratio, CFTC net-long share of open interest and official daily GPR — none cleared the gates, so
> they show values and dates but no bull/bear label. Stored forecasts keep one row per
> (model version, horizon, as_of): same-day recomputes update in place, a new day appends,
> so the table is the forecast archive.

### Research page (pre-registered verdict + skill overview)
<p align="center">
  <img src="docs/images/screenshots/research-verdict.png" alt="Research page: verdict (forward window not yet decidable)" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/research-forward-window.png" alt="Research page: how many trading days the forward window still needs" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/research-overview.png" alt="Research page: skill overview across five horizons" width="800">
</p>

> The research page spells out why no edge can be claimed yet: the verdict only counts independent
> bets in the forward holdout (from 2026-10-02). The 1-day horizon has 1/20 bets and needs about
> 19 more trading days; the 5-day horizon needs about 99. The historical-holdout column is
> explicitly labelled "already seen by the first two rounds — record only" and never substitutes
> for the verdict. The page header also surfaces the **data window** (start/end, trading days,
> years): every number is recomputed from exactly that window (1-hour cache); where the counts
> disagree with the snapshots cited in README / historical lab reports, the research page wins.

### Summary
<p align="center">
  <img src="docs/images/screenshots/market-summary.png" alt="Market summary" width="800">
</p>

---

## 📐 Quant strategy

This section explains **how "the four layers of drivers" become the numbers on the page**, and
**where those numbers can be wrong**. The factor list, weights, direction priors and freshness
caps are defined in exactly one place — `backend/app/services/quant/definitions.py`; this section
does not restate them, and code wins over prose.

### 1. Four layers, 14 factors

The framework classifies the drivers of the international gold price into four layers:

| Layer | What it maps to | Factors | The question it answers |
|---|---|---|---|
| Monetary policy & rates | real rates, policy path, the dollar | 4 | Is the opportunity cost of holding gold rising or falling? |
| Risk & credit | volatility, credit stress, geopolitics | 3 | What is the market afraid of, and where is money hiding? |
| Supply & demand | central-bank buying, positioning, ETF flows | 3 | Who is really buying, and how much? |
| Market & technicals | momentum, seasonality, alternatives, risk appetite | 4 | What does price inertia itself say? |

Full definitions of the 14 factors (prior `+1` = the factor rising is bullish for gold, `-1` = bearish):

| Factor | Layer | Unit | Source | Prior | Weight 1d/1w/1m/1q/1y | Freshness cap |
|---|---|---|---|---|---|---|
| US 10-year real yield | Monetary policy & rates | % | US Treasury (TIPS real yield curve) | −1 | 0.25 / 0.5 / 1.0 / 1.0 / 0.8 | 7 days |
| Market-implied policy expectation | Monetary policy & rates | % | US Treasury (2-year) − NY Fed (EFFR) | −1 | 0.2 / 0.4 / 1.0 / 0.8 / 0.6 | 7 days |
| 10-year inflation expectation | Monetary policy & rates | % | US Treasury (nominal − real yields) | +1 | 0.1 / 0.2 / 0.5 / 0.5 / 0.4 | 7 days |
| Dollar index | Monetary policy & rates | points | Yahoo Finance (DX-Y.NYB) | −1 | 0.3 / 0.5 / 0.9 / 0.7 / 0.5 | 7 days |
| VIX | Risk & credit | points | Yahoo Finance (^VIX) | +1 | 0.6 / 0.5 / 0.4 / 0.3 / 0.2 | 7 days |
| Credit-market risk appetite | Risk & credit | % (20d) | Yahoo Finance (HYG/IEF ratio) | −1 | 0.5 / 0.4 / 0.3 / 0.2 / 0.2 | 7 days |
| Geopolitical risk strength | Risk & credit | % (news share) | this system's RSS corpus (keyword-intensity proxy) | +1 | 0.5 / 0.5 / 0.4 / 0.3 / 0.3 | 3 days |
| Central-bank gold reserves (China) | Supply & demand | 10k oz | Sina Finance (PBoC official reserve assets) | +1 | 0.2 / 0.4 / 0.7 / 1.0 / 1.0 | 62 days |
| COMEX speculative net long | Supply & demand | contracts | CFTC positioning report (contract 088691) | +1 | 0.8 / 0.7 / 0.4 / 0.3 / 0.2 | 14 days |
| Gold ETF shares (GLD) | Supply & demand | shares | Yahoo Finance (GLD share snapshot, accumulating since collection began) | +1 | 0.3 / 0.4 / 0.5 / 0.7 / 0.8 | 7 days |
| Gold trend momentum | Market & technicals | % (60d) | Yahoo Finance (GC=F close) | +1 | 1.0 / 1.0 / 0.4 / 0.3 / 0.2 | 7 days |
| Seasonality (month's historical mean) | Market & technicals | % (historical mean) | own price series (calendar month, prior years only) | +1 | 0.2 / 0.3 / 0.2 / 0.2 / 0.2 | 7 days |
| Bitcoin (digital-gold narrative) | Market & technicals | points | Yahoo Finance (BTC-USD) | −1 | 0.2 / 0.2 / 0.2 / 0.2 / 0.3 | 7 days |
| Equity risk appetite | Market & technicals | points | Yahoo Finance (SPY) | −1 | 0.5 / 0.4 / 0.3 / 0.2 / 0.2 | 7 days |

Direction priors come from economic reasoning and are **not guaranteed to hold** — the backtest
reports per-factor hit rates and IC (the "factor breakdown" section of the research page), and
the page shows contrary evidence as it is. Besides these 14 factors, the
`factor_observations` table also stores 10 **monitor-only** series (USDCNY, the CNY gold
reference, the TGA balance, RRP, open interest, GVZ, the gold/silver ratio, the copper/gold
ratio, the CFTC net-long share and official daily GPR). They never enter composition — see
section 8.

### 2. Five horizons, each with its own dominant layer

The first methodological step is **choose the horizon, then the variables** — the same factor
carries different weights at different horizons:

| Horizon | Label | Real-world span | Dominant layer | Comment |
|---|---|---|---|---|
| 1 trading day | 1d | intraday–1 week | market & technicals → supply & demand | flows, technicals and positioning dominate; macro weighs least |
| 5 trading days | 1w | intraday–1 week | market & technicals → risk & credit | weekly flows and event impulses; macro still secondary |
| 20 trading days | 1m | 1–3 months | monetary policy & rates → supply & demand | policy expectations, data and the dollar dominate |
| 60 trading days | 1q | 1–3 months | monetary policy & rates → supply & demand | policy path and demand structure both matter |
| 250 trading days | 1y | 6–18 months | supply & demand → monetary policy & rates | real-rate cycles, the easing path and central-bank buying dominate; **no direction is published** (it matched "always long" day by day in the holdout) — only the fair-value deviation and the annual calibrated interval |

This is why each of the 14 factors carries five weights instead of one global weight: explaining
tomorrow's gold price with central-bank buying, or next year's with VIX, gets the horizon wrong.

### 3. One calibrated distribution feeds every output (`quant-v7`)

The composite `score` is an **uncalibrated** input — it appears only in the factor table and the
"factor tilt (uncalibrated)" details block. Everything on the page comes out of the same
`engine.build_prediction_frame` exit:

```
signed_z_i = sign_i × z(x_i)                    per-factor direction alignment (5-year rolling z)
score_h    = Σ w_i(h) · signed_z_i / Σ w_i(h)   weights per horizon, renormalised

μ_h        = α + β · score_h                    expanding-window OLS on pairs with s + h ≤ t
scale_h    = std(e_s | s + h ≤ t)               std of walk-forward errors
F̂_h        weighted empirical distribution of recent realised e_s/scale_h; the nominal miss
            rate α is updated online by ACI

interval   = μ + scale · [ F̂⁻¹(α/2),  F̂⁻¹(1−α/2) ]
scenarios  = μ + scale · [ F̂⁻¹(0.25), F̂⁻¹(0.75) ]
p_up       = 1 − F̂( −μ / scale )               same distribution as the interval and scenarios
target     = base price × (1 + μ)               base = COMEX front-month daily close (gold_close)
direction  = sign(μ)                            exactly 0 is reported as "flat"
```

Model version **`quant-v7`**. Six hard conventions:

1. **No look-ahead.** Rolling statistics and regression samples are all shifted before t;
   sources published after the gold close carry `publication_lag_days` in the factor table
   (Treasury yield curve and NY Fed EFFR: 1 business day each; CFTC positioning and central-bank
   reserves are already tagged with their usable date at the source layer) — the engine aligns
   by visibility time, and the displayed age uses the same convention.
   Guard: `backend/tests/unit/quant/test_no_lookahead.py` — replace post-t data with garbage and
   the signal at t must stay bit-for-bit identical.
2. **No "assume unchanged" fallback.** With fewer than 60 regression pairs the horizon is
   "unavailable + reason": no score sign as a stand-in direction, no pretending μ = 0. With fewer
   than 60 realised errors, `scale` falls back to the expanding std of realised h-day returns,
   still using only past data.
3. **Expected return is capped**: `|μ| ≤ EXPECTED_CAP_SIGMAS × expanding std of realised h-day
   returns`. In windows where the score barely moves, the univariate OLS denominator approaches
   zero and β can reach 10⁴ — a real 20-year panel produced +126167% at 60 days. The cap keeps
   displayed targets and intervals from flying off.
4. **Missing factors are renormalised by remaining weights**, never treated as 0; fewer than 3
   usable factors means "forecast unavailable".
5. **Stale means disabled.** Observations past `max_age_days` become NaN in `align_series`: they
   enter no z, no composite and no backtest factor count — no three-month-old number pretending
   to be today's level.
6. **Time flows in one timezone** (`app.utils.timeutil`, default `Asia/Shanghai`).

The probability is **not** `Φ(μ/σ_display)` — that divides by the scale already widened for the
interval, pushing every probability toward 50%. Before 2.0.1 this was exactly the mechanism
behind the negative Brier skill score; now probability and interval are different reads of the
same distribution. `σ_display` still exists, for display only ("equivalent normal scale").

**The interval convention is asymmetric ACI (adaptive conformal inference)**: the nominal miss
rate α updates online as each forecast is issued. 2.0.1 fixed a misalignment that systematically
depressed coverage — α was updated by judging the bet sent h days ago with today's row, which
biases longer horizons more and pushes coverage down. After the fix, development coverage went
76.7% → 79.3% (20d) and 72.6% → 73.6% (60d) as measured through the research API.

### 4. Fair value in four layers

`decompose.py` uses a walk-forward expanding-window OLS:

```
log gold price ~ real yield + log dollar index + log central-bank reserves + VIX
```

and splits the price into **macro anchor + demand premium + risk premium + sentiment residual**.
The display convention lives only in `decompose.py`: demand and risk premia are chained
multiplicatively (the risk premium is applied to "anchor + demand premium"), so both
"anchor + demand + risk = fair value" and "the three blocks + residual = market price" hold by
construction. Regression coefficients at t use only realised samples with `s ≤ t−1`; fewer than
120 samples or a missing regressor returns "unavailable + reason". Deviation = market / fair − 1.

Since 2.0.1 the decomposition **no longer extrapolates beyond the regression's support**: if a
fitted value leaves the `6σ` / `12 log-premium` envelope, that block is reported as
`unsupported_by` and refuses to produce a number — a premium "computed" on inputs the historical
sample never covered is extrapolation noise, not information.

> With this, "is it expensive now" stops being a feeling: it becomes "the market trades X% above
> the model's fair value; of that, how much is demand, how much is risk, how much is sentiment" —
> plus "is this judgement inside the range the model has actually seen".

### 5. Scenario triggers and invalidation

The three scenarios are not hand-written: Base takes the middle 50% of the distribution
(q25–q75 of F̂), Bull and Bear take the top and bottom 25%, so their probabilities always sum to
100%. Each scenario also carries **trigger** and **invalidation** conditions generated from the
horizon's heaviest factor and the 200-day moving average — checkable sentences, not adjectives.
Non-positive scale, a missing base price or no usable factors returns "unavailable + reason"
without blocking the main forecast.

### 6. Backtest conventions: four periods, independent bets, three baselines

The backtest (`backtest.py`) is **walk-forward**: every historical point uses only what was
available then. Since 2.0.1 the sample is cut into four periods first — mixing them would be
evidence laundering:

| Period | Start | Purpose |
|---|---|---|
| development | data start | the only stretch where parameters and candidates may be tuned |
| historical holdout | 2023-10-02 | already seen by the first two rounds; **record only, never a selection basis** |
| forward holdout | 2026-10-02 (pre-registration seal) | the **only** judging window; below 20 independent bets the status is `pending` and the report says how many trading days are still missing |
| full sample | data start | display only; never used for verdicts |

Second, **overlapping samples are not independent evidence**. The 250-day historical holdout has
754 overlapping observations, which at stride = h become **3** genuinely independent bets. Every
skill judgement also reports `independent_bets` (754 / 151 / 37 / 12 / 3 across horizons); too
few samples are labelled "undecidable". Hit rates always sit next to three baselines:

| Baseline | Meaning |
|---|---|
| Always long | ignore every signal and guess up every day |
| Momentum | extrapolate the recent trend |
| Coin flip | 50% |

Measured 2026-10-02 (`quant-v6` conventions, 26-year panel; pending real-stack recomputation after the v7 publication-lag fix):

| Horizon | Development hit | Historical-holdout hit | Always-long (holdout) | Diff | Development coverage | Historical-holdout coverage | Full-sample coverage |
|---|---|---|---|---|---|---|---|
| 1d | 52.5% | 54.6% | 56.4% | −1.7pp | 79.9% | 78.4% | 79.7% |
| 1w | 53.4% | 60.9% | 62.1% | −1.2pp | 80.0% | 77.9% | 79.7% |
| 1m | 54.6% | 68.1% | 68.1% | +0.0pp | 79.0% | 76.9% | 78.8% |
| 1q | 60.8% | 83.4% | 83.4% | +0.0pp | 74.5% | 65.3% | 73.5% |
| 1y | 71.8% | 100.0% | 100.0% | +0.0pp | 61.2% | 28.4% | 58.4% |

Read this carefully: the historical holdout is a three-year one-way gold rally, so "always long"
alone scores 56–100%. At 20 days and beyond the model matches it day by day (+0.0pp); **at 1 day
and 1 week it does worse** (−1.7pp / −1.2pp) — on short horizons it does call down moves, and in
this rally a down call is simply wrong. Its Brier skill score is negative
(−0.006 / −0.029 / −0.096 / −0.388); at 1 year the base rate is 100%, so the constant forecast has
zero loss and the skill score is **undefined** — no number is printed there. A
distribution-level CRPS is reported alongside with its own skill score against the zero-drift
benchmark (Brier scores up/down, CRPS scores how well the whole distribution matches). **That record proves
neither an edge nor its absence — it only proves the historical holdout has been seen.**

From 2.0.2 the research page puts two **first-class KPIs** next to the hit rate:

- **Edge vs always-long with a 95% confidence interval** (`direction_edge_vs_up_ci95`):
  the point estimate is almost always negative in a one-way market; whether the interval
  crosses zero decides whether the edge can be called a result. The interval uses a
  block bootstrap with block length = the horizon, so overlapping samples do not
  artificially narrow it.
- **Dare-to-call-down quality** (`down_call_edge_vs_up`): the number of down calls, their
  hit rate, and the difference against "always long" **on the same down-call days** —
  calling down is easy in a bear market; the difference shows whether the model dares to
  bet against a benchmark that is making money from rallies. With fewer than 30 down
  calls the hit rate is `None`, never "100% of zero calls".

The forward verdict now also prints a **Beta posterior** (fixed uniform Beta(1,1) prior
plus independent-bet counts: mean, 95% credible interval, P(better than always-long))
and the **CRPS** skill score side by side. The selection rules are unchanged — the
posterior only makes "how much independent evidence backs this hit rate" visible.

Hence 2.0.1 moves the
judging window forward, and coverage gaps are audited by volatility bucket (thresholds from the
expanding past distribution only, independent bets inside each bucket, counts reported when
fewer than 30).

### 7. Research bench and pre-registration: improvements must clear the line first

`scripts/quant_lab.py` **freezes the candidate list and the pass lines before running the numbers**,
then evaluates them over three sample periods. The candidates are not arbitrary: baseline B0,
drift D1/D3/D5, composite S1–S4, interval P1–P4, calibration C0/C1/C2, factor-set F1–F4 and
ensemble E0 and multivariate M1/M2 — 22 in total (defined in one place,
`scripts/quant_lab.py`). The M family (multivariate walk-forward Ridge) is a research-bench
comparison against "compose first, then regress" and does not change the live `quant-v7`.

**The first round (17 candidates, before 2.0) concluded "no conclusion"**: 17 candidates × 5
horizons, none cleared the line on the holdout, and after the engine fixes they are
statistically indistinguishable from each other
(full table: [`docs/specs/2026-10-02-研究台报告.md`](docs/specs/2026-10-02-研究台报告.md)).
**That negative result is the most valuable output of this round**: it redirected the budget from
"keep tuning" to "new information sources and a longer history" — the panel was backfilled to 20
years, evaluation moved to independent bets + HAC, and five new series were wired in (section 8).

The same discipline now has an executable form: the **factor gate layer**
(`backend/app/services/quant/screen.py`, driven by `scripts/screen_factors.py`). Any new factor
must pass three gates before it may enter composition:

1. **Significance**: covariance after de-meaning (not raw correlation) with HAC (Newey–West)
   t-statistics, plus a Bonferroni correction and a hard `|t| ≥ 3` threshold (p-values alone get
   fooled by borderline sampling);
2. **Cross-horizon agreement**: the sign must agree across short/medium/long horizons — one
   significant cell is not enough;
3. **Forward-window confirmation**: after the pre-registration seal
   (`ACTIVE_HOLDOUT_START = 2026-10-02`) the series must accumulate `max(20, ⌈300/h⌉)`
   independent bets; until then the status is `pending` with the number of trading days still
   missing.

Measured on all 255 cells of a 26-year panel: **no signal passed gates ①②**; "reversed
significance" is recorded but never adopted (a pre-committed direction rule — no post-hoc sign
flips), and the list came out empty with the closest entry at `|t| = 2.98`; gate ③ is `pending`
everywhere (about 299 trading days short at 1d/5d, 399 at 20d, 1199 at 60d, 4999 at 250d).
In other words: today no new series deserves a bull/bear label.

**Round three (2.0.1)** pre-registered one candidate, C2 (calibration counted per bet + a lookback
window), with the bar written down first: 60-day development coverage must land in [0.78, 0.82],
the width must not widen, and the cross-bucket coverage spread must stay within 2pp. Measured:

| Horizon | Live B0 coverage | C1 (per bet) | **C2 (per bet + window)** | Width ratio (C2/B0) |
|---|---|---|---|---|
| 5d | 0.7997 | 0.8097 | 0.8161 | 1.054× (widening — vetoed) |
| 20d | 0.7895 | 0.8055 | 0.7984 | 0.991× |
| 60d | 0.7437 | 0.7720 | **0.7679** | 0.881× |

**Verdict: C2 is eliminated.** Its 60-day coverage is 1.2pp short of the pre-registered 0.78, and
the bar does not move for it. The control candidate C0 equals live B0 value for value (proving
the machinery itself has no side effects). The record is in
[`docs/specs/2026-10-02-量化引擎第三轮预注册.md`](docs/specs/2026-10-02-量化引擎第三轮预注册.md);
reproduce with `python scripts/quant_lab.py --group calibration --horizons 20,60`.

> The honest summary: 2.0.1 did not replace the model with a "looks stronger" version, because
> the evidence does not support one. It made every future improvement clear the line first — and
> made "not there yet" visible by itself.

### 8. Monitor dashboard: 21 water-level rows

`monitor.py` covers **21 rows**. Each row carries frequency, source, current value, signal
(bullish / bearish / neutral / information) and as-of date. Signal rules are deterministic
thresholds centralised in `_rule`; rows without data or without enough history honestly return
"unavailable + reason". Each row updates at its own source cadence (daily / weekly / monthly) —
this is not one uniform refresh:

| # | Indicator | Freq | Unit | Source | Signal rule / note |
|---|---|---|---|---|---|
| 1 | US 10y real yield (TIPS) | D | % | US Treasury TIPS curve | 5-obs change ≤ −0.10pp bullish, ≥ +0.10pp bearish |
| 2 | Breakeven inflation (10y nominal − real) | D | % | US Treasury yield curve | 5-obs change ≥ +0.10pp bullish, ≤ −0.10pp bearish |
| 3 | Dollar index (DXY) | D | pts | Yahoo Finance (DX-Y.NYB) | 5-obs change ≥ +1% bearish, ≤ −1% bullish |
| 4 | Market-implied policy expectation (2y − EFFR) | D | % | US Treasury − NY Fed | 5-obs change ≥ +0.10pp bearish, ≤ −0.10pp bullish |
| 5 | Central-bank gold reserves | M | 10k oz | Sina Finance (official reserves) | MoM increase bullish, decrease bearish |
| 6 | Gold ETF shares (GLD) | D | shares | Yahoo Finance | last two observations: increase bullish (subscription), decrease bearish |
| 7 | CFTC net long (crowding) | W | contracts | CFTC positioning report | net z ≥ +1.5 bearish, ≤ −1.5 bullish |
| 8 | Shanghai gold premium | D | CNY/g | SGE AU9999 | **measured unavailable**: reason shown, no invented number |
| 9 | VIX | D | pts | Yahoo Finance (^VIX) | ≥ 25 bullish, ≤ 15 bearish |
| 10 | Credit appetite (HYG/IEF 20d change) | D | % | Yahoo Finance | ≥ +2 bearish, ≤ −2 bullish |
| 11 | Gold vs 200-day MA | D | USD | own price series | deviation ≥ +0.5% bullish, ≤ −0.5% bearish |
| 12 | USD/CNY | D | CNY | Yahoo Finance (CNY=X) | information only: conversion reference, no direction |
| 13 | CNY gold reference | D | CNY/g | gold close × USDCNY ÷ 31.1035 | information only: price anchor for domestic investors |
| 14 | US Treasury TGA balance | D | USD mn | US Treasury Fiscal Data | 20-obs increase ≥ 50bn bearish, decrease ≥ 50bn bullish |
| 15 | NY Fed reverse repo (RRP) | D | USD 100mn | NY Fed open-market results | 20-obs increase ≥ 5bn bearish, decrease ≥ 5bn bullish |
| 16 | COMEX gold open interest | W | contracts | CFTC positioning report | information only: participation gauge, no direction |
| 17 | Gold implied volatility (^GVZ) | D | pts | Yahoo Finance (^GVZ) | information only: 18-year panel, \|t\| < 0.6 at all horizons |
| 18 | Gold/silver ratio | D | ratio | Yahoo Finance (GC=F ÷ SI=F) | information only: best cell 60d t=+2.30 (iid +10.76), gate not cleared |
| 19 | Copper/gold ratio | D | ratio | Yahoo Finance (HG=F ÷ GC=F) | information only: 250d t=+1.27 over 26 years, gate not cleared |
| 20 | CFTC net long share of open interest | W | % | CFTC positioning report | information only: crowding as a share, 250d t=+0.73, gate not cleared |
| 21 | Geopolitical risk (official daily GPR) | D | pts | Iacoviello & Papaioannou GPR | information only: 20d t=−2.64 (reversed), short of \|t\| ≥ 3, no direction |

> Rows 17–21 are the second round's five new sources. Whether they carry directional information
> was tested on a 26-year panel through the strict gates (section 7) and none cleared — so these
> five **never get a bull/bear label**, they are water levels only. Rows 12–16 are likewise
> monitor-only series stored in the same table (`factor_observations`) without entering
> composition; order and count are fixed by `monitor.ROW_SPECS` and guarded line by line in
> `backend/tests/unit/quant/test_monitor.py`.

### 9. Data sources and freshness

- **All free, no keys**: US Treasury yield curve and Fiscal Data (TGA), NY Fed RRP and EFFR,
  CFTC positioning reports, Yahoo Finance (DXY / GC=F / SI=F / HG=F / GLD / SPY / BTC-USD /
  ^VIX / ^GVZ / HYG / IEF / CNY=X), Iacoviello & Papaioannou's official daily GPR series,
  Sina Finance (central-bank reserves), and this system's own RSS corpus.
- **Per-source throttling**: the sync engine gives each source its own 6–24h window and fetches
  increments; one source failing does not affect the others, and the failure reason is written
  into the sync report. The page keeps per-source status (ok / not due / unavailable) in a folded
  "data source status" block instead of spending space on it.
- **Per-factor freshness caps** (last column of the section-1 table): 7 days for daily series to
  cover long holidays, 62 days for monthly ones to cover publication delays. Observations past
  the cap become NaN **at composition time** (not filled forward and then labelled), so "stale"
  really means excluded.
- **Observations have a revision ledger; historical panels can be rebuilt.**
  `factor_observations` is append-only: repeating a fetch for the same `(factor_key, obs_date)` is
  idempotent, and a revised value appends a new observation. Any historical verdict can therefore
  be recomputed with `--as-of 2026-09-01` against the revision state visible that day —
  pre-registration has to be re-checkable, otherwise it is just a slogan. When upgrading an old
  database, `migrate_quant.py` backfills the ledger from existing observations; without it
  `--as-of` would silently return an empty panel, so the migration prints the number of rows it
  is backfilling.
- **Future observations are rejected**: any row whose `obs_date` is later than "today" is
  refused at the door (timezone rule #5), so the backtest can never read data that had not
  happened yet.
- **First backfill defaults to 10 years** (`QUANT_HISTORY_YEARS`, raise it if you like), then
  increments only. To stretch the panel to 20 years in one go, use
  `backend/scripts/backfill_quant.py --apply --years 20`; `--dry-run` only prints what each
  series is missing and writes nothing.

### 10. Known limitations (stated without polish)

1. **The 1-year coverage is still well below nominal.** Development 55.9%, full sample 52.8%,
   historical holdout 28.8% (nominal 80%). Width calibration cannot repair a biased centre (μ),
   and the gap grows monotonically with horizon (development coverage 80.2 / 80.1 / 79.3 / 73.6 /
   55.9% for 1/5/20/60/250 days). This heads the next round's agenda; none of the 20 candidates
   (including round-three C2) changed that.
2. **The forward window is not yet decidable.** The verdict counts only independent bets from
   2026-10-02: 1/20 at 1d, about 19 trading days short; 0/20 at 5d (about 99 short), 20d about
   399, 60d about 1199, 250d about 4999. Until then neither the page nor the research page
   claims "edge" or "no edge".
3. **No directional edge in the historical holdout.** Across the five horizons direction matched
   "always long" day by day (+0.0pp) and the Brier skill score was negative — that record cannot
   serve as a selection basis.
4. **The Shanghai gold premium is unavailable.** SGE AU9999 has no public key-free interface; the
   row says "unavailable + reason" and invents nothing.
5. **Web search is off by default.** It uses MiMo's plugin-style `web_search`, not a generic
   OpenAI capability; with the plugin disabled the endpoint returns `HTTP 400 · web search tool
   found in the request body, but webSearchEnabled is false` (reproducible). To enable it:
   `LLM_SEARCH_ENABLED=true` plus an endpoint with the plugin switched on; while off,
   institutional views fall back to the RSS news window and no doomed request is sent.
6. **Geopolitical risk strength is a corpus proxy** (share of related coverage in recent news),
   not an official index. The official daily GPR series is on the monitor table as an
   information row, but it does not enter composition until it clears the gates; the two are
   never mixed.
7. **No authentication, no multi-tenancy.** Every endpoint is public, including
   `POST .../refresh`, which triggers paid LLM calls.
8. **Not a trading system.** No brokerage, no orders, no custody; every output carries a
   disclaimer.

---

## 🚀 Quick start

### Requirements

| Dependency | Version | Purpose | Check |
|---|---|---|---|
| Node.js | ≥22.22.2 (or 24.15+/26+) | frontend runtime incl. npm. The floor comes from the strictest dependency in the lockfile (jsdom `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0`); Node 22.2.0 runs, but Vite prints a version warning | `node -v` |
| Python | 3.11 - 3.12 | backend runtime | `python --version` |
| SQLite | bundled with Python | storage: single file `backend/goldmind.db`, **zero install, zero config** | nothing to check |
| Google Chrome (or Edge) | any recent version | browser E2E reuses the locally installed Chrome; without Chrome, Windows' built-in Edge works (`E2E_BROWSER=msedge`). Neither path **downloads** Playwright browsers | open Chrome → `chrome://version` |

### Local development (the documented path: zero-config SQLite)

#### 1. Get the code

```bash
git clone https://github.com/JasonBuildAI/GoldMind.git
cd GoldMind
```

#### 2. Install dependencies

**Backend:**

```bash
cd backend

# create a virtualenv (recommended; the .venv below is this one)
python -m venv .venv

# activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# install
pip install -r requirements.txt
```

> **Versions are pinned** (`==`, not `>=`), pinned to the versions the tests actually ran
> against. Loose ranges mean `pip install` can pull a breaking major any day, and you only find
> out in deployment. Same on the frontend — `package-lock.json` is committed, so use `npm ci`,
> not `npm install`.

**Frontend:**

```bash
cd app

# use ci rather than install: strictly lockfile-driven and reproducible
npm ci
```

#### 3. Configure (only the three LLM values are required)

```bash
cd backend
cp .env.example .env
```

Open `backend/.env` and fill in three values. The database needs nothing — SQLite is the default:

```ini
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.deepseek.com/v1   # any OpenAI-compatible endpoint
LLM_MODEL=deepseek-chat
```

Common providers (pick one; the endpoint must speak the OpenAI protocol):

| Provider | `LLM_BASE_URL` | `LLM_MODEL` |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Ollama (local) | `http://localhost:11434/v1` | `qwen2.5:14b` |
| Xiaomi MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v2.6-flash` |

> ⚠️ Keys live only in `.env` (git-ignored): never in the repo, logs or commits. To check your
> environment, run `python scripts/verify_setup.py` (read-only, no DB, no network).
> Every other optional setting (scheduler, rate limits, quant backfill years, web-search switch)
> is commented in `backend/.env.example`; **the defaults just work**.

#### 4. Initialise the database (SQLite, zero config)

```bash
cd backend

# create tables + fetch and fill recent history (needs internet access to public sources)
python init_db.py

# tables only, no data: a few seconds, works offline
SKIP_SEED=1 python init_db.py
```

`init_db.py` creates `backend/goldmind.db` and all tables, then tries Sina Finance → Eastmoney →
Yahoo Finance for gold prices and the dollar index. Total failure is not fatal: rerun
`python seed_data.py` later.

**Upgrading an existing database to 2.0.1:**

```bash
cd backend

# institutional views: add as_of_date / source and copy real forecasts from legacy alias rows
# (add-only; no row is ever deleted)
python scripts/migrate_institution_views.py --dry-run   # dry-run is the default; look first
python scripts/migrate_institution_views.py --apply
# rollback (drops the two columns; existing rows stay)
python scripts/migrate_institution_views.py --drop-columns

# quant engine: upgrade to the factor_observations / factor_observation_revisions /
# model_evaluations shape and backfill the ledger from existing observations (idempotent,
# add-only)
python scripts/migrate_quant.py --dry-run
python scripts/migrate_quant.py
# rollback (drops the three new tables and the quant columns on predictions; data survives)
python scripts/migrate_quant.py --drop --yes

# news digest: widen news_digest_items.url from VARCHAR(500) to TEXT (Google News
# article links exceed 500 chars; MySQL rejects the whole batch under VARCHAR;
# column type only, no row is deleted)
python scripts/migrate_news_digest_url.py --dry-run
python scripts/migrate_news_digest_url.py --apply
# rollback (refuses when any url is longer than 500 chars — never truncates data)
python scripts/migrate_news_digest_url.py --rollback
```

> The revision ledger is the prerequisite for `--as-of` rebuilds. For backfilled rows,
> `recorded_at` is the day the row **entered this system**; historical backfill happens in one
> go, so asking for an earlier date returns an empty panel — that is the **correct** answer, not
> a bug.

#### 5. Run the services

Two terminals — there is **no** `start_all.ps1` one-liner:

```bash
# terminal 1: backend (from backend/)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# terminal 2: frontend (from app/)
npm run dev
```

> You can skip the second terminal and run only the frontend: without a backend the page says
> "API unavailable" and shows no built-in numbers.

**Cold-start expectations:**

- The five analysis sections **will not be populated immediately**: with no cache they return
  empty and kick off a background analysis (the page says "AI analysis in progress; the first
  load can take 1–2 minutes"), then fill in. You can also trigger each section's re-run button.
- The quant forecast needs a multi-year factor backfill first; it stays "unavailable" until the
  fetch completes, then updates incrementally.
- The page polls the market endpoint every 30 seconds (paused while the tab is hidden, with an
  immediate catch-up on return); default limits are 60 req/min (6 req/min for LLM endpoints).
  429 / 5xx / network errors are retried with backoff (429 honours `Retry-After`), so normal
  browsing does not turn the page into a wall of failures.

**URLs:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

#### 6. Zero-key self-check (no LLM key required)

No API key, but still want to run the whole thing? The repo ships a fake OpenAI-compatible
service; with SQLite it drives the entire "news → analysis → cache → page" path without spending
quota or touching the internet.

```powershell
# terminal 1: fake LLM (OpenAI-compatible, pick any port)
cd backend
.venv\Scripts\python.exe scripts\dev_mock_llm.py --port 8099

# terminal 2: SQLite tables + deterministic seed data (offline, repeatable), then point the
# backend at the fake LLM
cd backend
$env:DATABASE_URL = "sqlite:///./goldmind.db"
.venv\Scripts\python.exe scripts\dev_seed_sqlite.py --db goldmind.db
$env:LLM_API_KEY  = "zero-key"                          # placeholder, not a real key
$env:LLM_BASE_URL = "http://127.0.0.1:8099/v1"
$env:LLM_MODEL    = "dev-mock"
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

# terminal 3: frontend
cd app
npm run dev
```

Open http://localhost:5173: the five analysis sections show the fake LLM's sample content. The
quant sections compute for real and need real public market data (no key) — if data is missing,
follow the page's "re-fetch" prompt, or seed real history via step 4.

> This is also exactly what `npm run test:e2e` automates. For a real LLM, fill the three values
> in `backend/.env`; environment variables win over `.env`, so the self-check never touches your
> real configuration.

### Optional: MySQL / Docker (not exercised by this repository)

The quick start, gate commands and CI in this README go through **SQLite only** — the only
reproduction path covered by this repo's tests. Two optional MySQL/container assets remain for
people who need them, with **no guarantee they work out of the box at this version**:

- `docker-compose.yml` + `backend/schema.sql`: a three-container setup (mysql / backend /
  frontend). MySQL is initialised from `schema.sql`; the backend's `DATABASE_URL` is injected by
  compose.
- Local MySQL: set
  `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/gold_analysis` in `backend/.env`,
  then `python init_db.py` (the MySQL path creates the database first, then runs `schema.sql`).
- Backups: `python scripts/backup_db.py` does **not** run mysqldump for MySQL — it prints a
  command template and exits 2 (`-p` prompts for the password; it never enters shell history
  or the script). The SQLite path is backed up directly with per-table row-count verification.

> ⚠️ These paths **have not run the same gates** as the default SQLite path; known behavioural
> differences exist (ENUM storage, case-sensitive string comparison, transaction semantics).
> Before relying on them, establish a baseline with
> `GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" python -m pytest`.

---

## 🧪 Common commands

**The single source of truth for gate commands.** After any change, everything must be green
(the rules are in [`AGENTS.md`](AGENTS.md)).

### Backend

```bash
cd backend

# install (first time)
pip install -r requirements.txt -r requirements-dev.txt

# config-level self-check (read-only: no DB, no network; failures print the fix, exit code 0/1)
python scripts/verify_setup.py

# back up the database: SQLite is copied via the backup API with per-table row-count
# verification (default output backend/backups/, gitignored); MySQL is not run here —
# the script prints a mysqldump template and exits 2 instead of pretending success
python scripts/backup_db.py
python scripts/backup_db.py --out D:/goldmind-backups

# data sanity: future dates / invalid values / cross-store consistency (report only, exit 0/1)
python scripts/check_data_sanity.py
python scripts/check_data_sanity.py --strict   # cross-store drift also fails
python scripts/check_data_sanity.py --fix      # delete future-dated rows (irreversible: back up first!)

# tests — the full gate
python -m pytest

# one layer at a time
python -m pytest tests/unit          # unit: no DB, no network
python -m pytest tests/integration   # integration: in-memory SQLite + fake LLM
python -m pytest tests/e2e           # end-to-end: the real usage order, chained

# optional: rerun under the MySQL dialect (**only if you truly need MySQL**; SQLite is the
# default and the CI convention). ENUM storage, JSON columns and string case-sensitivity all
# differ. Point it at a **separate test database**: the suite truncates every table.
GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" \
    python -m pytest

# Test-database guard: the database name above **must contain "test"**, otherwise the suite
# refuses to start. The suite drops/clears every table it connects to; on 2026-10-02 it was
# once pointed at the dev database gold_analysis and wiped 9 business tables. Leave it unset
# to use in-memory SQLite (the default, safe path).

# static check: full syntax
python -m compileall -q app

# do the API docs (both languages) still match the router table?
python scripts/gen_api_doc.py --check     # exit code 1 when stale
python scripts/gen_api_doc.py             # regenerate docs/API.md and docs/en/api.md

# database init (SQLite: tables + history; the file is created automatically)
python init_db.py
SKIP_SEED=1 python init_db.py        # tables only, no data (works offline)

# fix enum values in old databases (idempotent; only affects databases created by early schema.sql)
python scripts/fix_enum_columns.py --dry-run
python scripts/fix_enum_columns.py

# one manual factor-sync round (first run backfills QUANT_HISTORY_YEARS, default 10; then increments)
python -c "from app.database import SessionLocal; from app.services.quant.sync import run_sync; db=SessionLocal(); print(run_sync(db, force=True).to_dict()); db.close()"

# stretch the historical panel: 20 years by default; --dry-run prints what is missing, writes nothing
python scripts/backfill_quant.py --dry-run
python scripts/backfill_quant.py --apply --years 20

# quant research bench: pre-registered candidates × horizons × three sample periods (reads the DB)
python scripts/quant_lab.py
python scripts/quant_lab.py --out docs/specs       # output dir (quant_lab.md / quant_lab.csv)
python scripts/quant_lab.py --horizons 20,60       # subset of horizons
python scripts/quant_lab.py --group calibration    # one candidate group (repeatable)
python scripts/quant_lab.py --as-of 2026-09-01     # rebuild the panel as seen that day
python scripts/quant_lab.py --holdout-start 2023-10-02   # reproduce a historical verdict

# factor gate: the three gates over candidates (--include-holdout is off by default, to respect
# the pre-commitment)
python scripts/screen_factors.py
python scripts/screen_factors.py --horizons 20,60 --as-of 2026-09-01
```

### Frontend

```bash
cd app

# install
npm ci

# build + type check — the full gate
npm run build

# static check
npm run lint

# unit + integration tests (vitest + Testing Library)
npm test

# browser end-to-end (Playwright) — requires npm run build first
npm run test:e2e

# local development
npm run dev

# re-shoot the 14 README screenshots (needs the real stack running: backend 8000 + frontend 5173)
node scripts/capture_screenshots.mjs
# optional: SCREENSHOT_BASE_URL / SCREENSHOT_OUT / SCREENSHOT_BROWSER=chrome|msedge|chromium
```

### Browser end-to-end tests

`npm run test:e2e` really starts three services and drives a real browser:

1. a fake LLM service (`backend/scripts/dev_mock_llm.py`, OpenAI-compatible, no quota),
2. the real backend (uvicorn + SQLite, seeded by `backend/scripts/dev_seed_sqlite.py`),
3. the production build (`vite preview`, proxying `/api` to the backend).

It reuses the locally installed Chrome and **does not download** Playwright browsers; on Windows
without Chrome, the built-in Edge works (`E2E_BROWSER=msedge`). If your Python is not on `PATH`,
point `E2E_PYTHON` at it:

```powershell
$env:E2E_PYTHON = "path\to\python.exe"
cd app
npm run build
npm run test:e2e              # default: reuse local Chrome

$env:E2E_BROWSER = "msedge"   # no Chrome: use local Edge
npm run test:e2e
```

> The E2E run uses an isolated database and cache directory (`backend/e2e.db`,
> `backend/e2e-cache/`) and never touches your development data; both are git-ignored.

### End-to-end smoke test (real LLM)

```bash
cd backend
python scripts/smoke_llm.py
```

> ⚠️ Requires `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` in `backend/.env` and really spends
> quota. It probes auth, `max_tokens` and Chinese JSON output; web search is probed only when
> `LLM_SEARCH_ENABLED=true` (skipped by default). Results land in
> `backend/scripts/smoke_llm_result.json` (git-ignored).

### Continuous integration (GitHub Actions)

The default branch only accepts green merges: `.github/workflows/ci.yml` runs three parallel
jobs on PRs and pushes to `main`, using exactly the gate commands above —

| Job | Runs | Environment |
|---|---|---|
| `Backend (pytest)` | `python -m pytest` | Python 3.11 + in-memory SQLite (no MySQL) |
| `Frontend (lint + test + build)` | `npm run lint` / `npm test` / `npm run build` | Node 22 |
| `Browser E2E (Playwright)` | `npm run test:e2e` | Python 3.11 + Node 22 + Chromium + fake LLM |

In CI the E2E job passes `E2E_BROWSER=chromium` into `app/playwright.config.ts` and installs the
browser via `npx playwright install --with-deps chromium`; locally the variable stays empty so
the installed Chrome is reused, or set it to `msedge` for Windows' built-in Edge.

Dependency updates go through `.github/dependabot.yml`: pip / npm / github-actions each open a
small number of PRs weekly, **never auto-merged** — every PR still has to pass the three checks,
and a human decides when to merge.

> Branch protection (required checks, PR-only merges) is a GitHub repository setting, not
> version-controlled; enable it under Settings → Branches. After the workflow has succeeded
> once, tick the three checks as required.

### Troubleshooting

- **httpx raises `Invalid port: ':1]'` or `Missing dependencies for SOCKS support`**
  — the machine has proxy environment variables (`ALL_PROXY` / `HTTP_PROXY` …) or `NO_PROXY`
  contains `[::1]`, which httpx cannot parse. Clear them before running tests:

  ```powershell
  $env:ALL_PROXY=''; $env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:NO_PROXY=''
  ```

- **Tests report `no such table`** — tests use in-memory SQLite, so this should not happen; if
  it does, check whether you bypassed `backend/tests/conftest.py`'s fixtures.

- **Windows console raises `UnicodeEncodeError: 'gbk' codec can't encode ...`** — a GBK console
  cannot print non-GBK characters such as `−` or `≈`. The repo's entry scripts handle this
  contract; for your own one-off scripts use `python -X utf8 script.py`, or write results to a
  UTF-8 file.

- **`--as-of` returns an empty panel** — first check the revision ledger is backfilled:
  `python scripts/migrate_quant.py --dry-run` prints how many rows are missing. Ledger rows from
  the historical backfill carry the backfill day, so earlier dates correctly return empty.

- **Whole sections fail to "analyse / fetch", and a refresh sometimes fixes it** — the error text
  now distinguishes the causes:
  - *Too many requests*: the dashboard polls every 30 s (paused when hidden) and 429s are retried
    with backoff. If it persists, multiple tabs or clients share one backend's rate budget; raise
    `RATE_LIMIT_PER_MINUTE`.
  - *Data tables missing … run `python init_db.py`*: the API answers **503** (no longer a bare
    500) with the fix command, and startup logs a `[启动自检]` line. Rebuild, then backfill.
  - The quant section's "missing gold price series" has one more cause: Yahoo Finance rate-limits
    this host (`YFRateLimitError: Too Many Requests`). The engine then falls back to the locally
    synced `gold_prices` / `dollar_index` tables (source labelled "本地行情表…兜底") instead of
    going dark.

- **Tests refuse to start with "database name does not contain test"** — that is the guard, not a
  bug: the suite drops every table it connects to. Point `GOLDMIND_TEST_DATABASE_URL` at a
  dedicated database whose name contains `test`, or leave it unset for in-memory SQLite.

---

## 🗂️ Directory layout

```
GoldMind/
├── app/                          # frontend (React 19 + TypeScript + Tailwind)
│   ├── src/
│   │   ├── sections/            # the seven page sections, each with its tests
│   │   ├── research/            # research page: pre-registered evaluation, verdict window, bins
│   │   ├── components/          # reusable components (incl. the forecast-date column)
│   │   ├── layout/              # masthead / footer
│   │   ├── services/            # API client and types (api.ts)
│   │   └── test/                # test fixtures
│   ├── scripts/
│   │   └── capture_screenshots.mjs  # README screenshots: asserts real content, never a blank shot
│   └── package.json
├── backend/                      # backend (FastAPI + SQLAlchemy; SQLite single file by default)
│   ├── app/
│   │   ├── services/            # business logic
│   │   │   ├── llm_provider.py                     # **the only LLM entry point**
│   │   │   ├── institution_prediction_service.py   # institutional views (incl. registry)
│   │   │   ├── news_digest.py                      # message board: crawl / deterministic scoring / per-window top 10 (no LLM)
│   │   │   ├── analysis_input.py                   # input packet: merged news + price context + capability note
│   │   │   └── quant/                              # quant engine: sources / derive / storage /
│   │   │                                           #   sync / engine / decompose / scenarios /
│   │   │                                           #   backtest / monitor / screen /
│   │   │                                           #   preregistered / stats / service
│   │   ├── routers/             # API routes
│   │   ├── models/ schemas/     # data models and response contracts
│   │   ├── tasks/ scheduler.py  # scheduled jobs (incl. the single timezone rule)
│   │   └── utils/timeutil.py    # **the only source of "now" and "today"**
│   ├── scripts/                 # migrations, backfill, research bench, factor gates, doc gen,
│   │                            # smoke tests and dev tools
│   ├── tests/                   # unit / integration / e2e
│   ├── schema.sql               # MySQL (optional) DDL; SQLite goes through model create_all
│   ├── goldmind.db              # default SQLite database (runtime, git-ignored)
│   └── requirements*.txt
├── docs/                         # Chinese docs (authoritative)
│   ├── en/                      # English mirror, one-to-one with the Chinese versions
│   ├── specs/                   # per-round specs and plans (records, not a second authority)
│   ├── 00-产品方向.md · 10-密钥与隐私.md · 20-前端设计规范.md
│   ├── ARCHITECTURE.md · API.md
│   └── images/screenshots/      # README screenshots (generated by capture_screenshots.mjs)
├── .github/
│   ├── workflows/ci.yml          # CI gates: backend / frontend / browser E2E
│   └── dependabot.yml            # dependency updates
├── AGENTS.md                     # how we work: rules, gates, process
├── CHANGELOG.md / CHANGELOG_EN.md
├── CONTRIBUTING.md / CONTRIBUTING_EN.md
├── README.md / README_EN.md
└── docker-compose.yml            # optional path (not exercised by this repo)
```

---

## 🗺️ Documentation map

The single "what to change → what to read" map. The Chinese version is authoritative; the
English one mirrors it.

| Document | English | Contents | Read it when |
|---|---|---|---|
| [`AGENTS.md`](AGENTS.md) | — (Chinese only) | how we work: rules, gates, process | before touching anything |
| [`docs/00-产品方向.md`](docs/00-产品方向.md) | [`docs/en/product-direction.md`](docs/en/product-direction.md) | what the product should be; **current vs target** | before changing requirements |
| [`README.md`](README.md) | [`README_EN.md`](README_EN.md) | layout, commands, configuration (this file) | when looking for a command or setting |
| [`docs/10-密钥与隐私.md`](docs/10-密钥与隐私.md) | [`docs/en/secrets-and-privacy.md`](docs/en/secrets-and-privacy.md) | key handling rules and the historical leak | before touching config/keys |
| [`docs/20-前端设计规范.md`](docs/20-前端设计规范.md) | [`docs/en/frontend-design.md`](docs/en/frontend-design.md) | frontend visual language: tokens, typography, copy rules | before UI changes |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | [`docs/en/architecture.md`](docs/en/architecture.md) | architecture (section 11 covers the quant engine) | before structural changes |
| [`docs/API.md`](docs/API.md) | [`docs/en/api.md`](docs/en/api.md) | API spec (**both generated from the router table**) | before changing endpoints |
| [`CHANGELOG.md`](CHANGELOG.md) | [`CHANGELOG_EN.md`](CHANGELOG_EN.md) | what changed per release | before upgrading |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | [`CONTRIBUTING_EN.md`](CONTRIBUTING_EN.md) | contribution process | before opening a PR |
| [`docs/specs/`](docs/specs/) | — (Chinese only) | per-round specs and plans (records, not a second authority). Quant trail: `2026-10-02-量化策略提升路线图.md`, `2026-10-02-研究台报告.md`, `2026-10-02-量化引擎第三轮预注册.md`, `2026-10-02-量化引擎口径一致性修正.md` | when tracing a decision |

> 📌 `docs/API.md` and `docs/en/api.md` are **not hand-written** — they are generated from the
> FastAPI router table by `backend/scripts/gen_api_doc.py`, and
> `backend/tests/integration/test_api_doc.py` compares them in the gate: change a route without
> regenerating and the gate goes red.

---

## 🔄 Workflow

1. **Collection**: Tencent Finance real-time gold; Sina Finance ICE dollar index; history backfill
   from Sina / Eastmoney / Yahoo; news via RSS
2. **Persistence**: prices, the dollar index and news go into SQLite (single file by default;
   `DATABASE_URL` switches to MySQL)
3. **Analysis**: five services build prompts → one LLM call each (endpoint from `LLM_*`) → parse JSON
4. **Quant**: public sources → factor observations (current value + revision ledger) → rolling z →
   per-horizon weights → one calibrated distribution → walk-forward backtest and monitor table
5. **Caching**: two levels, in-memory + JSON files (2-hour TTL), surviving restarts and shared
   across processes
6. **Presentation**: the frontend polls the market endpoint every 30s (paused while the tab is hidden); analyses are fetched on
   demand; a stored quant forecast carries the measured skill of its own horizon

---

## 🤖 About the analysis services

Early docs called these five services "LangChain agents"; that never matched the implementation.
They are **independent single-turn LLM calls**: no inter-agent communication, no shared state,
linked only through the cache and the database. Every client is constructed through
`backend/app/services/llm_provider.py`.

| Service | Code | Input | Output |
|---|---|---|---|
| Bullish factors | `app/services/bullish_factor_service.py` | last 24h news + gold price | 5 bullish factors + summary |
| Bearish factors | `app/services/bearish_factor_service.py` | last 24h news + gold price | 5 bearish factors + summary |
| Institutional views | `app/services/institution_prediction_service.py` | last 30 days of news + search | each institution's latest verifiable forecast (date + source) |
| Investment advice | `app/services/investment_advice_service.py` | market state + factors + views | three strategies + risk notes |
| Market summary | `app/services/market_summary_service.py` | all of the above | core logic + risks + judgement |

**Model**: decided by `LLM_MODEL` in `backend/.env` (same for the provider — see "Local
development"); the model name in the footer comes from `/health`'s `ai_config` and is never
hard-coded.

**Degradation**: when a data source or web search is unavailable, a service returns an explicit
"unavailable" status and falls back to database / RSS content — it **never** invents data.

When the frontend has no data it **shows "temporarily unavailable" with the reason** and no
built-in numbers or conclusions. This used to be documentation only: each section carried its
own hard-coded fallback (gold 2823, targets 5400/5000/4500/2700, a 14-point price series …) and
rendered it as real content whenever an API failed. All those constants are gone, and tests pin
"no built-in copy on failure".

**Removed**: the early `backend/app/agents/` package (`BaseAgent` / `MarketAnalyzerAgent` /
`NewsAnalyzerAgent`) was never instantiated anywhere and has been deleted.

---

## ⚠️ Honest statement (implementation boundaries)

This section is for anyone whose expectations come from the project description. The following
capabilities **do not exist**; please do not read the project as if they did:

| Rumoured capability | Reality |
|---|---|
| Multi-agent collaboration | 5 **independent single-turn LLM calls**, not agents collaborating: build prompt → `llm.invoke(prompt)` → parse JSON. No tool-calling loop, no agent messages |
| RAG / vector search | no vector store, no embeddings, no retrieval step. Prices and news are pasted into the prompt context |
| ReAct reasoning loop | not implemented; no Thought / Action / Observation cycle |
| Live web search | off by default (`LLM_SEARCH_ENABLED=false`). It uses MiMo's plugin-style `web_search`, not a generic OpenAI feature; with the plugin disabled the endpoint returns `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`, and the service falls back to the RSS news window |
| Sentiment analysis | `sentiment` is always `NEUTRAL`, kept only for response-shape stability; the page shows no sentiment conclusions |
| Redis / message bus / WebSocket / K8s / WAF / auth middleware | none. Caching is in-memory + JSON files |
| Trade execution | no broker, no orders, no custody |
| A quant forecast with a statistical edge | **the forward window is not decidable yet** (1/20 bets at 1d, 0/20 elsewhere). In the historical holdout the direction matched "always long" day by day (+0.0pp) with a negative Brier skill score; the page and the research page report this as-is instead of overselling the model |

**"A section says unavailable" is designed behaviour, not a bug**: reasoning models share
`LLM_MAX_TOKENS` (default 8192) between thinking and output. That budget truncates large JSON
such as the three-strategy payload, parsing fails, and the section honestly reports
"investment strategy unavailable" instead of showing a fabricated strategy (old versions pinned
4096, so this section stayed empty for a long time. Raising `LLM_MAX_TOKENS` on the deployment
side fixes it; 32768 returned reliably during this repo's development). Endpoints also carry
content filters and occasionally return `finish_reason=content_filter` (message: "The request
was rejected because it was considered high risk"); the backend retries once and then reports
"unavailable", and `finish_reason` plus token usage are in the logs for diagnosis.

**Why so verbose**: the project's core promise is "**no fabrication**". When a source or a search
is unavailable, it says so and why — instead of letting the model invent institutional target
prices, central-bank purchases or price levels from memory. Better an honest "data unavailable"
than a confident lie.

---

## 🤝 Contributing

All forms of contribution are welcome! See the
[contribution guide](./CONTRIBUTING_EN.md) ([中文](./CONTRIBUTING.md)) to get involved.

### Contributors

<a href="https://github.com/JasonBuildAI/GoldMind/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=JasonBuildAI/GoldMind" alt="Contributors" />
</a>

---

## 📄 License

Released under the [MIT License](./LICENSE).

---

## 🙏 Acknowledgements

- Any OpenAI-compatible LLM endpoint (development used [Xiaomi MiMo](https://platform.xiaomimimo.com/)) — language model and web-search capability
- [FastAPI](https://fastapi.tiangolo.com/) — high-performance web framework
- [React](https://react.dev/) — frontend UI framework
- US Treasury, NY Fed, CFTC, Yahoo Finance, Sina Finance and Iacoviello & Papaioannou (GPR) — key-free public data

---

## 📧 Contact

Questions, suggestions or collaboration ideas:

- 🐛 **Issues & ideas**: please open a [GitHub Issue](https://github.com/JasonBuildAI/GoldMind/issues)

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/JasonBuildAI">JasonBuildAI</a></sub>
</p>
