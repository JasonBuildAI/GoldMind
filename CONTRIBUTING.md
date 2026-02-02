# 贡献指南 | Contributing to GoldMind

首先，感谢您考虑为 GoldMind 做出贡献！正是像您这样的人让这个项目成为社区的优秀工具。

## 🎯 贡献方式

- **报告 Bug** - 创建带有 bug 标签的 Issue
- **建议功能** - 创建带有 enhancement 标签的 Issue
- **编写代码** - 提交 Bug 修复或新功能的 Pull Request
- **改进文档** - 帮助我们改进 README、文档和代码注释
- **分享想法** - 参与讨论并分享您的想法

## 🚀 快速开始

### 1. Fork 并克隆

```bash
# 在 GitHub 上 Fork 本仓库，然后克隆您的 Fork
git clone https://github.com/YOUR_USERNAME/goldmind.git
cd goldmind
```

### 2. 搭建开发环境

按照 [README.md](README.md#-快速开始) 中的快速开始指南设置本地环境。

### 3. 创建分支

```bash
# 功能分支
git checkout -b feature/功能名称

# 或修复分支
git checkout -b fix/bug描述
```

## 📋 开发规范

### 代码风格

#### Python（后端）

- 遵循 PEP 8 代码风格指南
- 尽可能使用类型提示
- 为函数和类编写文档字符串
- 使用 `black` 进行代码格式化
- 使用 `flake8` 进行代码检查

```bash
# 格式化代码
black backend/app

# 检查代码规范
flake8 backend/app
```

#### TypeScript（前端）

- 遵循现有的代码风格
- 使用 TypeScript 严格模式
- 使用有意义的变量名
- 为复杂逻辑添加注释

```bash
# 检查 TypeScript
cd app && npm run build

# 代码检查
cd app && npm run lint
```

### 提交信息规范

使用约定式提交格式：

```
feat: 添加白银价格分析智能体
fix: 解决数据库连接超时问题
docs: 更新 API 文档
refactor: 优化缓存机制
test: 为黄金服务添加单元测试
style: 调整代码格式
chore: 更新依赖版本
```

**提交类型说明：**

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式调整（不影响功能）|
| `refactor` | 代码重构 |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖更新 |

### Pull Request 流程

1. **更新文档** - 如果您修改了 API，请更新 README
2. **添加测试** - 为新功能包含测试用例
3. **确保 CI 通过** - 所有检查必须通过
4. **请求审查** - @提及维护者进行审查
5. **处理反馈** - 根据要求进行修改
6. **合并** - 维护者会在合适时合并

## 🏗️ 项目结构

```
goldmind/
├── app/                    # 前端（React + TypeScript）
│   ├── src/
│   │   ├── sections/      # 页面区块
│   │   ├── components/    # 可复用组件
│   │   ├── services/      # API 服务
│   │   └── contexts/      # React 上下文
│   └── README.md
├── backend/               # 后端（FastAPI + Python）
│   ├── app/
│   │   ├── agents/        # AI 智能体
│   │   ├── services/      # 业务逻辑
│   │   ├── routers/       # API 端点
│   │   ├── models/        # 数据库模型
│   │   └── schemas/       # Pydantic 模式
│   └── README.md
└── docs/                  # 文档
```

## 🧪 测试

### 后端测试

```bash
cd backend
pytest tests/
```

### 前端测试

```bash
cd app
npm test
```

## 📝 文档规范

- 修改安装说明时更新 README.md
- 为新函数添加 JSDoc 注释
- 修改端点时更新 API 文档
- 重大变更添加架构图

## 🐛 报告 Bug

报告 Bug 时请包含以下信息：

- **问题描述** - 清晰的 Bug 描述
- **复现步骤** - 如何触发该 Bug
- **期望行为** - 应该发生什么
- **实际行为** - 实际发生了什么
- **截图** - 如适用
- **环境信息** - 操作系统、Python/Node 版本
- **日志** - 错误信息和堆栈跟踪

**Bug 报告模板：**

```markdown
## 问题描述
[清晰简洁地描述 Bug]

## 复现步骤
1. 进入 '...'
2. 点击 '...'
3. 滚动到 '...'
4. 出现错误

## 期望行为
[描述您期望发生的情况]

## 实际行为
[描述实际发生的情况]

## 环境信息
- OS: [例如 Windows 11]
- Python: [例如 3.11.0]
- Node: [例如 18.0.0]
- 浏览器: [例如 Chrome 120]

## 截图
[如有截图请添加]

## 附加信息
[其他相关信息]
```

## 💡 建议功能

功能建议应包含：

- **使用场景** - 为什么需要这个功能？
- **建议方案** - 它应该如何工作？
- **替代方案** - 考虑过的其他方法
- **附加信息** - 原型图、示例等

**功能请求模板：**

```markdown
## 功能描述
[清晰简洁地描述您想要的功能]

## 使用场景
[描述这个功能将解决什么问题]

## 建议方案
[描述您希望它如何工作]

## 替代方案
[描述您考虑过的其他解决方案]

## 附加信息
[原型图、示例或其他上下文]
```

## 🎨 设计规范

### UI 组件

- 使用 Tailwind CSS 进行样式设计
- 遵循现有的配色方案（金色/琥珀色主题）
- 确保响应式设计
- 保持可访问性标准

### API 设计

- 使用 RESTful 规范
- 返回一致的响应格式
- 包含正确的 HTTP 状态码
- 使用 OpenAPI/Swagger 进行文档化

**响应格式示例：**

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

```json
{
  "success": false,
  "error": "错误信息",
  "code": "ERROR_CODE"
}
```

## 🔒 安全规范

- 永远不要提交 API 密钥或机密信息
- 使用环境变量存储敏感数据
- 遵循 OWASP 安全指南
- 私下报告安全问题

## 📞 获取帮助

- **GitHub Issues** - 用于 Bug 报告和功能请求
- **GitHub Discussions** - 用于问题和想法讨论
- **邮件** - 安全问题请发送至: security@goldmind.ai

## 🏆 贡献者认可

贡献者将被：
- 列入 README.md 的致谢部分
- 在发布说明中提及
- 添加到贡献者图表

## 📄 许可证

通过贡献，您同意您的贡献将在 MIT 许可证下授权。

---

感谢您对 GoldMind 的贡献！🚀
