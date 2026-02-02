<p align="center">
  <img src="docs\images\6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>基于多智能体协作的下一代黄金市场智能分析引擎</strong><br>
  <em>A Next-Generation Multi-Agent Gold Market Intelligence Analysis Engine</em>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/JasonBuildAI/GoldMind?color=blue&label=stars&style=flat-square" alt="Stars">
  <img src="https://img.shields.io/github/watchers/JasonBuildAI/GoldMind?color=green&label=watchers&style=flat-square" alt="Watchers">
  <img src="https://img.shields.io/github/forks/JasonBuildAI/GoldMind?color=orange&label=forks&style=flat-square" alt="Forks">
  <img src="https://img.shields.io/github/issues/JasonBuildAI/GoldMind?color=red&label=issues&style=flat-square" alt="Issues">
  <img src="https://img.shields.io/github/issues-pr/JasonBuildAI/GoldMind?color=purple&label=pull%20requests&style=flat-square" alt="Pull Requests">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Ask%20DeepWiki-智能问答-blue?style=flat-square&logo=bookstack" alt="DeepWiki">
  <img src="https://img.shields.io/badge/Docker-部署就绪-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/version-v1.0.0-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <a href="./README_EN.md">English</a> | <strong>中文文档</strong>
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> •
  <a href="#-文档">文档</a> •
  <a href="#-贡献">贡献</a>
</p>

---

## ⚡ 项目概述

**GoldMind** 是一个基于 **LangChain Multi-Agent 架构** 的黄金市场智能分析平台，融合 **ReAct 推理框架**、**RAG（检索增强生成）** 与 **多模型协作** 技术，为投资者提供深度市场洞察。

系统基于 **GLM-4-Plus**（智谱AI）与 **DeepSeek-V3** 双引擎驱动，通过专用 Agent 分工协作：**Market Analysis Agent** 负责技术面量化分析，**News Intelligence Agent** 基于实时搜索进行舆情解析，**Institution Research Agent** 追踪主流机构观点，**Investment Advisory Agent** 融合多源信息生成策略建议。各 Agent 通过结构化输出实现结果融合，形成对黄金市场的全景认知。

> 你只需：关注黄金市场动态，系统自动采集数据并分析  
> GoldMind 将返回：融合价格走势、市场情绪、机构观点的综合分析报告

### 🎯 核心技术架构

**🚀 LangChain Multi-Agent 框架**  
基于 LangChain 构建的模块化 Agent 系统，每个 Agent 封装独立的分析逻辑与工具链。通过 `BaseAgent` 抽象基类统一 LLM 调用接口，支持 DeepSeek 与智谱AI 双模型后端灵活切换。Agent 间通过结构化数据传递实现协作，避免单点失效，提升系统鲁棒性。

**🌐 GLM-4-Plus 实时搜索增强**  
集成智谱AI **GLM-4-Plus** 模型的 **Web Search** 能力，实现对机构研报、财经新闻、市场动态的实时检索与理解。相比传统静态数据源，系统能够捕捉最新市场变化，为分析提供时效性信息支撑。

**🧠 DeepSeek 深度推理与多 Agent 融合**  
采用 **DeepSeek-V3** 作为核心推理引擎，结合其强大的长文本理解与逻辑推理能力，对多 Agent 输出进行融合分析。通过设计特定的融合 Prompt，将技术面、基本面、情绪面、机构观点四维信息整合，生成具备逻辑一致性的投资判断。

**📊 ReAct 推理 + RAG 检索增强**  
在 Agent 内部实现 **ReAct（Reasoning + Acting）** 推理模式：Thought（分析当前状态）→ Action（调用工具获取数据）→ Observation（整合观察结果）→ Final Answer（输出结论）。结合 RAG 技术从本地数据库检索历史价格、新闻舆情等上下文信息，增强 LLM 的事实性与准确性。

---

## 📸 系统截图

### 首页仪表盘
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/dashboard.jpeg" alt="Dashboard" width="800">
</p>

### 实时价格走势
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/price-chart.jpeg" alt="Price Chart" width="800">
</p>

### 多空因素分析
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-up.jpeg" alt="Bullish Factors" width="400">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-down.jpeg" alt="Bearish Factors" width="400">
</p>

### 机构观点
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/institutional-views.jpeg" alt="Institutional Views" width="800">
</p>

### 投资建议
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/investment-advice.jpeg" alt="Investment Advice" width="800">
</p>

### 市场总结
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/market-summary.jpeg" alt="Market Summary" width="800">
</p>

---

## 🔄 工作流程

1. **数据采集层**：实时金价API抓取 & 新闻舆情Web搜索 & 机构研报智能检索
2. **多Agent并行分析**：Market Analysis Agent技术面量化 & News Intelligence Agent情绪解析 & Institution Research Agent观点追踪
3. **ReAct推理决策**：各Agent基于RAG检索历史数据 → Thought分析 → Action工具调用 → Observation整合 → Final Answer输出
4. **结果融合引擎**：DeepSeek-V3接收四维结构化数据 → 多源信息交叉验证 → 逻辑一致性校验 → 生成综合投资判断
5. **智能报告生成**：Investment Advisory Agent整合所有分析结果 → 生成策略建议与风险提示 → 结构化JSON响应前端可视化

---

## 🤖 Agent原理

### 📈 市场分析 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + 智谱AI GLM-4-Plus |
| **大模型** | 智谱AI GLM-4-Plus (支持实时搜索) |
| **架构** | ReAct推理架构 + 实时搜索插件 |
| **功能逻辑** | 基于24小时新闻与市场数据，智能提取看涨/看空因子 |
| **数据来源** | 智谱AI实时搜索 + 腾讯财经API + MySQL历史数据 |

---

### 🏛️ 机构预测 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + 智谱AI GLM-4-Plus |
| **大模型** | 智谱AI GLM-4-Plus (支持实时搜索) |
| **架构** | 专用Agent架构 + Web Search实时检索插件 |
| **功能逻辑** | 实时抓取高盛、瑞银、摩根士丹利、花旗等主流机构最新黄金预测观点，提取目标价位与逻辑依据 |
| **数据来源** | 智谱AI实时搜索 + 机构官方研报 + 权威财经新闻 |

---

### 📰 新闻分析 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + 智谱AI GLM-4-Plus |
| **大模型** | 智谱AI GLM-4-Plus (支持实时搜索) |
| **架构** | 实时搜索 + 情感分析 + 多空因子提取 |
| **功能逻辑** | 24小时滚动抓取黄金市场相关新闻，分析情感倾向，智能提取看涨/看空因子及其市场影响权重 |
| **数据来源** | 智谱AI实时搜索 + 新浪财经 + 腾讯财经 + 金十数据 |

---

### 💡 投资建议 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + DeepSeek-V3 + RAG |
| **大模型** | DeepSeek-V3 (671B参数) |
| **架构** | RAG检索增强生成 + 多源分析结果融合 |
| **功能逻辑** | 综合分析市场分析Agent、机构预测Agent、新闻分析Agent的输出结果，生成个性化投资策略与风险提示 |
| **数据来源** | 市场分析Agent结构化输出 + 机构预测Agent观点汇总 + 新闻分析Agent情绪数据 |

---

### 🧠 综合分析 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + DeepSeek-V3 + 多Agent协作 |
| **大模型** | DeepSeek-V3 (671B参数) |
| **架构** | 多Agent结果融合 + 深度推理生成 + 结构化输出 |
| **功能逻辑** | 整合所有Agent分析结果，进行交叉验证与逻辑一致性校验，生成全面市场认知与投资判断，输出包含技术面、基本面、情绪面、机构观点的四维综合分析报告 |
| **数据来源** | 市场分析Agent + 机构预测Agent + 新闻分析Agent + 投资建议Agent |

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8.0
- Docker (可选)

### 方式一：Docker部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/JasonBuildAI/GoldMind.git
cd GoldMind

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入你的API密钥

# 3. 启动服务
docker-compose up -d

# 4. 访问应用
# 前端: http://localhost:5173
# API文档: http://localhost:8000/docs
```

### 方式二：本地开发

**1. 后端启动**

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库和API配置

# 初始化数据库
python init_db.py

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**2. 前端启动**

```bash
cd app

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:5173
```

---

## 📚 文档

| 文档 | 说明 | 链接 |
|------|------|------|
| API文档 | 接口规范与示例 | [docs/API.md](./docs/API.md) |
| 架构设计 | 系统架构详解 | [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) |
| 贡献指南 | 如何参与项目 | [CONTRIBUTING.md](./CONTRIBUTING.md) |

---

## 🤝 贡献

我们欢迎所有形式的贡献！请查看我们的[贡献指南](./CONTRIBUTING.md)了解如何参与项目。

### 贡献者

<a href="https://github.com/JasonBuildAI/GoldMind/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=JasonBuildAI/GoldMind" alt="Contributors" />
</a>

---

## 📄 许可证

本项目采用 [MIT 许可证](./LICENSE) 开源。

---

## 🙏 致谢

- [DeepSeek](https://deepseek.com/) - 提供AI模型支持
- [智谱AI](https://www.zhipuai.cn/) - 提供大语言模型API
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能Web框架
- [React](https://react.dev/) - 前端UI框架

---

<p align="center">
  <strong>⭐ 如果这个项目对你有帮助，请给我们一个Star！</strong>
</p>

<p align="center">
  Made with ❤️ by <a href="https://github.com/JasonBuildAI">JasonBuildAI</a>
</p>
