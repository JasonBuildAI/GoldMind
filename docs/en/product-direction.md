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
| Gold price and dollar index collection | Tencent Finance real-time gold price; Sina Finance ICE dollar index; historical backfill supports three sources: Sina / Eastmoney / Yahoo; every price carries its `basis` (realtime quote / daily close / quant benchmark), source and as-of date, and a same-day realtime-vs-close divergence above 3% is named by the data sanity check (2.0.2 items 1 and 2) |
| Historical data storage | A single SQLite file by default (`backend/goldmind.db`), two tables: `gold_prices` / `dollar_index`; `DATABASE_URL` can switch to MySQL (not exercised in this repository) |
| Bullish/bearish factor analysis | Based on the last 24 hours of news (high-authority message-board items + RSS, deduplicated by normalised URL; each prompt line carries a title plus a cleaned, truncated summary), calls the LLM to generate 5 bullish + 5 bearish factors, with caching |
| Institutional views | Scans the last 30 days of news (`INSTITUTION_NEWS_LOOKBACK_DAYS`) + (web search) and compiles the **most recent verifiable** prediction from Goldman Sachs / UBS / Morgan Stanley / Citi, labelled with the prediction date and source; an empty price target never overwrites an existing real record |
| Message board | Crawls four categories of high-authority sources — central banks / wire services / industry bodies / professional financial media (13 built-in, verified working; `NEWS_DIGEST_SOURCES` overrides them) — for gold-related headlines; scores them deterministically by source authority / gold relevance / same-story coverage / recency (no LLM), and shows the Top 10 in each of three windows (24h / 7d / 30d); items expand to a summary and same-story reports, link to the original article, and can be crawled manually; when nothing is available it says so, with the reason; these high-authority items also feed the news input of the factors / institutional views / advice / summary services (`services/analysis_input.py`) |
| Chinese for messages | The source pool is all English RSS, so each crawl automatically translates a batch into a **Chinese title plus a two-to-three sentence Chinese brief** (one LLM call per crawl, only untranslated items; `NEWS_TRANSLATE_ENABLED` / `NEWS_TRANSLATE_BATCH` tune it). The Chinese may only **condense facts the source summary already states** — no numbers, institutions or background the source never mentioned. Translations are stored alongside the English original and shown together so a reader can check them item by item; when translation is impossible the page says "Chinese translation unavailable (reason)" instead of inventing Chinese; Chinese never feeds scoring, clustering or ordering, and never enters an analysis prompt |
| Investment advice | Combines market state, bullish/bearish factors, institutional views and recent news to generate three tiers of strategy: conservative / balanced / opportunity |
| Market summary | Outputs the core logic, the main risks, institutional price targets and an overall judgement |
| Scheduled refresh | APScheduler: prices daily at 06:30; news and AI analysis every even hour; the message board at minute 25 of every hour; missed date jobs are caught up at start-up and every job runs with `coalesce` + `misfire_grace_time` (2.0.2) |
| Fully automatic operation (2.0.2) | `backend/.env` is the only manual input: the bootstrapper creates the schema, migrates, backfills and warms the first analyses (`AUTO_BOOTSTRAP`); LLM settings hot-reload (`CONFIG_WATCH`); a daily automatic backup (7 SQLite copies) and data sanity check run on their own (`AUTO_BACKUP`); `init_db.py` / `backfill_quant.py` / `migrate_*.py` are optional ops tools now - not using them loses no functionality |
| Source availability board | `GET /api/gold/sources/status` aggregates each fetch channel's last attempt (ok / no data / failed + reason); `/health` exposes the bootstrap progress (`bootstrap`) and the hot-reload state (`config_watch`) |
| Quant prediction engine | 14 factors covering four categories of drivers (monetary policy and rates / safe-haven and credit / supply-demand structure / market and technicals), all from free public data sources and updated automatically on each source's own release cadence; rolling z-scores are combined into a score → **one calibrated distribution** over 1 / 5 / 20 / 60 / 250 trading days (intraday–1 week / 1–3 months / 6–18 months) (expected return μ, uncertainty σ, upside probability p = 1 − F̂(−μ/scale), the tail share of that same calibrated distribution); the direction = sign(μ), and the price target and range and the three scenarios are all derived from this one distribution — factor scores are uncalibrated inputs, and the "factor bias (uncalibrated)" row is listed separately for comparison only; **each horizon has its own dominant weights** (short horizons: capital flows and technicals; medium horizons: policy expectations and the dollar; long horizons: central-bank purchases and demand structure); the walk-forward backtest hit rate scores exactly this direction, compared against "always long / momentum / coin flip", with the uncalibrated score direction's record listed as a separate tier. Per-source failures are annotated on the page with the reason, and when fewer than 3 factors are available it says plainly that the "prediction is unavailable"; the 1-year horizon **stops publishing a direction** by the pre-registered rule (it matched "always long" day by day in the holdout and has no verifiable edge) and publishes only the fair-value deviation and the annual calibrated interval |
| Frontend dashboard | Vue 3 single-page dashboard (Pinia + Vite, two HTML entries): masthead + 7 sections (Conclusion / Market / Drivers / Messages / Quant Prediction / Strategy / Data & Methods) — Messages is a first-class section (`#messages`), not a block inside "Drivers" — with 30-second quote polling (paused while the tab is hidden); plus a separate "Research" page (`app/research.html`) showing the holdout evaluation of the pre-registered candidates. Visual language and component rules live in `docs/20-前端设计规范.md` |
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
| Event-conditioned distributions | Event tags (FOMC / CPI / NFP / central-bank decision / central-bank buying) shipped as deterministic rules with no calendar API; the "distribution conditioned on the event" needs a free, verifiable macro calendar that was not found on 2026-10-03, so it is **not landed**. |
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
   `https://api.xiaomimimo.com/v1` + an `sk-` key). The code has guarded this since
   2026-10-02: `backend/app/services/llm_provider.py` checks the combination when it
   builds the chat and search clients, logs one warning with the switch guidance
   (never the key itself), and `/health` reports `services.ai_config.token_plan_backend`.
3. **Chinese and Asian physical sources have to be re-measured.** Probed on 2026-10-03
   (re-run with `python scripts/probe_sources.py`): the Shanghai Gold Exchange Au99.99 daily
   series (`sge_gold`) is reachable and wired in, turning the "Shanghai premium" row from
   unavailable into a real calculation; the Sina / Tencent quote endpoints are reachable and in
   use; the Jin10 flash API (HTTP 502), FX168 RSS (connects but 0 items), MINING.COM (403) and
   Kitco (404) are unreachable and explicitly not landed. Sources change, so the conclusions
   only cover the measurement day. News remains mostly English-language financial media and can
   be reconfigured through `NEWS_RSS_SOURCES`.
4. **No auth by default, with an optional token.** All endpoints are publicly accessible,
   including `POST .../refresh`, which triggers paid LLM calls; since 2.0.2 a `REFRESH_TOKEN`
   can be set, after which POST refresh requires the `X-Refresh-Token` header.
   `LLM_DAILY_CALL_BUDGET` (default 200/day) additionally caps paid calls - once exhausted
   every block says "unavailable + reason" rather than inventing content.
5. **In the holdout the long-horizon coverage is still below nominal, and the direction has no edge**. The interval width has been calibrated to the empirical quantiles of historical walk-forward errors
   (recomputed 2026-10-02, holdout from 2023-10-02): the actual coverage of the 80% interval is 78.9% / 77.6% / 73.2% / 61.2% / 24.1% (1 day → 1 year);
   over the same holdout the direction hit rates are 56.3% / 62.2% / 68.2% / 83.3% / 100%, matching "always long" day by day (+0.0pp), with a negative Brier skill score.
   The 1-year horizon is the number-one problem: the systematic bias in μ cannot be repaired, and widening the interval does not buy better direction.
   The pre-registered verdict of 2026-10-02: 17 candidates × 5 horizons, none passed, so the live version is kept and labelled "no statistical edge" (that was `quant-v4`; the second round fixed the ACI
   mismatch on 2026-10-02 and moved it to `quant-v5`, which changed the interval values, and the third-round C2 candidate was likewise retired by its pre-registered bar; the same day's engine hardening moved it
   to `quant-v6` — alignment no longer drops observations dated on a non-trading day and the ACI alpha cap came down to 0.5, so hit rates and coverage changed again; the 2.0.2 release of 2026-10-03 then wrote the publication lag into the factor table (`publication_lag_days`, one business day for the three rate factors) and moved it to `quant-v7`, so the `quant-v6` and older records are no longer comparable); the page honestly shows the coverage
   side by side with the two benchmarks, always-long / momentum (see Section 11 of docs/ARCHITECTURE.md).
6. **The message board does not fetch full articles, and its Chinese covers titles and summaries
   only**. It uses only the title, summary and link that each source's RSS provides, does not
   bypass logins or paywalls, and sends readers to the original article through an external link
   that may or may not be reachable. The Chinese title and brief are generated by an LLM from
   exactly those two things (see the "Chinese for messages" row above) and may only condense what
   the source already states, so they read shorter than the article itself — that is the caliber,
   not a defect. Some outlets have no public RSS, so they are reached through Google News
   domain-scoped search; aggregator-routed items carry an explicit `via_aggregator` label, and
   when that entry point is unavailable those sources are counted as failures in the fetch
   report rather than replaced with other content.
7. **The global central-bank gold caliber is China only.** The WGC monthly central-bank page is
   reachable but has no free machine-readable feed (a public data-API path probed 404), and IMF
   SDMX / DataMapper answered 502 / a TLS handshake failure / 403 - neither offers a "free,
   machine-readable, repeatable" global series, so the `central_bank` factor stays as the
   People's Bank of China official reserves (a China caliber) and says so on the page instead of
   passing one country off as the world.

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
