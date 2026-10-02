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
┌──────────────┐   /api/**   ┌──────────────┐            ┌────────────────┐
│  Browser     │ ──────────► │  FastAPI     │ ─────────► │ SQLite(default)│
│  React 19    │             │  (uvicorn)   │            │ or MySQL(opt.) │
└──────────────┘             └──────┬───────┘            └────────────────┘
                                    │
                                    │ llm_provider (the only exit)
                                    ▼
                             ┌──────────────┐
                             │  any OpenAI  │
                             │  compatible  │
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
│   ├── src/sections/      seven sections: market / bullish vs bearish / institutional views / messages / investment strategy / quant prediction / conclusion
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
    │   ├── database.py    engine and session (SQLite by default; MySQL optional)
    │   ├── models/        ORM definitions of the 6 tables
    │   ├── routers/       4 router modules
    │   ├── services/      business logic (see below)
        │   └── utils/     rate_limit and so on
    ├── scripts/           smoke_llm / dev_mock_llm / dev_seed_sqlite
    └── tests/             unit / integration / e2e
```

---

## 3. Analysis pipeline

**This is not a multi-agent system.** The five services each complete one independent single-turn
LLM call and do not communicate with each other:

```
SQLite(gold_news, news_digest_items, gold_prices)
        │
        ▼
  assemble prompt ──► llm.invoke() ──► parse JSON ──► two-level cache ──► HTTP response
        ▲
        └── optional: plugin-style web_search (LLM_SEARCH_ENABLED, off by default)
```

News and the price context are assembled into one shared input packet by
`services/analysis_input.py` (`build_analysis_input`: `news_items` / `news_block` / `price` /
capability statement), consumed by the factor, institutional-view, advice and summary services.
Every prompt states explicitly that the call is single-turn with no web or tool access and that
missing data must be reported as such, so the model cannot fill gaps from memory.
Factor output then passes a deterministic structure check in `services/factor_validation.py`
(at most 5 factors, dedupe by id / title, ids restricted to the allowed set, best-effort numeric
citation against the news actually sent); failing factors are dropped entirely, and if none
survive the service degrades to an empty structure instead of caching half-dirty data.

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
  controlled by `LLM_TRUST_ENV`). If the host sets a SOCKS proxy or has `[::1]` in `NO_PROXY`,
  httpx raises during **construction**; `ChatOpenAI` prepares both a sync and an async client, so
  supplying only the sync one still builds a default async client and reads the environment. The
  exception is swallowed by the layer above and replaced with defaults, which shows up as "the page
  has analysis content, but not a single model call ever happened".
- **The `web_search` tool is off by default**: it is a MiMo plugin-style capability (not a generic
  OpenAI one) and requires the endpoint to have it enabled plus an explicit
  `LLM_SEARCH_ENABLED=true`; otherwise it returns
  `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`
  (measurements in `scripts/smoke_llm.py`). When search is unavailable the system falls
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
| `news_digest_items` | high-authority message-board items (storage-isolated from `gold_news`); `url` is `TEXT` (Google News links exceed 500 chars, and `VARCHAR(500)` makes MySQL reject the whole batch — upgrade old databases with `scripts/migrate_news_digest_url.py`), deduplicated via prefix index 191, `published_at` is indexed |
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

The engine uses SQLite by default (the single file `backend/goldmind.db`) and also supports MySQL:
SQLite needs `check_same_thread=False`, and an in-memory database additionally needs `StaticPool`,
otherwise every connection sees its own separate empty database. Under SQLite, `init_db.py` creates
tables with the models' `create_all`; under MySQL it creates the database first and then runs
`schema.sql`.

> Tests run against in-memory SQLite by default; to verify MySQL, use the
> `GOLDMIND_TEST_DATABASE_URL` switch in `conftest.py` to run the same suite again (point it at a
> separate test database; the cases truncate every table). The two differ in enum storage, JSON
> columns and string case comparison.

---

## 7. Configuration

Every configuration item lives in `app/config.py` and can be overridden directly with environment
variables. Commonly used items:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/goldmind.db` | a single-file SQLite database by default, zero install; can also point at MySQL (optional, not exercised in this repository) |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | — (you must fill these in) | LLM access; any OpenAI-compatible endpoint, configured only when all three are set |
| `LLM_MAX_TOKENS` | `8192` | Per-call output cap, shared by the model's thinking and its answer |
| `LLM_SEARCH_ENABLED` | `false` | Plugin-style web-search switch (no effect until the endpoint enables it) |
| `LLM_TRUST_ENV` | `false` | whether to read the host's proxy environment variables |
| `CACHE_DIR` | `backend/cache` | file cache directory |
| `NEWS_RSS_SOURCES` | four built-in sources | format `name\|URL,name\|URL` |
| `NEWS_DIGEST_SOURCES` | 13 built-in high-authority sources | message-board source pool, format `name\|URL\|tier\|relevance`; empty means the built-in defaults |
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
| Update the message digest | `25 * * * *` | full crawl of the message board's high-authority sources (no LLM calls) |
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
- **Failure propagation** (hardened on 2026-10-02):
  - Missing databases/tables (MySQL 1146/1049, SQLite `no such table`) are translated into a
    **503 + `python init_db.py` guidance** instead of a bare 500; startup runs a schema self-check
    and logs an ERROR when tables are missing. Other SQL errors still surface as 500 and are not
    masked by that guidance.
  - The frontend retries idempotent GETs on **429 / 5xx / network errors** with exponential backoff
    (±25% jitter), at most 3 attempts; 429 prefers `Retry-After` (then body `retry_after`).
    `POST` and `GET ...?refresh=true` are never retried — they may trigger a paid LLM call.
  - In-flight GETs for the same URL are merged into one request (StrictMode double-mount and
    polling/manual-refresh collisions no longer double the request rate); dashboard polling runs
    every 30 s, pauses while `document.hidden`, and catches up immediately on return.

> This project has **no authentication**. For a public deployment, add access control at the
> reverse proxy; otherwise anyone can trigger the `/refresh` endpoints, which consume LLM quota.

---

## 10. Deployment

**The documented reproduction path is local SQLite** (see "Quick Start" in `README.md`): no database
server and no containers — `python init_db.py` creates `backend/goldmind.db` and the tables.

The repository still keeps optional MySQL / container assets, **not exercised by this round's gate**:

- `docker-compose.yml` starts three containers: `mysql` / `backend` / `frontend`(nginx); the backend
  entrypoint waits for the database, runs `init_db.py` and then starts uvicorn, while the frontend's
  nginx reverse-proxies `/api/` and `/health` to the backend and LLM credentials come from
  `backend/.env` (`LLM_*`)
- On first start, MySQL executes `backend/schema.sql` (mounted read-only as
  `/docker-entrypoint-initdb.d/01-schema.sql`): the script only contains
  `CREATE TABLE IF NOT EXISTS` and **no CREATE DATABASE / USE** (hardcoding the database name would
  break the configuration); the mysql image selects the database from `MYSQL_DATABASE` before
  running it, so the script can run repeatedly

> To switch to a local MySQL, write `DATABASE_URL` in `backend/.env` and run `python init_db.py`
> (the MySQL path creates the database and then executes `schema.sql`). The behavioural differences
> between the two MySQL paths and the SQLite default (ENUM storage, string case comparison,
> transaction semantics) are known; run the full gate via `GOLDMIND_TEST_DATABASE_URL` first.

---

## 11. Quant prediction engine

`app/services/quant/`: turns "the four classes of factors that affect the international gold price"
(monetary policy and rates / hedging and credit / supply-demand structure / market and technicals)
into backtestable signals. The factor list, weights, direction priors and freshness caps are
defined **in one place only**, `app/services/quant/definitions.py`, and the API outputs according to
it — documentation does not copy a second version.

| Stage | Location | Key points |
|---|---|---|
| Data sources | `sources/*.py` | all free, no keys required (including the Treasury DTS TGA, the New York Fed RRP, CFTC open interest, Yahoo USDCNY); the HTTP client is injectable, and tests never really go online. When the external quote source (Yahoo) fails, the gold benchmark and the dollar factor fall back to the locally synced `gold_prices` / `dollar_index` tables (source labelled "本地行情表…兜底"): only the provenance changes, never the factor set or weights |
| Derivation | `derive.py` | raw series → factor values; units and conventions are fixed in this layer only |
| Persistence | `storage.py` | `factor_observations`, unique constraint `(factor_key, obs_date)`, idempotent |
| Sync | `sync.py` | per-source throttling (6h ~ 24h), incremental fetching, per-source degradation, and a sync report |
| Signals | `engine.py` | rolling z → direction alignment → weights by horizon (`definitions.horizon_weights`) → one calibrated distribution giving expected return, uncertainty, upside probability, target price and interval |
| Fair value | `decompose.py` | walk-forward expanding-window OLS (`log gold price ~ real rate + log dollar index + log central bank reserves + VIX`) splits the gold price into macro anchor + demand premium + risk premium + sentiment residual; deviation = market price / fair value − 1 |
| Scenarios | `scenarios.py` | quantiles of the predictive distribution N(μ, σ²) → Base [q25, q75] (50%) / Bull top 25% / Bear bottom 25%; the trigger and invalidation conditions are generated from this horizon's heaviest factor + the 200-day moving average |
| Backtest | `backtest.py` | walk-forward hit rate (scoring the calibrated direction) + three benchmarks + a separate score for the uncalibrated score direction + 80% interval coverage + segments split at 2022-01-01 + per-factor hit rate and IC |
| Monitoring | `monitor.py` | a weekly dashboard giving frequency / source / value / signal / data as-of date row by row; signal rules are centralised in `_rule`, informational rows have `signal=null`, and missing data is marked "unavailable + reason" |
| Exit | `service.py` | the scheduled task and `POST /api/gold/quant/refresh` share the same chain |
| Statistics | `stats.py` | significance toolbox for overlapping samples: Newey–West HAC standard errors, circular block-bootstrap intervals, HAC t / Diebold–Mariano, Brier skill score and reliability bins (no scipy) |
| Pre-registration | `preregistered.py` | **the only implementation** of the candidate list, selection rules and pass lines: register first, test second; changing a constant after seeing holdout results breaks pre-registration |
| Screening | `screen.py` | three pre-registered gates a new series must clear before it may enter the factor set: HAC significance with a Bonferroni correction **plus** an effect-size floor, the same sign across at least two horizons, and an unchanged sign on the forward window. It has **no adoption power**: `Verdict.adopted` is always `False` and nothing under `app/` imports it, so it can only reject or park a candidate |
| Research bench | `scripts/quant_lab.py` | pre-registered candidates × horizons × four sample periods (development / spent historical holdout / **forward** holdout / full), reading the project database directly and adjudicating on the forward window only, feeding the "Research" page and the bench report |

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

Predictions have a single distribution exit (`engine.build_prediction_frame` +
`engine.calibrate_distribution`): at time t, μ = α + β·score (expanding-window OLS, with sample pairs
satisfying s + h ≤ t) and **|μ| ≤ `EXPECTED_CAP_SIGMAS` × the expanding standard deviation of
realised h-day returns** (an OLS over a nearly constant score can push β to 1e4; on 2019-01-08 it
produced a 60-day expected return of +1261, so the cap is mandatory);
scale = std(e_s | s + h ≤ t) (the standard deviation of the **walk-forward prediction error**, not
the regression residual; with fewer than 60 realised errors it falls back to the expanding standard
deviation of realised h-day returns, still using past data only);
F̂ = the **half-life-weighted empirical distribution** of the last `CALIBRATION_WINDOW` studentized
errors `e_s/scale_s`, with the nominal miss rate α updated online by ACI
(`α ← α + γ(α_target − miss)`). Two details were forced by measurement:

- **`miss` scores the interval that was issued for that bet**, not the interval shown on the current
  row: the error series is already shifted right by `horizon` rows, so the error on row t belongs to
  the bet issued on row `t − horizon` (`calibrate_distribution(issued_lag=)`). Mixing the two up
  leaves long horizons systematically under-covered (development period, before the fix: 20-day
  0.767, 60-day 0.726; after: 0.791 / 0.744);
- calibration samples come in three modes (`engine.CALIBRATION_MODES`, research-bench candidates
  C0 / C1 / C2): `row` counts every row (the delivered convention), `bet` counts every
  `horizon`-th row, and `bet_window` adds a calendar-equivalent look-back window on top of `bet` —
  h-day forward errors overlap at daily frequency, so one bet is counted h times and the conformal
  "exchangeable samples" premise breaks. All constants that belong to these modes are given in one
  place, `engine.calibration_settings()`: change the sampling unit and γ / half-life / look-back
  window must move with it. Which mode ships is decided by `engine.DEFAULT_CALIBRATION_MODE`; the
  candidate definitions and decision rules live in
  `docs/specs/2026-10-02-量化引擎第三轮预注册.md`.

All four outputs come from that one F̂:

```
80% interval    = μ + scale · [ F̂⁻¹(α/2),  F̂⁻¹(1−α/2) ]   ← asymmetric; default interval="aci"
scenario band   = μ + scale · [ F̂⁻¹(0.25), F̂⁻¹(0.75) ]    ← same quantile sample, nested by construction
upside prob.    = 1 − F̂( −μ / scale )                     ← not Φ(μ/σ)
displayed scale = (upper − lower) / (2 × 1.2816)           ← the `uncertainty` field
```

`uncertainty` only converts the interval width into a normal-scale display value: **under the
asymmetric convention the interval midpoint is not μ**, so "μ ± 1.2816·uncertainty" equals the shown
interval only in the symmetric modes (`normal` / `empirical`). It takes **no part** in the
probability: using it as the denominator of Φ once pushed every probability toward 50% (one of the
direct reasons the Brier skill score was negative across the board; fixed 2026-10-02).
The "direction" on the page = sign(μ) (exactly 0 is recorded as "flat"). Deriving it from the
distribution median was tried and lost 60-day hit rate on the real 20-year panel, because the
walk-forward error's location term is systematically negative: the location term sets the scale for
probability and interval, it does not make the decision (see `engine.SignalSnapshot.direction`).
The factor-composite score is an **uncalibrated** input: it appears only in the factor table and the
"factor tilt (uncalibrated)" row, and backtests score it separately
(`metrics.score_direction_accuracy`). When there are fewer than 60 regression samples,
`expected_return` is NaN → the whole horizon returns "unavailable + reason"; it does not fall back to
"expected unchanged", and the sign of the score does not stand in for the direction. The actual
coverage of the 80% interval after empirical-quantile calibration (recomputed 2026-10-02, holdout
from 2023-10-02): 1 day → 1 year is 78.9% / 77.6% / 73.2% / 61.2% / 24.1%; over the same holdout the
direction hit rates are 56.3% / 62.2% / 68.2% / 83.3% / 100%, matching "always long" day by day
(+0.0pp), with a negative Brier skill score — the model has no directional edge in the holdout. The
1-year horizon is the number-one problem: interval-width calibration cannot repair the centre (μ)
bias, and more coverage does not buy better direction. The pre-registered verdict of 2026-10-02:
17 candidates × 5 horizons, none passed, so the live version is **kept and labelled "no
statistical edge"** (that was `quant-v4`; the second round fixed the ACI mismatch and moved it to
`quant-v5`, the same day's engine hardening moved it to `quant-v6` (alignment no longer drops
observations dated on a non-trading day and the alpha cap came down to 0.5 — the table above is
the v6 recomputation), and the third-round C2 candidate was likewise retired by its pre-registered bar —
details in `docs/specs/2026-10-02-研究台报告.md` and
`docs/specs/2026-10-02-量化引擎第三轮预注册.md`, rules in `preregistered.py`).
The page honestly shows coverage side by side with the "always long / momentum" benchmarks
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

## 12. Message board (high-authority news digest)

The "Messages" section has its own table and fetch cadence (storage-isolated from `gold_news`).
Since 2026-10-02 its high-authority items also serve as analysis input: `services/analysis_input.py`
merges them with `gold_news`, deduplicating by normalised URL (message-board items win), and feeds
the bullish/bearish factors, institutional views, investment advice and market summary prompts with
a title plus a cleaned, truncated summary per item (implementation: `services/news_digest.py`,
`services/analysis_input.py`).

- **Source pool**: 13 built-in, verified-working sources across four categories — central
  banks (Federal Reserve / ECB official RSS), wire services and industry bodies (Reuters / AP /
  World Gold Council via Google News `site:` filters, because their own RSS feeds are gone),
  and professional financial media (Bloomberg / FT / WSJ / CNBC / MarketWatch / Kitco /
  MINING.COM / Investing.com). `NEWS_DIGEST_SOURCES` overrides the whole pool; format
  `name|URL|tier|relevance`.
- **Admission rules**: an item must have both a link and a published time — anything missing
  either is skipped and counted in the fetch report, never backfilled with the fetch time.
  `gold` sources must match financial-context gold terms (`gold medal` and other sports uses
  are excluded, as are fashion and idiom metaphors such as `gold dream` and `go for gold`; the
  list is maintained from real misclassifications seen in the feeds); `monetary` sources
  additionally accept FOMC / rates / inflation / central-bank terms.
- **Deterministic scoring** (no LLM):
  `importance = 100×(0.40·authority + 0.25·relevance + 0.20·coverage + 0.15·recency)`,
  `confidence = 100×(0.45·authority + 0.30·coverage + 0.25·relevance)`; recency decays
  exponentially on a 7-day scale (`exp(-age_hours/168)`). Same-story items are clustered by
  title (Jaccard ≥ 0.6 and at least 2 shared terms); coverage counts distinct sources and the
  cluster representative is its highest-importance member.
- **Windows**: the last 30 days are scored once, then exposed as three filtered views —
  24 hours / 7 days / 30 days, each capped at the top 10. The same event scores identically in
  every window; **overlap is by design**.
- **An empty database is reported honestly**: `has_data=false` plus a reason (never crawled /
  every source failed / no qualifying item in 30 days); the page shows "unavailable" and never
  fabricates items.
- **API and schedule**: `GET /api/gold/news/digest` and `POST /api/gold/news/digest/refresh`
  (fetch report stored in cache_manager under `news_digest_fetch_status`); the
  `update_news_digest` job crawls every hour at minute 25.

---

## 13. Capabilities that explicitly do not exist

The following appeared in earlier documents but is not in the code:

Redis, message bus, WebSocket push, K8s / Istio, WAF, CSRF token, authentication/authorization
middleware, log tracing middleware, RAG (vector store / embedding / retrieval), ReAct reasoning
loops, multi-agent collaboration, TF-IDF / NER, news sentiment analysis (the `sentiment` field is
always `NEUTRAL`, only to keep the API shape stable).

The `app/agents/` package (`BaseAgent` / `MarketAnalyzerAgent` / `NewsAnalyzerAgent`) was never
instantiated anywhere and has been deleted.
