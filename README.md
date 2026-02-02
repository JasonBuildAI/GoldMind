<p align="center">
  <img src="https://img.shields.io/badge/GoldMind-AI%20Gold%20Analysis-gold?style=for-the-badge&logo=chart-line&logoColor=white" alt="GoldMind">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>AI驱动的黄金市场智能分析平台</strong>
</p>

<p align="center">
  <a href="https://github.com/JasonBuildAI/GoldMind/stargazers">
    <img src="https://img.shields.io/github/stars/JasonBuildAI/GoldMind?style=social" alt="GitHub Stars">
  </a>
  <a href="https://github.com/JasonBuildAI/GoldMind/network/members">
    <img src="https://img.shields.io/github/forks/JasonBuildAI/GoldMind?style=social" alt="GitHub Forks">
  </a>
  <a href="https://github.com/JasonBuildAI/GoldMind/issues">
    <img src="https://img.shields.io/github/issues/JasonBuildAI/GoldMind" alt="GitHub Issues">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/JasonBuildAI/GoldMind" alt="License">
  </a>
</p>

<p align="center">
  <a href="#-功能特性">功能特性</a> •
  <a href="#-技术架构">技术架构</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-文档">文档</a> •
  <a href="#-贡献">贡献</a>
</p>

---

## ⚡ 项目概述

**GoldMind** 是一款基于多智能体协作技术的下一代黄金市场智能分析引擎。通过构建高保真的数字孪生市场，将全球黄金市场的实时行情、宏观经济信号、地缘政治事件与舆情情绪等多维数据注入「智能体社会」——在此空间内，**Market Agent**（市场分析器）、**News Agent**（舆情解析器）、**Insight Agent**（趋势洞察器）与**Advisor Agent**（策略建议器）四大专业智能体进行链式思维碰撞与协同推演，突破单一模型的认知局限，生成具备深度、准度与多维视角的投资决策支持。

> 你只需：关注黄金市场动态，系统7×24小时自动采集全球数据并实时分析  
> GoldMind 将返回：一份融合技术面、基本面、情绪面的综合分析报告，以及基于多智能体共识的投资策略建议

### 🎯 核心能力

**🚀 多智能体协同分析引擎**  
系统不仅依赖单一LLM进行分析，更融合了多智能体协作架构与深度学习模型。通过Market Agent进行技术面量化分析、News Agent进行舆情情绪识别、Insight Agent进行趋势推演、Advisor Agent进行策略生成——多智能体在独立的「论坛」环境中进行思维碰撞与辩论，由Orchestrator Engine协调并引导，确保分析结果的深度、准度与多维视角。

**🌐 全域数据感知与实时处理**  
系统配备分布式数据采集集群，可对伦敦金、纽约金、上海金等全球主要市场的实时行情进行毫秒级捕获；同时整合宏观经济指标、央行政策、地缘政治事件等10+维度数据源进行7×24小时监控。具备强大的多模态解析能力，能深度处理新闻文本、社交媒体情绪与市场交易信号。

**🧠 智能体「论坛」协作机制**  
系统的技术核心之一。每个Agent在独立的「论坛」环境中进行链式思维碰撞与辩论，由Forum Engine监控并引导。这种机制避免了单一模型的思维局限与交流导致的同质化，催生出更高质量的集体智能——让AI像专业投研团队一样进行头脑风暴与交叉验证。

**📊 轻量化与高扩展性框架**  
基于纯Python模块化设计，实现轻量化、一键式部署。代码结构清晰，开发者可轻松集成自定义数据源、分析模型与业务逻辑，实现平台的快速扩展与深度定制。支持从个人投资者到机构级部署的弹性架构。

---

## ✨ 功能特性

### 📊 数据服务
| 功能 | 描述 | 状态 |
|------|------|------|
| 实时金价 | 伦敦金、纽约金、上海金实时报价 | ✅ |
| 历史数据 | 支持日线、周线、月线历史查询 | ✅ |
| 汇率换算 | 多币种实时汇率转换 | ✅ |
| 数据缓存 | Redis高性能缓存机制 | ✅ |

### 🤖 AI分析
| 功能 | 描述 | 状态 |
|------|------|------|
| 趋势分析 | 基于技术指标的趋势判断 | ✅ |
| 新闻分析 | 实时新闻舆情情绪分析 | ✅ |
| 机构观点 | 汇总主流机构预测观点 | ✅ |
| 多空因素 | 自动识别影响金价的利多利空因素 | ✅ |

### 🖥️ 前端展示
| 功能 | 描述 | 状态 |
|------|------|------|
| 价格图表 | 交互式K线图与技术指标 | ✅ |
| 仪表盘 | 实时数据监控面板 | ✅ |
| 响应式设计 | 支持桌面端和移动端 | ✅ |
| 深色模式 | 自适应深色主题 | ✅ |

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   React 18   │  │  TypeScript  │  │  TailwindCSS │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        API网关层                             │
│                    FastAPI + Uvicorn                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      智能体调度层                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  市场分析器   │  │  新闻分析器   │  │  预测生成器   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       数据服务层                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    MySQL     │  │    Redis     │  │   外部API    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

**后端**
- **框架**: FastAPI (Python 3.11+)
- **数据库**: MySQL 8.0 + SQLAlchemy
- **缓存**: Redis
- **AI模型**: DeepSeek API / Zhipu AI
- **任务调度**: APScheduler

**前端**
- **框架**: React 18 + TypeScript
- **构建**: Vite
- **样式**: Tailwind CSS
- **组件**: Radix UI + shadcn/ui
- **图表**: Recharts

**基础设施**
- **容器化**: Docker + Docker Compose
- **版本控制**: Git

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8.0
- Redis 7.0
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
