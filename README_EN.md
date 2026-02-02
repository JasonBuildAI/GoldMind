<p align="center">
  <img src="docs\images\6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>Next-Generation Multi-Agent Gold Market Intelligence Analysis Engine</strong><br>
  <em>A Next-Generation Multi-Agent Gold Market Intelligence Analysis Engine</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/version-v1.0.0-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <strong>English</strong> | <a href="./README.md">中文文档</a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-overview">Overview</a> •
  <a href="#-agent-principles">Agent Principles</a> •
  <a href="#-system-showcase">System Showcase</a> •
  <a href="#-workflow">Workflow</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## ⚡ Overview

**GoldMind** is an intelligent gold market analysis platform based on **LangChain Multi-Agent Architecture**, integrating **ReAct reasoning framework**, **RAG (Retrieval-Augmented Generation)**, and **multi-model collaboration** technologies to provide investors with deep market insights.

The system is powered by dual engines: **GLM-4-Plus** (Zhipu AI) and **DeepSeek-V3**, with specialized Agents collaborating through division of labor: **Market Analysis Agent** handles technical quantitative analysis, **News Intelligence Agent** performs sentiment analysis based on real-time search, **Institution Research Agent** tracks mainstream institutional views, and **Investment Advisory Agent** generates strategic recommendations by integrating multi-source information. Each Agent achieves result fusion through structured output, forming a panoramic understanding of the gold market.

> You only need to: Follow gold market dynamics, the system automatically collects data and analyzes  
> GoldMind will return: Comprehensive analysis reports integrating price trends, market sentiment, and institutional views

### 🎯 Core Technical Architecture

**🚀 LangChain Multi-Agent Framework**  
A modular Agent system built on LangChain, with each Agent encapsulating independent analysis logic and toolchains. Through the `BaseAgent` abstract base class, unified LLM calling interfaces are supported, enabling flexible switching between DeepSeek and Zhipu AI dual-model backends. Agents collaborate through structured data transfer, avoiding single points of failure and enhancing system robustness.

**🌐 GLM-4-Plus Real-time Search Enhancement**  
Integrates Zhipu AI's **GLM-4-Plus** model's **Web Search** capability, enabling real-time retrieval and understanding of institutional research reports, financial news, and market dynamics. Compared to traditional static data sources, the system can capture the latest market changes, providing timely information support for analysis.

**🧠 DeepSeek Deep Reasoning & Multi-Agent Fusion**  
Adopts **DeepSeek-V3** as the core reasoning engine, leveraging its powerful long-text understanding and logical reasoning capabilities to fuse multi-Agent outputs. Through specially designed fusion Prompts, four-dimensional information (technical, fundamental, sentiment, and institutional views) is integrated to generate investment judgments with logical consistency.

**📊 ReAct Reasoning + RAG Retrieval Augmentation**  
Implements the **ReAct (Reasoning + Acting)** reasoning pattern within Agents: Thought (analyze current state) → Action (call tools to fetch data) → Observation (integrate observation results) → Final Answer (output conclusion). Combined with RAG technology to retrieve historical prices, news sentiment, and other contextual information from local databases, enhancing LLM factuality and accuracy.

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

### Dashboard
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/dashboard.jpeg" alt="Dashboard" width="800">
</p>

### Real-time Price Trends
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/price-chart.jpeg" alt="Price Chart" width="800">
</p>

### Bullish/Bearish Factor Analysis
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-up.jpeg" alt="Bullish Factors" width="400">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-down.jpeg" alt="Bearish Factors" width="400">
</p>

### Institutional Views
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/institutional-views.jpeg" alt="Institutional Views" width="800">
</p>

### Investment Advice
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/investment-advice.jpeg" alt="Investment Advice" width="800">
</p>

### Market Summary
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/market-summary.jpeg" alt="Market Summary" width="800">
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
# Zhipu AI - For real-time search, news analysis, institutional forecasts
# Get it at: https://open.bigmodel.cn/
ZHIPU_API_KEY=your_zhipu_api_key_here

# DeepSeek - For deep reasoning and investment advice generation
# Get it at: https://www.deepseek.com/
DEEPSEEK_API_KEY=your_deepseek_api_key_here
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
# Zhipu AI (Zhipu AI) - For real-time search, news analysis, institutional forecasts
# Get it at: https://open.bigmodel.cn/
ZHIPU_API_KEY=your_zhipu_api_key_here

# DeepSeek - For deep reasoning and investment advice generation
# Get it at: https://www.deepseek.com/
DEEPSEEK_API_KEY=your_deepseek_api_key_here
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

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GoldMind System Workflow                           │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────────┐
     │  Data Layer   │
     └──────┬───────┘
            │
     ┌──────▼───────┐     ┌──────────────────────────────────────────────────┐
     │ Data Sources  │────▶│ • Gold Price API (Yahoo Finance)                │
     │               │     │ • US Dollar Index API                            │
     │               │     │ • Web Search (Zhipu AI)                          │
     │               │     │ • News Websites                                  │
     └──────┬───────┘     └──────────────────────────────────────────────────┘
            │
            ▼
     ┌──────────────────────────────────────────────────────────────────────┐
     │                        Agent Analysis Layer                           │
     │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
     │  │ Market Analysis │  │ News Intelligence│  │Institution      │      │
     │  │     Agent       │  │     Agent       │  │Research Agent   │      │
     │  │                 │  │                 │  │                 │      │
     │  │• Price Trends   │  │• News Search    │  │• Institution    │      │
     │  │• Technical      │  │• Sentiment      │  │  Views Tracking │      │
     │  │  Indicators     │  │  Analysis       │  │• Report         │      │
     │  │• Pattern        │  │• Event          │  │  Analysis       │      │
     │  │  Recognition    │  │  Extraction     │  │                 │      │
     │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘      │
     │           │                    │                    │               │
     │           └────────────────────┼────────────────────┘               │
     │                                │                                    │
     │                                ▼                                    │
     │                    ┌─────────────────────┐                          │
     │                    │   Data Integration  │                          │
     │                    │   & Structured      │                          │
     │                    │   Output            │                          │
     │                    └──────────┬──────────┘                          │
     └───────────────────────────────┼──────────────────────────────────────┘
                                     │
                                     ▼
     ┌──────────────────────────────────────────────────────────────────────┐
     │                     DeepSeek Fusion Layer                             │
     │                                                                       │
     │  ┌─────────────────────────────────────────────────────────────────┐  │
     │  │              Investment Advisory Agent                           │  │
     │  │                                                                  │  │
     │  │  • Multi-dimensional Information Fusion                          │  │
     │  │  • Logical Consistency Check                                     │  │
     │  │  • Strategy Recommendation Generation                            │  │
     │  │  • Risk Assessment                                               │  │
     │  │                                                                  │  │
     │  │  Output: Comprehensive Investment Advice Report                  │  │
     │  └─────────────────────────────────────────────────────────────────┘  │
     └──────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
     ┌──────────────────────────────────────────────────────────────────────┐
     │                      Presentation Layer                               │
     │                                                                       │
     │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
     │  │   Price     │  │   Bullish/  │  │ Institution │  │ Investment  │ │
     │  │   Chart     │  │   Bearish   │  │    Views    │  │   Advice    │ │
     │  │             │  │   Factors   │  │             │  │             │ │
     │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
     │                                                                       │
     └──────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent Principles

### Agent Division of Labor Design

GoldMind adopts a **"Divide and Conquer, then Fuse"** design philosophy, with each Agent responsible for analysis in specific domains, ultimately integrated by the Investment Advisory Agent to form a comprehensive judgment.

#### Market Analysis Agent

**Responsibilities**: Technical quantitative analysis of gold prices

**Core Capabilities**:
- Price trend analysis (support/resistance levels, trend lines)
- Technical indicator calculation (RSI, MACD, Bollinger Bands, etc.)
- Pattern recognition (head and shoulders, double tops, triangles, etc.)
- Volatility analysis

**Output Format**:
```json
{
  "trend": "bullish/bearish/neutral",
  "support_levels": [2680, 2650],
  "resistance_levels": [2720, 2750],
  "indicators": {
    "rsi": 65.3,
    "macd": "bullish_cross"
  },
  "patterns": ["ascending_triangle"],
  "analysis": "Technical analysis text..."
}
```

#### News Intelligence Agent

**Responsibilities**: Real-time search and sentiment analysis of market news

**Core Capabilities**:
- Real-time Web search (Zhipu AI GLM-4-Plus Web Search)
- Financial news collection and filtering
- Sentiment analysis (bullish/bearish/neutral)
- Event extraction and impact assessment

**Output Format**:
```json
{
  "sentiment": "bullish",
  "confidence": 0.75,
  "key_events": [
    {
      "title": "Fed signals rate cuts",
      "impact": "high",
      "sentiment": "bullish"
    }
  ],
  "bullish_factors": ["factor1", "factor2"],
  "bearish_factors": ["factor3"],
  "analysis": "News analysis text..."
}
```

#### Institution Research Agent

**Responsibilities**: Tracking and analyzing mainstream institutional views

**Core Capabilities**:
- Collect institutional research reports and forecasts
- Extract key views and price targets
- Analyze consistency of institutional views
- Track changes in institutional positions

**Output Format**:
```json
{
  "institutions": [
    {
      "name": "Goldman Sachs",
      "rating": "buy",
      "target_price": 2800,
      "key_points": ["point1", "point2"]
    }
  ],
  "consensus": "bullish",
  "average_target": 2750,
  "analysis": "Institutional analysis text..."
}
```

#### Investment Advisory Agent

**Responsibilities**: Integrate multi-dimensional information to generate investment advice

**Core Capabilities**:
- Multi-Agent output fusion
- Logical consistency checking
- Strategy recommendation generation
- Risk assessment and position management

**Fusion Strategy**:
1. **Weighted Scoring**: Assign weights to different dimensions (technical 30%, fundamentals 25%, sentiment 25%, institutional 20%)
2. **Conflict Detection**: Identify contradictions between different Agent conclusions
3. **Confidence Calibration**: Adjust confidence based on data quality and timeliness
4. **Comprehensive Judgment**: Generate final investment advice

**Output Format**:
```json
{
  "recommendation": "buy/hold/sell",
  "confidence": 0.82,
  "rationale": "Comprehensive analysis text...",
  "risk_level": "medium",
  "position_suggestion": "30%",
  "time_horizon": "medium_term",
  "key_factors": ["factor1", "factor2"]
}
```

### ReAct Reasoning Pattern

Each Agent internally implements the ReAct (Reasoning + Acting) pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                      ReAct Loop                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Thought │───▶│  Action  │───▶│Observation│              │
│  │          │    │          │    │          │              │
│  │"Current  │    │Call Tool │    │"Data:..." │              │
│  │ gold     │    │or Search │    │          │              │
│  │ price is │    │          │    │          │              │
│  │ 2700,    │    │          │    │          │              │
│  │ need to  │    │          │    │          │              │
│  │ analyze  │    │          │    │          │              │
│  │ trend"   │    │          │    │          │              │
│  └──────────┘    └──────────┘    └─────┬────┘              │
│       ▲                                │                    │
│       │                                │                    │
│       └────────────────────────────────┘                    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    Final Answer                       │  │
│  │  "Based on technical analysis, current gold price    │  │
│  │   shows an upward trend, recommend buying..."        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### RAG Retrieval Enhancement

The system uses RAG technology to enhance LLM factuality:

**Retrieval Content**:
- Historical gold price data (2025 to present)
- Historical US dollar index data
- Past news sentiment records
- Historical institutional view records

**Retrieval Strategy**:
- Time-based: Retrieve data from the most recent 30 days
- Similarity-based: Retrieve historical periods similar to current market conditions
- Relevance-based: Retrieve information relevant to current analysis questions

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

- [LangChain](https://github.com/langchain-ai/langchain) - LLM application development framework
- [DeepSeek](https://www.deepseek.com/) - Deep reasoning model
- [Zhipu AI](https://open.bigmodel.cn/) - GLM-4-Plus model and Web Search capability
- [FastAPI](https://fastapi.tiangolo.com/) - High-performance Python web framework
- [React](https://react.dev/) - Frontend UI library
- [Recharts](https://recharts.org/) - React charting library

---

## 📧 Contact Author

If you have any questions, suggestions, or collaboration inquiries, please feel free to contact us:

- 📮 **Email**: JasonBuildAI@gmail.com
- 📮 **QQ**: 3310145612@qq.com

---

<p align="center">
  <strong>GoldMind</strong> - Empowering Investment Decisions with Intelligence
</p>

<p align="center">
  <a href="https://github.com/JasonBuildAI/GoldMind">⭐ Star us on GitHub</a> •
  <a href="https://github.com/JasonBuildAI/GoldMind/issues">🐛 Submit Issue</a> •
  <a href="https://github.com/JasonBuildAI/GoldMind/discussions">💬 Join Discussion</a>
</p>
