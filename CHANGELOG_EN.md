# Changelog

Every release, **one line per change**. Version numbers map one-to-one to git tags:
`vX.Y.Z` is the `## [X.Y.Z] - YYYY-MM-DD` section below.

Versioning follows [Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

> 🌐 [中文](./CHANGELOG.md) | [English](./CHANGELOG_EN.md)

---

## [Unreleased]

(Unreleased work for the next round lives here; everything in 2.0.2 is below.)

### Changed

- **Layout switched to a two-column shell — left sidebar + content column — filling the whole page.**
  The wordmark, anchor nav, today's brief and data freshness moved out of the top bar into the left
  sidebar (`AppSidebar`: a sticky column, translucent, hairline on its right edge), and the content
  column now takes every remaining pixel — the body is **no longer centred and narrowed to 1180px**,
  so tables and charts fit on one screen on a wide display; readability is instead guaranteed by each
  section's own 68ch measure. Below 960px it collapses to a single column and the sidebar becomes a
  bar at the top of the page.
- **Frontend rewritten: React 19 → Vue 3 + Pinia.** `app/src` is grouped by feature
  (`views/dashboard` / `views/research` / `components` / `stores` / `composables` / `styles`), one file
  per concern; the two HTML entries (dashboard / research) and the `./research.html` relative link are
  unchanged. Tests moved from Testing Library to `@vue/test-utils`, and type checking now runs through
  `vue-tsc`.
- **Visual language switched to Apple macOS / HIG**: layered surfaces, hairlines, 6/8/10 radii, two
  very light shadow levels, a translucent sidebar and card overlays, the system font stack (serif stack
  removed) and Apple's semantic palette; every foreground/background pair is measured against 4.5:1. See
  `docs/20-前端设计规范.md` (sections 2 and 4 rewritten).
- Dropped the dependencies that were **not actually used**: Tailwind (only 6 of 639 `className`
  occurrences were utilities), recharts (used in 2 charts only, now hand-rolled SVG), Radix Tabs
  (replaced by an in-house ARIA tablist), lucide-react / clsx / tailwind-merge. Frontend JS output
  dropped from 863 kB to 312 kB.

### Added

- A layout self-check script, `app/scripts/verify_layout.mjs` (needs the real stack running): it measures
  in a real browser at 1440×900 and 390×844 — no horizontal overflow (offending elements are named), two
  columns filling the viewport and a single column when narrow, a sticky sidebar with its hairline, live
  design tokens, no decorative gradients or glow, reachable anchors, and body/secondary text contrast
  ≥ 4.5:1. Unit tests run in happy-dom, which has **no layout engine**, so it cannot see "the page
  scrolls sideways".
- Three gate guards: `src/__tests__/guards/forbiddenCopy.test.ts` (renders every section, then scans
  for capability claims), `pageStructure.test.ts` (one h1 / skip-link target exists / nav anchors
  resolve / reading order / unique ids / tabs carry `aria-selected` / buttons have accessible names /
  no nested disclosures) and `designTokens.test.ts` (no hardcoded hex colors in components). All three
  were mutation-verified (see the appendix of this round's spec).

### Fixed

- The bootstrap `schema_migrations` registry now builds its SQL from a Core Table: `key` is a
  MySQL reserved word, so the hand-written SQL made MySQL fail with 1064 and blocked automatic
  migrations; SQLite behaviour is unchanged (verified against a real MySQL server).
- Two tab groups in the frontend shared the same tabpanel ids (`tabpanel-${horizon}` for both the five
  decision horizons and the backtest horizons), which pointed `aria-controls` at the wrong element;
  `TabsNav` now requires the caller to supply a `panelId` prefix.
- Horizontal page scrolling on narrow screens (measured: the document was 1025px wide in a 390px
  viewport), from three separate causes: grid/flex children missing `min-width: 0` (long paragraphs and
  tables widened their track), `.table-scroll` itself missing `min-width: 0` (so "scroll inside the
  table" became "scroll the whole page"), and a chart that never cleared the browser's default `figure`
  margin (`1em 40px` — 40px of overflow on one side alone).
- The screenshot script's default URL changed from `127.0.0.1:5173` to `localhost:5173`: the Vite dev
  server only listens on `::1` by default (the README's documented address is localhost too), so
  hardcoding IPv4 failed to connect and hung on "cannot read /health".

---

## [2.0.2] - 2026-10-03

### Added

- **Fully automatic operation: `backend/.env` is the only manual input.** The bootstrapper (`app/bootstrap.py`, wired into the FastAPI lifespan) creates the schema, applies migrations, backfills according to coverage (prices / dollar index / news and digest / full quant factor history, `QUANT_BACKFILL_YEARS` default 20, resumable after interruption, revision log included) and warms the first analyses once data is ready; every phase is idempotent and retried on the next boot. `/health.bootstrap` exposes "step N of M" plus the remaining gaps (`AUTO_BOOTSTRAP` defaults to true)
- Migration registry + `schema_migrations` table: `migrate_quant` / `migrate_institution_views` / `migrate_news_digest_url` / `fix_enum_columns` all became idempotent automatic migrations; SQLite is backed up to `backend/backups/` before any DDL, MySQL only ever adds columns or tables and never deletes data
- LLM configuration hot-reload (`CONFIG_WATCH` defaults to true): `backend/.env` is watched, and when LLM keys appear or change the settings reload, the client cache resets and a fresh analysis round starts immediately - no restart. Keys that still need a restart (e.g. `DATABASE_URL`) are reported under `/health.config_watch`
- Scheduler self-healing and daily maintenance: missed date-driven jobs are caught up at start-up instead of waiting for cron, every job runs with `coalesce` + `misfire_grace_time`, and two long-term jobs were added - a daily automatic backup (7 SQLite copies kept; MySQL explicitly documented as not dumped on your behalf) and a daily data sanity check (auto-fixes only the safe cases, after a successful backup) (`AUTO_BACKUP` defaults to true)
- LLM call gate `services/llm_gate.py`: an unchanged input fingerprint skips the recomputation and reuses the cache (an explicit forced refresh is exempt); new `LLM_DAILY_CALL_BUDGET` (default 200/day, <=0 means uncapped) degrades every block to "unavailable + reason" once exhausted, and never to invented content
- `GET /api/gold/sources/status` aggregates each fetch channel's last attempt and availability; `/health` gained the `bootstrap` and `config_watch` fields
- Every price now carries its `basis` (realtime quote / daily close / quant benchmark), its source and its as-of date (item 1); a same-day realtime-vs-close divergence above 3% is named by the data sanity check
- News items gained `via_aggregator` (reached through an aggregator) and `event_tags` (deterministic FOMC / CPI / NFP / central-bank decision / central-bank buying tags, fed into the analysis prompt and shown as-is on the page)
- Quant `quant-v7`: factors carry `publication_lag_days` and align on the observable time (item 12); the 250-day horizon stops publishing a direction (`direction_status: not_published` plus the reason, keeping the fair-value gap and the calibrated interval); new first-class metrics "edge over always-long (with confidence interval)" and "down-call quality", a Beta posterior on the forward verdict (hard-coded `Beta(1,1)` prior, next to CRPS), regime and rolled-benchmark lab candidates (research bench only), and the "high-authority digest intensity" derived series (pre-registered candidate, monitor row 22)
- Weight-sensitivity report `backend/scripts/weight_sensitivity.py` (item 6): rank stability, sign flips and per-factor leverage under weight perturbation, report-only with a normalisation guard; per-factor coverage profile (first/last observation, yearly counts, gap years, "accumulating") (item 11)
- Shanghai Gold Exchange Au99.99 daily series wired in as `sge_gold` (item 3), turning the "Shanghai premium" row from unavailable into a real calculation; the same-day source probe recorded Jin10 / MINING / Kitco / FX168 as unreachable and explicitly not landed
- Optional `REFRESH_TOKEN` (item 20): when set, POST refresh requires the `X-Refresh-Token` header
- Data-sanity entry point `scripts/check_data_sanity.py`: future dates / NaN and ±inf / loose plausibility bounds / cross-store consistency in one report; its first run flagged 1 future-dated row in the long store (etf_shares 2026-10-05, purged after backup) and 778 diverging seasonality rows between the two stores
- The 13 high-authority digest sources now feed all four LLM analyses: factors / institutions / advice / market summary share one "analysis input packet"; news goes from titles-only to "title + summary (truncated, HTML stripped)", and source, time and link travel into the prompt
- Deterministic structure validation of LLM output (`services/factor_validation.py`): id and title dedupe, empty-item filtering, at most 5 items, best-effort numeric citation checks; a failing response degrades to an empty structure instead of passing through
- Predictions are stored as an **append-only daily snapshot**: one row per `(model version, horizon, as-of date)`, updated in place within a day and kept across days, so "what was said then" can be replayed
- Backtests report **CRPS** (a distribution-level score) and its skill against the zero-drift benchmark next to the Brier skill, in both the API and the research page
- The research page states the data window (start / end, trading days, years): every number is recomputed on the current database window, and the page wins when its sample counts disagree with snapshots cited elsewhere
- Backup entry point `scripts/backup_db.py`: full copy plus per-table row-count check for SQLite; MySQL gets explicit `mysqldump` guidance and is not dumped on the user's behalf
- New M-family candidates in the quant lab: walk-forward Ridge directly on the factor matrix (realized pairs only, means/stds estimated inside the same window), compared with "compose first, then univariate regression"; definitions stay in `scripts/quant_lab.py` and never enter the live service
- LLM endpoint compliance guard: a `tp-` key combined with a token-plan endpoint triggers a one-time constructor warning (no key material) with switch guidance; `/health` exposes `token_plan_backend`

### Changed

- Store alignment moved into the bootstrapper (item 14): the service database is authoritative and overwrites the long research store, long-only dates are inserted but never deleted; the 10,902 pre-existing divergences (the GPR series shifted by one day plus five fake rows a cold-start test had written into the long store) dropped to zero, and `check_data_sanity --strict` went from failing to passing
- Ops scripts demoted to optional: `init_db.py` / `backfill_quant.py` / `migrate_*.py` / `backup_db.py` / `check_data_sanity.py` stay as they are, but "not using them loses no functionality"; the Docker entry point now waits for the database and starts uvicorn directly, and the bare-metal path is simply `uvicorn app.main:app`
- Quick start is now "fill `backend/.env` -> start -> done", README zh/en in sync
- The research page and dashboard promote the direction edge KPI, the Beta posterior and the monitor grouping (participating signals / watch-only) to first-class positions
- The four LLM services consume one shared "analysis input packet" (same window, same price context, same skill note), removing per-service drift
- The quant page moved the uncalibrated factor tilt and the sync report's "not due" noise off its main tables: the tilt sits in a details block, per-source status sits in a folded "data source status" block, and the main surface keeps conclusions and actionable items only
- Dashboard polling drops from 10 s to 30 s, pauses while the tab is hidden and catches up immediately on return (idle request rate ~30/min -> ~8/min)

### Breaking changes

- The `/news` response drops the dead `sentiment` field and the sentiment endpoint `/api/gold/news/sentiment/summary` is removed (the DB column keeps the history, the filter parameter stays; the page no longer shows sentiment conclusions)
- Model version `quant-v6 -> quant-v7`: publication-lag alignment plus the 250-day direction policy; the forward window restarts on the new seal date 2026-10-03 (old `quant-v6` rows stay in the database and remain queryable by version; v6 bets no longer count towards the verdict)

### Fixed

- LLM completions that hit the per-call output ceiling (`finish_reason=length`) no longer degrade the whole block: `invoke_with_retries` retries once with a compaction hint (fewer array items, shorter fields) and only then honestly returns "temporarily unavailable" instead of stitching partial JSON. Observed on the first real cold start: the four-strategy investment-advice schema hit the 8192-token ceiling and the block fell back to empty; the retry produced a complete three-strategy answer
- The bootstrap no longer force-refreshes the market summary on every boot (`force` is forwarded; an unchanged input fingerprint is not re-billed), and a new step 7 ("align the local research long store after backfill") converges both stores in a single boot while the first alignment imports long-store history to avoid re-downloading it
- The long store's GPR series lacked the publication-lag shift and was offset by one day (the legacy consequence of item 12), and a cold-start test had once written fake rows into the long store - both are repaired by the bootstrapper's store alignment, measured as 10,902 diverging rows -> 0
- During the bootstrap backfill the page now shows "initialising (step N of M)" with the remaining gaps instead of "unavailable"; with no LLM configured the data layer keeps running and catches up automatically once the configuration appears, with no "reanalyse" click needed
- The investment-advice window now rolls with the calendar (the hard-coded `datetime(2025,1,1)` is gone); "volatility range" is renamed to "high-low amplitude" with its definition written down, prompt synced
- `etf_shares` refuses observation dates later than today (storage guard + source fix); future dates no longer appear on the page
- The news-scan institution summary is assembled deterministically from the structured rows, so the LLM text can no longer contradict the structured data
- The market summary never states institutional views when institution data is missing (deterministic sanitising + prompt hardening)
- Investment advice no longer calls the LLM with no factors / no institutions / no news: it returns price statistics plus a "not enough data" note, flagged `insufficient_data` in the UI
- Test-database guard: the database name in `GOLDMIND_TEST_DATABASE_URL` must contain `test`, or the suite refuses to start at import time (2026-10-02 incident: it pointed at the dev database and `drop_all` wiped 9 business tables)
- Missing database/tables now answer **503 + `python init_db.py` guidance** (was a bare 500); startup runs a schema self-check and logs an ERROR when tables are missing; other SQL errors still return 500
- When the external quote source (Yahoo) is rate-limited or down, the quant engine falls back to the locally synced `gold_prices` / `dollar_index` tables for the benchmark and the dollar factor, labelled as such; no more whole-page "missing gold price series"
- The frontend retries **429 / 5xx / network errors** with exponential backoff (429 honours `Retry-After`, at most 3 attempts); in-flight GETs for the same URL are merged into one request; `POST` and `?refresh=true` are never retried
- Real-stack acceptance hit a 500 on the investment-advice endpoint: the post-retry model output omitted `disclaimer`, the cache kept serving the incomplete shape, and response validation failed. The analyzer parse path, the realtime exit and the cache-read exit now backfill missing contract keys with empty values (`core_principles=[]`, `disclaimer=""`, ...), normalising the shape without inventing content; only genuinely parsed rounds record the input fingerprint, so an empty shape still retries on the next round

### Documentation

- README zh/en: 2.0.2 banner / badge / new screenshots, quick start rewritten as "fill `.env` -> start", a new "fully automatic operation" section, and the three gold-price bases plus monitor row 22 explained
- `docs/ARCHITECTURE.md` gained an "automatic operation" section (bootstrap phases, migration registry, hot reload, scheduler self-healing and backups); `docs/API.md` and `docs/en/api.md` were regenerated from the route table
- New spec / plan for this round (`docs/specs/2026-10-03-2.0.2-整改与自动化.md` and its `-plan`), the weight-sensitivity report (`docs/specs/2026-10-03-权重敏感性报告.md`) and the zero-touch cold-start acceptance report (`docs/specs/2026-10-03-零人工冷启动验收.md`)
- `docs/10-密钥与隐私.md` (and its English twin) document the six new keys: `AUTO_BOOTSTRAP` / `QUANT_BACKFILL_YEARS` / `AUTO_BACKUP` / `CONFIG_WATCH` / `REFRESH_TOKEN` / `LLM_DAILY_CALL_BUDGET`

---

## [2.0.1] - 2026-10-02

### Added

- Factor gate and screening tool `backend/scripts/screen_factors.py`: de-meaned covariance + Newey–West HAC + Bonferroni + |t| >= 3, same sign across horizons, forward-window confirmation; none of the 255 cells on the 26-year panel passes, and after the engine fixes the 17 candidates are indistinguishable — the negative result is what points this round at new information sources
- The monitor dashboard grows to **21 rows**: GVZ / gold-silver ratio / copper-gold ratio / CFTC net share of open interest / GPR are added as information-only rows that never emit a direction; with zero rows in the database they show "unavailable + reason" instead of vanishing from the table
- Factor observations now store a current value plus an append-only revision log, and `--as-of` rebuilds the panel as of any past date; upgrading an old database backfills ten years of revisions
- New evaluation conventions: independent bets drawn at stride=h (the 250-day holdout has 506 overlapping samples but really 2 bets), per-factor HAC t next to the inflated iid value, a coverage audit bucketed by realised volatility, and a register-only outlet for reverse-significant factors
- The third gate (forward window) is now executable: its window starts on 2026-10-02, reports pending with the number of trading days still missing, and its section always appears in the report
- Generic LLM access: any OpenAI-compatible endpoint works, configured through `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` (all three must be set); `LLM_PROVIDER` is a display-only label
- New `LLM_MAX_TOKENS` (default `8192`), `LLM_SEARCH_ENABLED` (default `false`), `LLM_SEARCH_MODEL` / `LLM_SEARCH_BASE_URL` / `LLM_SEARCH_API_KEY` and `LLM_SEARCH_MAX_KEYWORD`
- Quant research bench and pre-registration: the single implementation of the candidate list, selection rules and pass lines in `backend/app/services/quant/preregistered.py`, the full evaluation tool `backend/scripts/quant_lab.py`, the endpoint `GET /api/gold/quant/research` and the separate "Research" page `app/research.html`
- Quant statistics toolbox `backend/app/services/quant/stats.py`: Newey–West HAC standard errors, circular block-bootstrap intervals, HAC t / Diebold–Mariano, Brier skill score and reliability bins (overlapping samples are no longer treated as independent)
- 20 years of factor history backfilled (36,150 rows inserted / 26,445 updated; see `docs/specs/2026-10-02-回填报告.md`) so the holdout evaluation has data

### Changed

- Model version `quant-v5`: direction, upside probability, the 80% interval and the three scenarios all come from the same calibrated distribution F-hat (interval widths are F-hat empirical quantiles, no longer inflated a second time by `uncertainty`); direction again follows the sign of the calibrated mu, which measured better than the distribution median
- The four-layer fair-value decomposition no longer extrapolates: targets beyond 6 sigma or 12 log-premium are listed under `unsupported_by` and refuse to give a number
- Stale factors become NaN at composition time instead of being forward-filled into a fake level; scales with too few samples are labelled "undecidable" rather than "failed", and every persisted prediction carries the measured skill status of its own scale
- The monitor dashboard judges freshness row by row: stale rows show only the value and the observation date, with no bullish/bearish label
- Pre-registered candidate C2 (per-bet calibration plus window) is rejected for missing the 0.78 pass line at 60 days (0.7679), thresholds unchanged; the control candidate C0 matches B0 value for value
- **The default database is now a single SQLite file** (`backend/goldmind.db`, zero install, zero configuration): under SQLite `init_db.py` creates tables with the models' `create_all`, and `seed_data.py` no longer opens a raw pymysql connection; MySQL is now an optional path (not exercised by this round's gate)
- Quant evaluation now follows a **pre-registered** protocol: the candidate list and pass lines are frozen before looking at the holdout (from 2023-10-02); after the engine fixes the re-run leaves 17 candidates × 5 horizons indistinguishable and none of the 255 cells on the 26-year panel passes the gate, so the research page honestly labels the model "no statistical edge"

### Changed (breaking)

- **LLM settings renamed: `MIMO_*` → `LLM_*`, with no compatibility fallback.** On upgrade, rename `MIMO_API_KEY` / `MIMO_BASE_URL` / `MIMO_MODEL` / `MIMO_SEARCH_MODEL` / `MIMO_SEARCH_MAX_KEYWORD` / `MIMO_TRUST_ENV` in `backend/.env` and in the deployment environment to their `LLM_*` equivalents

### Fixed

- **ACI interval-coverage lag**: the alpha update judged "the bet issued h days ago" against "the current row interval"; after the fix, development-period coverage rises from 76.7% to 79.3% at 20 days and from 72.6% to 73.6% at 60 days
- Observations dated later than today are rejected; the frontend monitor table no longer rounds ratios below 0.01 to 0.00
- **Investment strategy showed "temporarily unavailable" for a long time**: the 5 analysis services hardcoded `max_tokens=4096`, truncating the full three-tier JSON; they now take `LLM_MAX_TOKENS` (default 8192), and a failed parse logs `finish_reason` and token usage
- Automatic single retry when the endpoint returns `finish_reason=content_filter`; the default news prompt cap is now 10 items
- Smoke script renamed to `backend/scripts/smoke_llm.py` (was `smoke_mimo.py`); the web-search probe only runs when `LLM_SEARCH_ENABLED=true`

### Docs

- `README.md` / `README_EN.md` fully rewritten: the ten-section quant strategy (21-row monitor table, pre-registration verdicts, known limitations), verified quick-start commands, and 14 screenshots captured from the live stack on 2026-10-02 (the script refuses to write empty images)
- New drift guards: architecture-document claims, the README monitor table vs `monitor.ROW_SPECS`, and README commands vs the real `--help` of each script (all mutation-tested)
- README reproduction gaps fixed: the Node floor is now ≥22.22.2 (or 24.15+/26+), a Google Chrome prerequisite was added, the non-existent `.\start_all.ps1` was removed, and cold-start expectations were added
- The masthead / trend / bullish-bearish / institutional / strategy / summary screenshots were all retaken; institutional views keeps its honest "no recent prediction" empty state and the docs state the exact error message
- README (Chinese and English) synced to the SQLite zero-configuration quick start; Section 6 of the quant strategy now reports the measured holdout coverage and direction hit rates, a "Research Bench and Pre-registration" section was added, and the known limitations were rewritten to the holdout convention
- `docs/ARCHITECTURE.md` (and its English mirror) now document SQLite by default for deployment and configuration, with statistics, pre-registration and the research bench added to Section 11; `docs/00-产品方向.md` (and its English mirror) now list SQLite as the default storage

## [2.0.0] - 2026-10-01

2.0 is about **verifiability**: predictions converge on one backtestable distribution,
institutional views stop erasing real data just because no new note was published that day,
and the documentation is bilingual with the API reference generated from code.

### Added

- Quant prediction engine: 14 factors covering four driver classes (monetary policy and rates / hedging and credit / supply-demand structure / market and technicals), all from free, key-less data sources
- Per-source throttled incremental sync (6h-24h) with persistence; a unique constraint on `factor_observations(factor_key, obs_date)` keeps repeated fetches idempotent
- Five prediction horizons with their own weights: short horizons are led by flows and technicals, medium ones by policy expectations and the dollar, long ones by central-bank buying and demand structure
- A single calibrated distribution (model version `quant-v4`): direction = sign(mu), upside probability = Phi(mu/sigma), target price = base price x (1+mu), 80% interval = mu +/- 1.2816 sigma, three scenarios = quantiles of N(mu, sigma^2)
- Interval width calibrated to the **empirical quantile** of walk-forward forecast errors (normal quantiles are systematically too narrow at long horizons); falls back to the expanding standard deviation when fewer than 60 realised errors exist
- Four-layer fair-value decomposition: macro anchor + demand premium + risk premium + sentiment residual, with deviation = market price / fair value - 1
- Each scenario carries **trigger** and **invalidation** conditions (built from that horizon's heaviest factor and the 200-day moving average, checkable line by line)
- Walk-forward backtest: hit rate side by side with the always-long / momentum / coin-flip baselines, plus the realised coverage of the nominal 80% interval, the split around 2022-01-01, and per-factor hit rates and IC
- Monitoring dashboard: 16 indicator rows, each with frequency, source, current value, signal (bull / bear / neutral / info) and data-as-of date
- New quant section in the frontend: five horizon tabs, fair-value decomposition, monitoring dashboard, backtest hit rate, four-category factor tables
- New endpoints `GET /api/gold/quant/factors|predictions|accuracy|monitor` and `POST /api/gold/quant/refresh`
- New migration `backend/scripts/migrate_quant.py` (idempotent, add-only, with rollback)
- New migration `backend/scripts/migrate_institution_views.py` (dry-run by default, `--apply` to run, `--drop-columns` to roll back, **never deletes a row**)

### Changed

- Institutional views now take each institution's **latest verifiable** prediction: the scan window is `INSTITUTION_NEWS_LOOKBACK_DAYS` (default 30 days) and no longer requires news published in the past 24 hours
- The institutional views table gained "prediction date" and "source" columns; a prediction date older than 30 days is labelled "stale N days"
- Institution names are normalised onto four canonical rows (Goldman Sachs / UBS / Morgan Stanley / Citi); writes, reads, the prompt and the tests all derive from one institution registry
- Institutional views no longer gate reads behind a "only if updated within 2 hours" check; rows are assembled directly, and when the window holds no new prediction the server writes a deterministic explanation
- Frontend presentation layer rebuilt as a light research brief: design tokens, tabular numerals, red-up/green-down with both symbol and text, all six sections left-aligned, no gradients or shadows
- Documentation is fully bilingual: README, user-facing docs and the API reference all have English mirrors; `docs/API.md` and `docs/en/api.md` are now generated from the route table by `backend/scripts/gen_api_doc.py`

### Fixed

- **An empty target price no longer overwrites an existing real prediction** — the four institutional targets overwritten with "none" at 06:01 on 2026-10-01 (5400 / 5000 / 6300 / 6000) have been restored from the legacy alias rows onto the canonical rows
- A placeholder cache whose four rows all have a null `target_price` no longer shadows the real data in the database (the old check only tested that the list was non-empty)
- Analysis services no longer return invented fallback factors or strategies: when a data source or web search is unavailable they return "unavailable + reason"
- The frontend no longer ships hard-coded fallback data in each section, and a test now pins "no built-in copy on failure"
- The settings object masks secrets on itself, so credentials cannot leak through logs or error messages

### Docs

- Rewrote `README.md` and added `README_EN.md`, including the 2.0 release banner and a dedicated "Quant Strategy" chapter
- Added `docs/en/`: `product-direction.md`, `secrets-and-privacy.md`, `frontend-design.md`, `architecture.md`, `api.md`
- Added `CONTRIBUTING_EN.md`, this file and `CHANGELOG.md`

---

## [1.0.0] - 2026-02-03

First public release.

### Added

- Gold price and dollar index collection (Tencent Finance realtime gold, Sina Finance ICE dollar index), with history backfill from Sina / Eastmoney / Yahoo
- MySQL 8 persistence (`gold_prices` / `dollar_index` / `news` / `institution_views` / `predictions`)
- Four LLM analysis services: bullish factors, bearish factors, institutional views, investment advice, plus a market summary
- React single-page dashboard: market / bullish vs bearish / institutions / strategy / conclusion
- Two-level cache (in-memory + JSON file) shared across processes and restarts
- APScheduler refresh tasks and one-command Docker Compose deployment

[2.0.2]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.2
[2.0.1]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.1
[2.0.0]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.0
[1.0.0]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v1.0.0
