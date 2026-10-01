# GoldMind API

> 🌐 [中文](../API.md) | [English](./api.md)

> 🤖 **Generated from the FastAPI route table by `backend/scripts/gen_api_doc.py` — do not edit by hand.**
> After changing an endpoint run `cd backend && python scripts/gen_api_doc.py`;
> `backend/tests/integration/test_api_doc.py` checks that both language versions match the routes.

The running service also serves interactive documentation at `http://localhost:8000/docs`
(Swagger UI) and `http://localhost:8000/openapi.json` (the OpenAPI schema).

---

## Conventions

- **Prefix**: every business endpoint lives under `/api/gold` (not `/api/analysis` or `/api/news`)
- **Auth**: none. Add access control at the reverse proxy before exposing this publicly
- **Rate limiting**: sliding window per client IP. Regular endpoints default to 60/min;
  paths ending in `/refresh` count as heavy operations and default to 6/min
  (AI analysis refreshes really call the LLM; the quant refresh fetches every data source).
  `/health` is not limited. Over the limit returns `429` with `retry_after` (seconds)
- **CORS**: only the origins listed in `CORS_ALLOW_ORIGINS`
- **Errors**: FastAPI's `{"detail": ...}`; rate limiting returns `{"error", "retry_after"}`

---

## Endpoints

### gold

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/gold/bearish-factors-ai` | AI-generated bearish factors (fast, cached response) |
| `POST` | `/api/gold/bearish-factors-ai/refresh` | Refresh the bearish-factor analysis. (**calls the LLM**, stricter rate limit) |
| `GET` | `/api/gold/bullish-factors-ai` | AI-generated bullish factors (fast, cached response) |
| `POST` | `/api/gold/bullish-factors-ai/refresh` | Refresh the bullish-factor analysis. (**calls the LLM**, stricter rate limit) |
| `GET` | `/api/gold/dollar-realtime` | Realtime dollar index (source: Sina Finance ICE DINIW; 30-second cache). |
| `GET` | `/api/gold/factors` | Stored market factors, optionally filtered by type. |
| `GET` | `/api/gold/factors/bearish` | Bearish factors read straight from the database (no AI call). |
| `GET` | `/api/gold/factors/bullish` | Bullish factors read straight from the database (no AI call). |
| `GET` | `/api/gold/institution-predictions-ai` | AI analysis of institution views: each bank's latest verifiable gold target, with its prediction date and source. |
| `POST` | `/api/gold/institution-predictions-ai/refresh` | Refresh the institution-view analysis. (**calls the LLM**, stricter rate limit) |
| `GET` | `/api/gold/institutions` | Stored institution views. |
| `GET` | `/api/gold/investment-advice-ai` | AI-generated investment advice. |
| `POST` | `/api/gold/investment-advice-ai/refresh` | Refresh the investment-advice analysis. (**calls the LLM**, stricter rate limit) |
| `GET` | `/api/gold/latest` | Latest gold price row in the database. |
| `GET` | `/api/gold/market-summary-ai` | AI-generated gold market summary. |
| `POST` | `/api/gold/market-summary-ai/refresh` | Refresh the market summary. (**calls the LLM**, stricter rate limit) |
| `GET` | `/api/gold/news` | News list, filterable by source and sentiment (no pagination; first `limit` rows only). |
| `GET` | `/api/gold/news/sentiment/summary` | News sentiment distribution. Note: rows are always stored as NEUTRAL — this project does no sentiment analysis, so this is always all-neutral; the field exists only to keep the response shape stable. |
| `GET` | `/api/gold/news/{news_id}` | Single news item. |
| `GET` | `/api/gold/predictions` | Stored price predictions. The table holds real rows: the quant engine (services/quant) writes one per refresh. |
| `GET` | `/api/gold/predictions/latest` | Latest stored price prediction. |
| `GET` | `/api/gold/prices/correlation` | Gold vs. dollar index correlation. |
| `GET` | `/api/gold/prices/daily` | Daily gold price series. |
| `GET` | `/api/gold/quant/accuracy` | Walk-forward hit rate, side by side with the always-long / momentum / coin-flip baselines. |
| `GET` | `/api/gold/quant/factors` | Current snapshot of the four driver categories: value, direction, contribution, source and data-as-of date. |
| `GET` | `/api/gold/quant/monitor` | Monitoring dashboard: one row per indicator (frequency, source, current value, signal, data as of). |
| `GET` | `/api/gold/quant/predictions` | Quant forecast: direction, upside probability, target price and per-factor contributions. |
| `POST` | `/api/gold/quant/refresh` | Fetch factors, recompute predictions and append one backtest run now (takes tens of seconds). (**heavy operation**, stricter rate limit) |
| `GET` | `/api/gold/quant/research` | Research page: skill overview, reliability bins, coverage, regime scores, factor breakdown and the pre-registered verdict. |
| `GET` | `/api/gold/stats` | Gold price statistics since 2025 (current price, return, volatility range, ...). |

### other

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service information and documentation entry points. |
| `GET` | `/health` | Enhanced health check covering every critical dependency. |

---

## Response fields follow the code

Response models live in `backend/app/schemas/`; field names follow that source.
For example `GET /api/gold/stats` returns `ytd_return` and `volatility`, not the
`ytd_change` / `volatility_range` an early hand-written doc claimed.

The matching frontend types live in `app/src/services/api.ts`; the two must agree.
