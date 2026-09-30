<p align="center">
  <img src="docs\images\6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>An AI Data Analysis Engine for the International Gold Market</strong><br>
  <em>An AI Data Analysis Engine for the International Gold Market</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/version-v1.0.0-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <strong>English</strong> | <a href="./README.md">中文文档</a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-overview">Overview</a> •
  <a href="#-system-showcase">System Showcase</a> •
  <a href="#-workflow">Workflow</a> •
  <a href="#-contributing">Contributing</a> •
  <a href="#-contact-author">Contact Author</a>
</p>

---

## ⚡ Overview

**GoldMind** is a gold market analysis dashboard: it collects gold and dollar-index prices
automatically and uses an LLM to turn recent news into a bullish/bearish contrast, institutional
views, investment strategies and a market summary, presented as a single-page **light research
brief** — five sections (Market / Bullish vs Bearish / Institutions / Strategy / Conclusion), all
left-aligned, with no gradients, no shadows and no card grid; numbers live in tables, and rising
is red while falling is green.

It is currently driven by a single model, **Xiaomi MiMo** (`mimo-v2.6-flash`). Every LLM
client is constructed through `backend/app/services/llm_provider.py`.

> You only need to: open the page
> GoldMind returns: today's gold price, the dollar index, and bullish/bearish analysis generated from the last 24 hours of news

> 📌 Product boundaries and known limitations live in [`docs/00-产品方向.md`](docs/00-产品方向.md) (Chinese). **Anything marked as planned there is not implemented — do not treat it as a feature.**

### 🎯 How it is actually implemented

These four points correct technical claims made by earlier versions of this document:

**"Multi-agent"**
Analysis is performed by four **independent single-turn LLM calls**, not agent collaboration: each service assembles a prompt, calls `llm.invoke(prompt)` once, and parses the JSON it returns. There is no tool-calling loop and no inter-agent communication. The `backend/app/agents/` package that earlier docs described has been removed; nothing ever instantiated it.

**"Real-time search"**
The design uses MiMo's `web_search` tool to retrieve institutional research and news. The Token Plan `tp-` key currently returns `HTTP 400` for that tool (measured; see `backend/scripts/smoke_mimo.py`). When search is unavailable the system falls back to database and RSS news and does **not** invent institutional price targets.

**"RAG"**
There is no vector store, no embeddings and no retrieval step. Historical prices and news are pasted straight into the prompt as context.

**"ReAct"**
Not implemented. There is no Thought / Action / Observation loop.

**"A section sometimes says unavailable"**
The model is a reasoning model, so `max_tokens=4096` covers both its thinking and its answer. The
investment-strategy prompt asks for three complete strategies in one JSON object; when the output
approaches that cap it gets truncated and the JSON fails to parse, so the section honestly says
"unavailable" instead of showing a fabricated strategy. The bullish or bearish factors can go
empty the same way, less often — press refresh to retry.

---

## 🌟 Our Vision

**GoldMind** is committed to building a **real and usable AI Agent international gold market data analysis and price prediction platform** through community collaboration.

Through technological innovation, we hope to:
- 📉 **Reduce information asymmetry** - Enable every investor to access professional-grade market analysis
- 🛡️ **Enhance risk resistance** - Provide multi-dimensional risk assessment and early warnings
- 💡 **Practical investment advice** - Based on data and logic, provide actionable investment strategies

> 🤝 **We look forward to your participation!** Whether it's code contributions, feature suggestions, or usage feedback, it will become an important force in driving the project forward.

If this project has been helpful or inspiring to you, a ⭐ **Star** is the best affirmation for us!

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

### Institutional Views
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/institutional-views.jpeg" alt="Institutional views" width="800">
</p>

> This deployment's MiMo key has no web search (the call returns `HTTP 400`). When no
> first-hand institutional view can be retrieved the table says "not available" — it never
> invents a price target.

### Investment Strategy
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/investment-advice.jpeg" alt="Investment strategy" width="800">
</p>

> The screenshot above shows the state before an analysis is stored: when the model output is
> truncated by the token cap, this section says so plainly instead of showing built-in advice.

### Conclusion
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/market-summary.jpeg" alt="Market summary" width="800">
</p>

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Description | Check Installation |
|------|---------|-------------|-------------------|
| Node.js | 18+ | Frontend runtime environment, includes npm | `node -v` |
| Python | 3.11 - 3.12 | Backend runtime environment | `python --version` |
| MySQL | 8.0+ | Data storage | `mysql --version` |

### Method 1: Local Development (Recommended)

#### 1. Configure Environment Variables

```bash
# Copy example configuration file
cd backend
cp .env.example .env

# Edit .env file and fill in necessary API keys
```

**Required Environment Variables:**

```bash
# ============================================
# Database Configuration
# ============================================
# MySQL database connection URL
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/gold_analysis

# ============================================
# AI API Key Configuration
# ============================================
# Xiaomi MiMo - one key for both reasoning and web search
# Get it at: https://platform.xiaomimimo.com/
# NOTE: the Token Plan terms restrict usage to coding tools; using it as this
# project's backend falls outside those terms. See docs/00-产品方向.md section 4.
MIMO_API_KEY=your_mimo_api_key_here
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.6-flash
```

#### 2. Install Dependencies

**Backend Dependencies:**

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Frontend Dependencies:**

```bash
cd app
npm install
```

#### 3. Initialize Database

```bash
cd backend

# Run database initialization (create tables + seed data)
python init_db.py

# If you want to skip data seeding and only create tables
SKIP_SEED=1 python init_db.py
```

**Manual Data Seeding:**

```bash
# If initialization skipped data seeding, or you need to update data
python seed_data.py
```

#### 4. Start Services

**Start both frontend and backend (run in project root):**

```bash
# Windows PowerShell
.\start_all.ps1

# Or start separately
```

**Start Individually:**

```bash
# Backend (in backend directory)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (in app directory)
npm run dev
```

**Service URLs:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Method 2: Docker Deployment

#### Prerequisites

| Tool | Version | Description | Check Installation |
|------|---------|-------------|-------------------|
| Docker | 20.10+ | Containerization platform | `docker --version` |
| Docker Compose | 2.0+ | Multi-container orchestration | `docker compose version` |

> ⚠️ **Network Requirements**: Need access to Docker Hub to download images. Users in China may need to configure VPN/proxy.

#### 1. Configure Environment Variables

```bash
# Copy example configuration file
cp backend/.env.example backend/.env

# Edit .env file and fill in necessary API keys
```

**Required Environment Variables:**

```bash
# ============================================
# Database Configuration (for Docker internal use)
# ============================================
MYSQL_ROOT_PASSWORD=your_secure_password
DATABASE_URL=mysql+pymysql://root:your_secure_password@mysql:3306/gold_analysis

# ============================================
# AI API Key Configuration
# ============================================
# Xiaomi MiMo - one key for both reasoning and web search
# Get it at: https://platform.xiaomimimo.com/
# NOTE: the Token Plan terms restrict usage to coding tools; using it as this
# project's backend falls outside those terms. See docs/00-产品方向.md section 4.
MIMO_API_KEY=your_mimo_api_key_here
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.6-flash
```

> 💡 **Note**: `docker-compose.yml` is configured to automatically load `backend/.env` file, no need to manually set environment variables.

#### 2. Start Services

```bash
# Build and start all services (frontend + backend + database)
docker-compose up -d --build

# Check service status
docker-compose ps

# View logs (observe data initialization progress)
docker-compose logs -f backend
```

**Network Configuration for China Users (if unable to download images):**

If using Clash/V2Ray or other proxy tools:

1. Enable system proxy or TUN mode
2. Configure in Docker Desktop → Settings → Resources → Proxies:
   - HTTP Proxy: `http://127.0.0.1:7890`
   - HTTPS Proxy: `http://127.0.0.1:7890`
3. Apply & Restart
4. Retry `docker-compose up -d --build`

> ⚠️ If network issues cannot be resolved, it is recommended to use **Method 1: Local Development**.

**First-time Startup Notes:**

Docker deployment will automatically complete the following initialization:
1. ✅ Create MySQL database and tables
2. ✅ **Automatically fetch and populate historical data** (gold and US dollar index data from 2025 to present)
3. ✅ Start backend services

The data fetching process may take 1-3 minutes, please observe the logs and wait for initialization to complete.

#### 3. Access Application

**Service URLs:**
- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

> 💡 **Tip**: When accessing for the first time, if you see "Loading data", it means the backend is still initializing data, please wait a moment and refresh the page.

---

## 🔄 Workflow

What the code actually does, end to end:

```
Market data ──► MySQL ──┐
RSS news    ──► MySQL ──┼──► assemble prompt ──► llm.invoke() ──► parse JSON ──► cache ──► dashboard
                        │
                        └──► (optional) MiMo web_search, skipped when unavailable
```

| Analysis service | Input | Output |
|---|---|---|
| Bullish factors | Last 24h news + gold price | 5 bullish factors |
| Bearish factors | Last 24h news + gold price | 5 bearish factors |
| Institutional views | Last 24h news + (search) | Four institutions' targets and reasoning |
| Investment advice | Market status + both factor sets + institutional views | Conservative / balanced / opportunity strategies |
| Market summary | All of the above | Core logic, risks, overall judgement |

Each of these is **one single-turn LLM call** — see "How it is actually implemented"
above. There is no agent orchestration, no reasoning loop and no retrieval step;
the earlier sections describing them have been removed rather than left to
contradict this one.

---

## 🧪 Commands

**The single source of truth for the gate.** Everything must be green before you
commit (the rules live in [`AGENTS.md`](AGENTS.md)).

### Backend

```bash
cd backend

# Install dependencies (first time)
pip install -r requirements.txt -r requirements-dev.txt

# Tests - the full gate
python -m pytest

# One layer at a time
python -m pytest tests/unit          # unit: no database, no network
python -m pytest tests/integration   # integration: in-memory SQLite + fake LLM
python -m pytest tests/e2e           # end to end: the whole chain in real order

# Run the same suite against MySQL (worth doing after database changes)
# Production is MySQL, and it differs from SQLite on enum storage, JSON columns and
# case-insensitive comparison - "green on SQLite" is not "green on MySQL".
# It must point at a SEPARATE test database: the suite truncates every table.
GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" \
    python -m pytest

# Static check: compile everything
python -m compileall -q app

# Database setup (create database + tables + backfill history)
python init_db.py
SKIP_SEED=1 python init_db.py        # schema only, no data

# Repair enum values in an older database (idempotent)
python scripts/fix_enum_columns.py --dry-run
python scripts/fix_enum_columns.py
```

### Frontend

```bash
cd app

npm ci

# Build + type check - the full gate
npm run build

# Static check
npm run lint

# Unit + integration tests (vitest + Testing Library)
npm test

# Browser end-to-end (Playwright) - needs npm run build first
npm run test:e2e

# Local development
npm run dev
```

---

## 🤝 Contributing

We welcome all forms of contributions! Please check our [Contributing Guide](./CONTRIBUTING.md) to learn how to participate in the project.

### Contributors

<a href="https://github.com/JasonBuildAI/GoldMind/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=JasonBuildAI/GoldMind" />
</a>

---

## 📄 License

This project is licensed under the [MIT License](./LICENSE).

---

## 🙏 Acknowledgements

- [Xiaomi MiMo](https://platform.xiaomimimo.com/) - LLM inference and web search
- [FastAPI](https://fastapi.tiangolo.com/) - High-performance Python web framework
- [React](https://react.dev/) - Frontend UI library
- [Recharts](https://recharts.org/) - React charting library

---

## 📧 Contact Author

If you have any questions, suggestions, or collaboration inquiries, please feel free to contact us:

- 🐛 **Questions & suggestions**: please open a [GitHub Issue](https://github.com/JasonBuildAI/GoldMind/issues)

---

<p align="center">
  <strong>GoldMind</strong> - Empowering Investment Decisions with Intelligence
</p>

<p align="center">
  <a href="https://github.com/JasonBuildAI/GoldMind">⭐ Star us on GitHub</a> •
  <a href="https://github.com/JasonBuildAI/GoldMind/issues">🐛 Submit Issue</a> •
  <a href="https://github.com/JasonBuildAI/GoldMind/discussions">💬 Join Discussion</a>
</p>
