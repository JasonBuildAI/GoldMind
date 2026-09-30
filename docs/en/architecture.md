# GoldMind Architecture

> 🌐 [中文](../ARCHITECTURE.md) | **English**

This document describes the **current implementation**. What the product should do is in
[`00-产品方向.md`](./00-产品方向.md), commands and configuration are in
[`../README.md`](../README.md), and the API specification is in [`API.md`](./API.md).

> This document used to be a 765-line "enterprise architecture whitepaper", much of which
> (Redis, message bus, WebSocket, K8s/Istio, WAF, auth middleware, RAG engine) **does not exist**
> in this project. It has now been rewritten to match the implementation; **every fact keeps a
> single source of truth**, and the capability list follows `00-产品方向.md`.

---

## 1. Components

```
┌──────────────┐   /api/**   ┌──────────────┐            ┌──────────────┐
│  Browser     │ ──────────► │  FastAPI     │ ─────────► │  MySQL 8     │
│  React 19    │             │  (uvicorn)   │            │  or SQLite   │
└──────────────┘             └──────┬───────┘            └──────────────┘
                                    │
                                    │ llm_provider (the only exit)
                                    ▼
                             ┌──────────────┐
                             │  Xiaomi MiMo │
                             │ OpenAI compat│
                             └──────────────┘
```

The frontend **always uses relative paths** `/api/**`:

- In development, `server.proxy` in `vite.config.ts` forwards them to `localhost:8000`
- In production, `location /api/` in `app/nginx.conf` forwards them to `backend:8000`

As a result the browser never makes cross-origin requests, and CORS only has to cover local
development addresses.

---

## 2. Directory layout

```
GoldMind/
├── AGENTS.md              how to work: rules, gates, process
├── README.md              directory, commands, configuration (single source of truth)
├── docs/
│   ├── 00-产品方向.md      what the product should do; current state vs goals
│   ├── 10-密钥与隐私.md    secret rules and handling of the historical leak
│   ├── ARCHITECTURE.md    this file
│   └── API.md             API specification
├── app/                   frontend (light research brief; visual and copy rules in docs/20-前端设计规范.md)
│   ├── src/sections/      six sections: market / bullish vs bearish / institutional views / investment strategy / quant prediction / conclusion
│   ├── src/layout/        header (wordmark, anchor navigation, data sources) and footer
│   ├── src/components/    in-section primitives (Section / StateBlock / tables / quotes ...)
│   ├── src/styles/        design tokens and base typography
│   ├── src/services/api.ts  the only HTTP exit
│   ├── src/contexts/      market data provider and polling
│   ├── src/components/ui/  only tabs.tsx remains
│   └── e2e/               Playwright end-to-end tests
└── backend/
    ├── app/
    │   ├── main.py        application entry, rate limiting, CORS
    │   ├── config.py      every configuration item (pydantic-settings)
    │   ├── database.py    engine and session (MySQL / SQLite dual support)
    │   ├── models/        ORM definitions of the 6 tables
    │   ├── routers/       4 router modules
    │   ├── services/      business logic (see below)
        │   └── utils/     rate_limit and so on
    ├── scripts/           smoke_mimo / dev_mock_llm / dev_seed_sqlite
    └── tests/             unit / integration / e2e
```

---

## 3. Analysis pipeline

**This is not a multi-agent system.** The five services each complete one independent single-turn
LLM call and do not communicate with each other:

```
MySQL(gold_news, gold_prices)
        │
        ▼
  assemble prompt ──► llm.invoke() ──► parse JSON ──► two-level cache ──► HTTP response
        ▲
        └── optional: MiMo web_search (the current credentials cannot use it, see below)
```

| Service | File | Output |
|---|---|---|
| Bullish factors | `services/bullish_factor_service.py` | 5 factors + summary |
| Bearish factors | `services/bearish_factor_service.py` | 5 factors + summary |
| Institutional views | `services/institution_prediction_service.py` | target prices and reasoning for the four major institutions |
| Investment advice | `services/investment_advice_service.py` | three tiers of strategy + risk warnings |
| Market summary | `services/market_summary_service.py` | core logic + risks + overall judgement |

### Behavior on a cache miss

When the cache is empty, `GET .../xxx-ai` does **not** call the model: it returns built-in default
content and triggers one background analysis, and the response carries
`metadata.status = "analyzing"`. What really calls the model is `POST .../refresh` or the background
task. On this basis the frontend uses a one-line notice to distinguish "real analysis" from
"default content".

---

## 4. LLM integration

Every client must be constructed through `app/services/llm_provider.py`; this is the **only exit**.
To switch provider, endpoint or model, change only `config.py` or `.env`.

Key design points:

- **httpx clients are passed explicitly** (`http_client` + `http_async_client`; `trust_env` is
  controlled by `MIMO_TRUST_ENV`). If the host sets a SOCKS proxy or has `[::1]` in `NO_PROXY`,
  httpx raises during **construction**; `ChatOpenAI` prepares both a sync and an async client, so
  supplying only the sync one still builds a default async client and reads the environment. The
  exception is swallowed by the layer above and replaced with defaults, which shows up as "the page
  has analysis content, but not a single model call ever happened".
- **The `web_search` tool is currently unavailable**: a Token Plan `tp-` key always gets HTTP 400
  from it (measurements in `scripts/smoke_mimo.py`). When search is unavailable the system falls
  back to the database and RSS, and **never fabricates data**.

---

## 5. Caching

Two levels, implemented in `services/cache_manager.py`:

| Level | Location | Notes |
|---|---|---|
| In-memory | in-process dict | the fastest; not shared across processes |
| File | `CACHE_DIR/*.json` | atomic write (temp file + rename); still hit after a restart |

TTLs are defined by two constants (`services/cache_manager.py`):

| Constant | Value | Purpose |
|---|---|---|
| `AI_ANALYSIS_CACHE_TTL` | 7200 (2 hours) | the five AI analysis results |
| `REALTIME_PRICE_CACHE_TTL` | 30 | real-time quotes (the cache for "fetch one external quote") |

**The analysis cache must be >= the scheduler's refresh interval.** When the cache expires, **one
user request triggers one on-demand paid LLM analysis** (see `get_xxx(use_cache=True)` in each
service), while the scheduler would refresh the same result on `UPDATE_AI_ANALYSIS_CRON` anyway:

```
TTL >= refresh interval  ->  by the time it expires the scheduler has almost always written a new result, no extra spend
TTL <  refresh interval  ->  every cycle triggers one extra paid analysis for nothing
```

Institutional predictions used to hard-code **3600** (1 hour) while the scheduler refreshed only
every **2 hours** — one extra analysis burned every cycle. Now all five services share the same
constant, and `tests/unit/test_cache_ttl_vs_schedule.py` parses the cron and guards this
relationship.

`CACHE_DIR` is configurable (default `backend/cache`); tests use their own directory. Cache files
are **not committed** (`.gitignore` ignores them).

---

## 6. Data model

| Table | Purpose |
|---|---|
| `gold_prices` | gold price OHLC, `date` unique |
| `dollar_index` | dollar index, `date` unique |
| `gold_news` | news; `published_at` is indexed |
| `market_factors` | bullish/bearish factors (separated by `type`) |
| `institution_views` | institutional views; `as_of_date` / `source` record the date each prediction was last verified and where the lead came from (`web_search` / `news_scan` / `legacy`); upgrading an old database goes through `scripts/migrate_institution_views.py` (adds columns / backfills data only, never deletes rows) |
| `predictions` | written on every refresh by the quant engine (`services/quant/service.py`): direction, horizon, base price, target price, score, expected return, uncertainty and model version |
| `factor_observations` | quant factor observations, unique on `(factor_key, obs_date)`; only successful observations are stored, failures are explained in the sync report |
| `model_evaluations` | walk-forward backtest results (hit rate / benchmark comparison / Brier / per-factor metrics); every evaluation appends one row |

> `update_logs` has been deleted: nothing wrote to it, read from it or exposed it, and the product
> direction never listed it as a goal, so it was a purely dead table. Likewise, consistency between
> `schema.sql` and the models is guarded by `tests/unit/test_schema_matches_models.py` — the two
> schemas once disagreed on the allowed values of enum columns, and MySQL compares ENUMs
> case-insensitively, which produced "writes go in, reads do not come out".

The engine supports both MySQL and SQLite: SQLite needs `check_same_thread=False`, and an in-memory
database additionally needs `StaticPool`, otherwise every connection sees its own separate empty
database.

> Tests run against in-memory SQLite by default, but production uses MySQL. The two differ in enum
> storage, JSON columns and string case comparison, so `conftest.py` keeps a
> `GOLDMIND_TEST_DATABASE_URL` switch that lets the same suite run against MySQL (point it at a
> separate test database; the cases truncate every table).

---

## 7. Configuration

Every configuration item lives in `app/config.py` and can be overridden directly with environment
variables. Commonly used items:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | local MySQL | can also point at SQLite |
| `MIMO_API_KEY` / `MIMO_BASE_URL` / `MIMO_MODEL` | — / Token Plan endpoint / `mimo-v2.6-flash` | LLM access |
| `MIMO_TRUST_ENV` | `false` | whether to read the host's proxy environment variables |
| `CACHE_DIR` | `backend/cache` | file cache directory |
| `NEWS_RSS_SOURCES` | four built-in sources | format `name\|URL,name\|URL` |
| `CORS_ALLOW_ORIGINS` | local development addresses | do not put `*` in it |
| `RATE_LIMIT_PER_MINUTE` | `60` | per-IP cap for regular endpoints |
| `RATE_LIMIT_AI_PER_MINUTE` | `6` | cap for endpoints that call the LLM |
| `SCHEDULER_ENABLED` | `true` | master switch for scheduled tasks |
| `SCHEDULER_TIMEZONE` | `Asia/Shanghai` | **the single time zone convention for the whole project**, see below |

### Time zone convention

`SCHEDULER_TIMEZONE` is not just the cron time zone; it is **the time convention of the entire
project**:

> Data is converted into it the moment it enters the system, and converted back only when it
> leaves.

This rule is not design fastidiousness — it was forced by two real incidents, and both only showed
up under particular deployments:

| Incident | Symptom |
|---|---|
| A scheduled task used `datetime.now().date()` for "today" | cron fires in UTC+8 but the container defaults to UTC, so the same quote was recorded as **the previous day** inside Docker |
| RSS's `published_parsed` is UTC and was stored directly with `datetime(*parsed[:6])` | the database stored UTC wall-clock time but read it back as local time, so the **"last 24 hours" window actually covered about 32 hours** |

The same root cause showed up once more: the frontend used
`new Date().toISOString().split('T')[0]` for "today", which is a **UTC date** — between 00:00 and
08:00 in UTC+8 it returns yesterday, and the real-time dollar index silently stops updating.

Ready-made entry points (do not invent new ones):

| What you need | What to use |
|---|---|
| The backend wants "now" / "today" | `app.scheduler.scheduler_now()` / `scheduler_today()` |
| An external timestamp (the UTC struct_time from RSS) | `app.services.news_service.to_local_naive()` |
| The trading day a data source reports (a string) | `app.scheduler.parse_source_date()` |
| The frontend needs to tell whether something is "today" | **do not compute it yourself** — use the trading-day field the backend provides (such as `DollarRealtime.date`) |

Forbidden: using `datetime.now().date()` for "today", `datetime.utcnow()`, or
`new Date().toISOString()` for a date. Tests construct scenarios from fixed instants instead of
depending on the clock when the tests run — this machine is in UTC+8, and many time zone bugs are
**impossible to catch** here.

---

### The query-parameter contract

**Nothing guarantees that parameter names match between the frontend and the backend**: the type
system does not cover URL strings, and FastAPI **silently ignores** query parameters that were never
declared. That is how one was missed in round 19:

```ts
`/api/gold/prices/correlation?days=${days}`   // the frontend was sending this all along
```

```python
async def get_correlation_data(limit: int = Query(...), include_realtime: bool = Query(...))
#                                            ^ days was never declared
```

`days=30` / `days=5` / `days=365` / passing nothing all returned exactly the same thing. The same
handler had earlier been fixed for `limit` (declared, validated, never used) — both times the two
ends of the parameter contract each wrote their own version, and neither side raised an error.

Hence two rules:

| Direction | Requirement | Who guards it |
|---|---|---|
| What the frontend sends | the endpoint must declare it | `tests/unit/test_api_params_contract.py` |
| What the endpoint declares | the function body must actually use it | same as above |

This guard only ensures the **names line up**; "the parameter really changes behaviour" is the job
of each endpoint's own behaviour tests (such as `test_correlation_days_actually_filters`).

---

## 8. Scheduled tasks

`app/scheduler.py`, APScheduler, time zone `Asia/Shanghai`:

| Task | Default cron | Notes |
|---|---|---|
| Update gold prices | `30 6 * * *` | daily at 06:30, skipped on weekends |
| Update the dollar index | same as gold prices | |
| Update news | even hours | RSS fetch |
| Update AI analysis | even hours | runs the 4 analysis services in sequence |
| Sync quant factors | `15 */2 * * *` | each source skips fetches that are not due yet, at its own cadence (`QUANT_ENABLED=false` turns it all off) |
| Recompute quant predictions | `45 */2 * * *` | recomputes the 1 / 5 / 20 / 60 / 250 trading-day predictions; backtests are throttled to 24 hours |

---

## 9. Request protection

Middleware in `app/main.py`, implemented in `app/utils/rate_limit.py`:

- **Rate limiting**: a sliding window per client IP; regular endpoints and endpoints that call the
  LLM are counted separately, and the latter has a stricter cap. `/health` is not rate-limited.
  Expired keys are cleaned up, so memory does not grow without bound.
- **CORS**: an explicit origin list; if `*` appears among the origins, the middleware forces
  credentials off.

> This project has **no authentication**. For a public deployment, add access control at the
> reverse proxy; otherwise anyone can trigger the `/refresh` endpoints, which consume LLM quota.

---

## 10. Deployment

`docker-compose.yml` starts three containers: `mysql` / `backend` / `frontend`(nginx).

- The backend entrypoint script waits for the database to become ready, then runs `init_db.py`, and
  then starts uvicorn
- The frontend serves the build output through nginx, with both `/api/` and `/health`
  reverse-proxied to the backend
- LLM credentials are injected through `backend/.env` (`MIMO_*`)

- On first start, MySQL executes `backend/schema.sql` (mounted read-only as
  `/docker-entrypoint-initdb.d/01-schema.sql`); the script carries its own `CREATE DATABASE` and
  `USE`, and everything uses `IF NOT EXISTS`, so it can run repeatedly

---

## 11. Quant prediction engine

`app/services/quant/`: turns "the four classes of factors that affect the international gold price"
(monetary policy and rates / hedging and credit / supply-demand structure / market and technicals)
into backtestable signals. The factor list, weights, direction priors and freshness caps are
defined **in one place only**, `app/services/quant/definitions.py`, and the API outputs according to
it — documentation does not copy a second version.

| Stage | Location | Key points |
|---|---|---|
| Data sources | `sources/*.py` | all free, no keys required (including the Treasury DTS TGA, the New York Fed RRP, CFTC open interest, Yahoo USDCNY); the HTTP client is injectable, and tests never really go online |
| Derivation | `derive.py` | raw series → factor values; units and conventions are fixed in this layer only |
| Persistence | `storage.py` | `factor_observations`, unique constraint `(factor_key, obs_date)`, idempotent |
| Sync | `sync.py` | per-source throttling (6h ~ 24h), incremental fetching, per-source degradation, and a sync report |
| Signals | `engine.py` | rolling z → direction alignment → weights by horizon (`definitions.horizon_weights`) → one calibrated distribution giving expected return, uncertainty, upside probability, target price and interval |
| Fair value | `decompose.py` | walk-forward expanding-window OLS (`log gold price ~ real rate + log dollar index + log central bank reserves + VIX`) splits the gold price into macro anchor + demand premium + risk premium + sentiment residual; deviation = market price / fair value − 1 |
| Scenarios | `scenarios.py` | quantiles of the predictive distribution N(μ, σ²) → Base [q25, q75] (50%) / Bull top 25% / Bear bottom 25%; the trigger and invalidation conditions are generated from this horizon's heaviest factor + the 200-day moving average |
| Backtest | `backtest.py` | walk-forward hit rate (scoring the calibrated direction) + three benchmarks + a separate score for the uncalibrated score direction + 80% interval coverage + segments split at 2022-01-01 + per-factor hit rate and IC |
| Monitoring | `monitor.py` | a weekly dashboard giving frequency / source / value / signal / data as-of date row by row; signal rules are centralised in `_rule`, informational rows have `signal=null`, and missing data is marked "unavailable + reason" |
| Exit | `service.py` | the scheduled task and `POST /api/gold/quant/refresh` share the same chain |

Three conventions that must not be broken:

1. **No look-ahead.** Rolling statistics and regression samples are all `shift`ed to before t; data
   sources published after the gold close (the Treasury yield curve, the New York Fed EFFR, CFTC
   positioning) are shifted wholesale by one business day by
   `sources/base.py::shift_to_next_trading_day`.
   Guard: `backend/tests/unit/quant/test_no_lookahead.py` — turn the data after t into garbage
   values, and the signal at t must be bit-for-bit unchanged.
2. **Never fabricate.** Fewer than 3 usable factors, a missing price series, or stale single-factor
   data (past that factor's update cadence) all return "unavailable + reason"; missing factors are
   renormalised over the remaining weights and are not treated as 0.
3. **Time flows in one time zone only.** Every "now" uses `app.utils.timeutil` (the scheduler time
   zone), the same convention as section 7.

Predictions have a single distribution exit (`engine.build_prediction_frame`): at time t,
μ = α + β·score (expanding-window OLS, with sample pairs satisfying s + h ≤ t),
σ = std(r_s − μ_s | s + h ≤ t) × q80(|r_s − μ_s| / (1.2816·σ_s)) (the standard deviation of the
**walk-forward prediction error**, with the width further calibrated by the error's **empirical
quantile** — normal quantiles are systematically too narrow at long horizons; when fewer than 60
realised errors exist it falls back to "the expanding standard deviation of realised h-day
returns", still using past data only), p_up = Φ(μ/σ).
Target price = base price ×(1+μ), 80% interval = μ ± 1.2816σ, three scenarios = quantiles of
N(μ, σ²), all derived from this single distribution; the "direction" on the page = sign(μ) (exactly
0 is recorded as "flat").
The factor-composite score is an **uncalibrated** input: it appears only in the factor table and the
"factor tilt (uncalibrated)" row, and backtests score it separately
(`metrics.score_direction_accuracy`). When there are fewer than 60 regression samples,
`expected_return` is NaN → the whole horizon returns "unavailable + reason"; it does not fall back to
"expected unchanged", and the sign of the score does not stand in for the direction. The actual
coverage of the 80% interval after empirical-quantile calibration (measured 2026-10-01):
full sample 78.1% / 77.3% / 75.8% / 76.7% / 61.0%, most recent 500 evaluable samples
70.2% / 66.0% / 64.4% / 55.0% / 27.6% (1 day → 1 year; before calibration
78.4% / 76.4% / 71.7% / 68.4% / 51.8% and 70.0% / 64.0% / 58.8% / 47.6% / 18.4%).
The 1-year horizon is still clearly low over the last two years: the average walk-forward error from
2023-10 to 2025-10 is +33.0%, i.e. the drift term (μ) underestimated the 2024–2025 rally —
interval-width calibration cannot compensate for the bias in the center; correcting μ again by the
expanding mean of the errors was tried (250-day coverage over the most recent 500 samples
27.6% → 41.6%), but the 1–60 day hit rates all dropped (e.g. 60-day 64.5% → 60.5%), so it was not
adopted, and the page shows coverage and benchmarks together, honestly
(see section 4 of docs/00-产品方向.md).
Guard: `tests/unit/quant/test_engine.py` (four criteria — direction / probability / σ / empirical
quantile, each mutation-verified), `tests/unit/quant/test_backtest_metrics.py`.

The display convention of the four-layer decomposition is fixed in one place, `decompose.py`: the
demand and risk premiums multiply in a chain (the risk premium takes "anchor + demand premium" as
its base), so that both "anchor + demand premium + risk premium = fair value" and "the three blocks
+ sentiment residual = market price" hold by construction; the regression coefficients at time t use
only realised samples with `s ≤ t−1`, and when fewer than 120 realised samples exist or any
regressor is missing it returns "unavailable + reason".
Guard: `backend/tests/unit/quant/test_decompose.py`.

Scenarios (`scenarios.py`) turn the same μ/σ into Base / Bull / Bear plus checkable trigger and
invalidation conditions; when σ is non-positive, the base price is missing or no factors are usable
it returns "unavailable + reason" without blocking the main prediction output.
Guard: `backend/tests/unit/quant/test_scenarios.py`.

The backtest (`backtest.py`) reports, beyond the hit rate, the actual coverage of the 80% nominal
interval (`metrics.interval_coverage_80`) and the `metrics.regimes` segment results split at
2022-01-01; when a segment has too few samples it gives only the sample count and the reason, and
never pads the numbers.
Guard: `backend/tests/unit/quant/test_backtest_metrics.py`.

The monitoring dashboard (`monitor.py`) covers 16 rows of metrics; usdcny / cny_gold / tga / rrp /
cftc_oi are monitor-only series, stored in the same table as the factors (`factor_observations`) but
not used in signal composition. The public endpoint for the Shanghai gold premium is unavailable in
practice, and its row honestly shows "unavailable + reason".
Guard: `backend/tests/unit/quant/test_monitor.py`.

---

## 12. Capabilities that explicitly do not exist

The following appeared in earlier documents but is not in the code:

Redis, message bus, WebSocket push, K8s / Istio, WAF, CSRF token, authentication/authorization
middleware, log tracing middleware, RAG (vector store / embedding / retrieval), ReAct reasoning
loops, multi-agent collaboration, TF-IDF / NER, news sentiment analysis (the `sentiment` field is
always `NEUTRAL`, only to keep the API shape stable).

The `app/agents/` package (`BaseAgent` / `MarketAnalyzerAgent` / `NewsAnalyzerAgent`) was never
instantiated anywhere and has been deleted.
