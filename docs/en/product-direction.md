# Product Direction

> 🌐 [中文](../00-产品方向.md) | **English**

This document is the **single source of truth** for "what the product should do". `AGENTS.md` only covers how to work and does not repeat anything here.
The single source of truth for directories, commands and configuration is `README.md`.

> Status markers: **current** = already usable in the code; **planned** = intended but not yet built.
> A capability marked "planned" in the docs does not count as implemented — once any capability ships, change its marker here to "current".

---

## 1. What This Is

GoldMind is a **gold market analysis dashboard for individual investors**: it automatically collects the gold price and the dollar index,
uses a large language model to generate bullish/bearish factors, institutional views, investment advice and a market summary, and finally presents everything as a single-page dashboard.

It is **not** a trading system: it does not connect to brokers, does not place orders, and does not custody funds.

### Who It Is For

Individual investors, especially those who want to "open one page and see what happened in the gold market today,
and what the bullish and bearish arguments are".

### One-Sentence Criterion

> Open the homepage without clicking any button and you can see **today's** gold price, the dollar index,
> and a bullish/bearish analysis generated from **today's** news — and when a data source is unavailable,
> the page **says so explicitly** instead of passing off sample data as analysis results.

---

## 2. Current State (Implemented)

| Capability | Description |
|------|------|
| Gold price and dollar index collection | Tencent Finance real-time gold price; Sina Finance ICE dollar index; historical backfill supports three sources: Sina / Eastmoney / Yahoo |
| Historical data storage | A single SQLite file by default (`backend/goldmind.db`), two tables: `gold_prices` / `dollar_index`; `DATABASE_URL` can switch to MySQL (not exercised in this repository) |
| Bullish/bearish factor analysis | Based on the last 24 hours of news, calls the LLM to generate 5 bullish + 5 bearish factors, with caching |
| Institutional views | Scans the last 30 days of news (`INSTITUTION_NEWS_LOOKBACK_DAYS`) + (web search) and compiles the **most recent verifiable** prediction from Goldman Sachs / UBS / Morgan Stanley / Citi, labelled with the prediction date and source; an empty price target never overwrites an existing real record |
| Investment advice | Combines market state, bullish/bearish factors and institutional views to generate three tiers of strategy: conservative / balanced / opportunity |
| Market summary | Outputs the core logic, the main risks, institutional price targets and an overall judgement |
| Scheduled refresh | APScheduler: prices daily at 06:30; news and AI analysis every even hour |
| Quant prediction engine | 14 factors covering four categories of drivers (monetary policy and rates / safe-haven and credit / supply-demand structure / market and technicals), all from free public data sources and updated automatically on each source's own release cadence; rolling z-scores are combined into a score → **one calibrated distribution** over 1 / 5 / 20 / 60 / 250 trading days (intraday–1 week / 1–3 months / 6–18 months) (expected return μ, uncertainty σ, upside probability p = 1 − F̂(−μ/scale), the tail share of that same calibrated distribution); the direction = sign(μ), and the price target and range and the three scenarios are all derived from this one distribution — factor scores are uncalibrated inputs, and the "factor bias (uncalibrated)" row is listed separately for comparison only; **each horizon has its own dominant weights** (short horizons: capital flows and technicals; medium horizons: policy expectations and the dollar; long horizons: central-bank purchases and demand structure); the walk-forward backtest hit rate scores exactly this direction, compared against "always long / momentum / coin flip", with the uncalibrated score direction's record listed as a separate tier. Per-source failures are annotated on the page with the reason, and when fewer than 3 factors are available it says plainly that the "prediction is unavailable" |
| Frontend dashboard | React single page: masthead + 6 sections (Market / Bullish vs Bearish / Institutions / Strategy / Quant Prediction / Conclusion), with 10-second quote polling; plus a separate "Research" page (`app/research.html`) showing the holdout evaluation of the pre-registered candidates |
| Cache | Two-level cache: in-process memory + JSON files, supporting multiple processes and sharing across restarts |

**LLM provider**: not hardcoded — any OpenAI-compatible endpoint (OpenAI / DeepSeek / Qwen /
Kimi / Ollama / Xiaomi MiMo …) works, decided by `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`
in `backend/.env` (missing any one of the three counts as "unconfigured": each section honestly
shows "temporarily unavailable"), and constructed uniformly through
`app/services/llm_provider.py`.

---

## 3. Planned (Not Yet Implemented — Do Not Treat as an Existing Capability)

| Capability | Description |
|------|------|
| Multi-agent collaboration / ReAct / RAG | The current implementation is a **single-turn prompt call**: `llm.invoke(prompt)` → parse the JSON. There is no tool-calling loop, no vector retrieval and no inter-agent communication. The early `app/agents/` package was never instantiated and has been deleted. |
| User system and personalization | No login, no user profiles; "personalized advice" is actually a generic strategy in three tiers by risk preference. |
| Mobile | None. |
| Web search fallback plan | See the limitations in the next section. |

---

## 4. Known Limitations (Must Be Honestly Reflected in the UI and Docs)

1. **Web search is off by default**. It uses MiMo's plugin-style `web_search` tool (not a generic
   OpenAI capability) and must be explicitly enabled with `LLM_SEARCH_ENABLED=true` on an endpoint
   where the plugin has been enabled; otherwise the endpoint returns
   `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`
   (verified in practice; see `backend/scripts/smoke_llm.py`). Therefore, when search is
   unavailable, "Institutional Views" **can only fall back to the database and RSS news**, and
   must not fabricate institutional price targets from the model's impressions.
2. **Mind the usage terms of whichever endpoint you pick**. Before connecting, confirm the
   provider's terms allow backend calls. Example: the Xiaomi Token Plan terms restrict it to
   "programming tools only; use in custom application backends is prohibited", so using a `tp-`
   key for backend calls is outside those terms and risks the service being suspended or the key
   being banned; the compliant approach is a pay-as-you-go endpoint (for MiMo,
   `https://api.xiaomimimo.com/v1` + an `sk-` key).
3. **The news sources are mainly English financial media**. The built-in default RSS sources (FXStreet / MarketWatch /
   CNBC / WSJ) are the set verified as usable in practice; the public
   RSS addresses of the Chinese sources (Sina, FX168, Jin10) have all expired and can be configured
   yourself via `NEWS_RSS_SOURCES`.
4. **No auth, no multi-tenancy**. All endpoints are publicly accessible, including
   `POST .../refresh`, which triggers paid LLM calls.
5. **In the holdout the long-horizon coverage is still below nominal, and the direction has no edge**. The interval width has been calibrated to the empirical quantiles of historical walk-forward errors
   (recomputed 2026-10-02, holdout from 2023-10-02): the actual coverage of the 80% interval is 78.9% / 77.6% / 73.2% / 61.2% / 24.1% (1 day → 1 year);
   over the same holdout the direction hit rates are 56.3% / 62.2% / 68.2% / 83.3% / 100%, matching "always long" day by day (+0.0pp), with a negative Brier skill score.
   The 1-year horizon is the number-one problem: the systematic bias in μ cannot be repaired, and widening the interval does not buy better direction.
   The pre-registered verdict of 2026-10-02: 17 candidates × 5 horizons, none passed, so the live version is kept and labelled "no statistical edge" (that was `quant-v4`; the second round fixed the ACI
   mismatch on 2026-10-02 and moved it to `quant-v5`, which changed the interval values, and the third-round C2 candidate was likewise retired by its pre-registered bar); the page honestly shows the coverage
   side by side with the two benchmarks, always-long / momentum (see Section 11 of docs/ARCHITECTURE.md).

---

## 5. Explicitly Out of Scope

- No live trading, no order placement, no broker API integration.
- No user funds or account system.
- No "guaranteed returns" style statements; all AI output must carry a disclaimer.
- No fabricated data just to look good — prefer showing "data unavailable".

---

## 6. When Changing This Document

Change this file only when the product direction changes; when the implementation changes, change the design docs under `docs/` or `README.md`.
**Keep a single authoritative source per fact**; elsewhere, only point to it.
