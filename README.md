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

## 📖 项目简介

**GoldMind** 是一个基于多智能体架构的AI驱动黄金市场分析平台。通过整合实时金价数据、新闻舆情分析和机器学习预测，为投资者提供全方位的黄金市场洞察。

### 🎯 核心能力

- **实时数据监控** - 自动采集全球主要市场黄金实时价格
- **AI智能分析** - 多智能体协作进行技术面、基本面、情绪面分析
- **预测与建议** - 基于历史数据和市场情绪生成投资建议
- **可视化展示** - 现代化Web界面展示分析结果

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
