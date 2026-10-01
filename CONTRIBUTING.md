# 贡献指南 | Contributing to GoldMind

> 🌐 **中文** | [English](./CONTRIBUTING_EN.md)

感谢您考虑为 GoldMind 做出贡献！

## 🎯 贡献方式

- **报告 Bug** - 创建 Issue 描述问题
- **建议功能** - 创建 Issue 提出建议
- **编写代码** - 提交 Pull Request
- **改进文档** - 完善 README 和代码注释

## 🚀 快速开始

### 1. Fork 并克隆

```bash
git clone https://github.com/YOUR_USERNAME/GoldMind.git
cd GoldMind
```

### 2. 搭建开发环境

参考 [README.md](README.md) 中的快速开始指南。

### 3. 创建分支

```bash
# 功能分支
git checkout -b feature/功能名称

# 修复分支
git checkout -b fix/bug描述
```

## 📋 开发规范

### 技术栈

**后端**
- Python 3.11+
- FastAPI
- SQLAlchemy
- MySQL

**前端**
- React 19
- TypeScript 5.9（`strict: true`）
- Tailwind CSS 3

**AI**
- 任何 OpenAI 兼容的 LLM 端点（OpenAI / DeepSeek / 通义 / Kimi / Ollama / 小米 MiMo 等，
  配置面见 `README.md`）—— 所有调用只经 `backend/app/services/llm_provider.py`

### 代码风格

#### Python

- 遵循 PEP 8
- 使用类型提示
- 编写文档字符串

#### TypeScript

- 使用严格模式（`tsconfig.app.json` 里 `strict: true`）
- 有意义的变量名
- 复杂逻辑添加注释

### 提交信息规范

前缀的**唯一真源是 [`AGENTS.md`](AGENTS.md) 的硬性要求第 2 条**，这里只列常用几个：

```
feat: 添加新功能        fix: 修复 Bug
refactor: 代码重构      perf: 性能优化
docs: 更新文档          test: 添加测试
chore: 构建/依赖更新    build: 构建系统      ci: CI 配置
```

一个 commit 只用一个前缀、只做一件事；第一行说清改了什么。
注意 message **用英文**（见 `AGENTS.md`）。

## 🏗️ 项目结构

```
GoldMind/
├── app/                    # 前端（React + TypeScript）
│   ├── src/
│   │   ├── sections/      # 页面区块
│   │   ├── components/    # 可复用组件
│   │   └── services/      # API 服务
│   └── package.json
├── backend/               # 后端（FastAPI + Python）
│   ├── app/
│   │   ├── services/      # 业务逻辑（含 llm_provider 与 single_flight）
│   │   ├── routers/       # API 路由
│   │   ├── models/        # 数据模型
│   │   └── utils/         # 限流等
│   ├── tests/             # unit / integration / e2e
│   └── requirements.txt
├── docs/                  # 产品方向、架构、API、密钥与隐私
└── README.md
```

## 🔒 安全规范

**重要**：永远不要提交以下敏感信息

- LLM API 密钥（任何供应商）
- 数据库密码
- 私钥或证书

**正确做法**：
- 使用 `.env` 文件存储敏感信息
- 确保 `.env` 在 `.gitignore` 中
- 提交前检查 `git diff`

**已自动化**：`backend/tests/unit/test_no_secrets_in_repo.py` 会扫描所有受版本控制
的文件，密钥形状的字符串、个人邮箱与 QQ 号都会让闸门变红。它守的是「从此往后」，
历史里的泄漏只能靠重写来消除（步骤见 `docs/10-密钥与隐私.md`）。

## 🐛 报告 Bug

创建 Issue 时包含：

- 问题描述
- 复现步骤
- 期望行为 vs 实际行为
- 环境信息（OS、Python/Node 版本）
- 错误日志

## 💡 建议功能

- 使用场景
- 建议方案
- 替代方案（如有）

## 📄 许可证

通过贡献，您同意您的贡献将在 MIT 许可证下授权。

---

感谢您对 GoldMind 的贡献！
