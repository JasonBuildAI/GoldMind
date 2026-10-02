<p align="center">
  <img src="docs/images/6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>面向国际黄金市场的 AI 数据分析引擎</strong><br>
  <em>An AI Data Analysis Engine for the International Gold Market</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0.2-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/released-2026--10--03-success?style=flat-square" alt="Release date">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/SQLite-零配置复现-003B57?style=flat-square&logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <a href="./README_EN.md">English</a> | <strong>中文文档</strong>
</p>

---

<!-- ⬇️⬇️⬇️ 发布横幅：改版本时这几行一起改 ⬇️⬇️⬇️ -->

<h1 align="center">🎉 GoldMind 2.0.2 正式发布</h1>

<h2 align="center">GoldMind 2.0.2 is here</h2>

<p align="center">
  <img src="https://img.shields.io/badge/release-v2.0.2-FFD700?style=for-the-badge" alt="v2.0.2">
  <img src="https://img.shields.io/badge/released-2026--10--03-2EA043?style=for-the-badge" alt="2026-10-03">
</p>

<p align="center">
  <strong>填一次 <code>backend/.env</code>，剩下全部自动：建库、迁移、回填、分析、备份、自检。</strong><br>
  <em>Configure <code>backend/.env</code> once; everything else runs itself — schema, backfill, analysis, backups, health checks.</em><br><br>
  📋 <a href="./CHANGELOG.md">更新日志 CHANGELOG</a> ·
  🌍 <a href="./CHANGELOG_EN.md">Changelog (EN)</a> ·
  🚀 <a href="https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.2">GitHub Release v2.0.2</a>
</p>

<!-- ⬆️⬆️⬆️ 发布横幅结束 ⬆️⬆️⬆️ -->

---

## 🆕 2.0.2 带来了什么

2.0.2 的目标只有一句话：**填一次 `backend/.env`，之后零人工**。围绕它落地了 20 条评审里
能自主完成的高价值项，重写了前端，并把「每个数字都标出处」推到金价口径层面。

| 方向 | 2.0.1 | 2.0.2 |
|---|---|---|
| 启动 | 要手动跑 `init_db.py` / 回填 / 首次分析 | 启动引导自动建表、自动迁移、按覆盖度回填、自动首轮分析；`/health.bootstrap` 显示「第 N 步 / 共 M 步」，失败下轮自动重试，重复启动不重复回填 |
| 配置 | 改 `.env` 必须重启 | LLM 配置热生效（`CONFIG_WATCH`）：watcher 检测到变化即重载，并立刻补一轮分析 |
| 调度 | 错过的 cron 窗口就错过了 | 启动即补差；所有任务 `coalesce` + `misfire_grace_time`；每日自动备份（SQLite 留 7 份）与数据体检（只修安全项，先备份） |
| 金价口径 | 同一页三个「金价」不加区分 | 每个价格附 `basis`（实时报价 / 日收盘 / 量化基准）、来源与 as-of；同日实时与收盘偏差 > 3% 进体检点名 |
| 量化 | 五个尺度都给方向 | 250 日尺度停发方向（`direction_status: not_published` + 原因，保留公允价值偏离与校准区间）；一级指标换成「相对永远看多的增量（含置信区间）」与「敢喊跌质量」；前向裁决加 Beta 后验、与 CRPS 并排；因子按发布滞后对齐（`quant-v7`，前向窗口重封板 2026-10-03） |
| 付费调用 | 每次刷新都真调 LLM | 输入指纹不变就跳过重算（强制刷新不受限）；`LLM_DAILY_CALL_BUDGET` 默认 200/日，用尽后如实显示「暂不可用」，不编内容 |
| 前端 | 七节信息密度高、层级混乱 | 重写为「报头（今日速览 + 数据新鲜度）→ 今日结论 → 行情 → 驱动 → 量化 → 策略 → 数据与方法」；每节「一句话结论 + 关键数字 + 一层折叠」，所有 API 字段都有展示位 |
| 可复核性 | 服务库与研究长库的分歧要人工核对 | 启动引导自动对齐两个库；实测 10902 行分歧清零，`check_data_sanity --strict` 通过；每条源记录尝试流水（`/api/gold/sources/status`） |

2.0.1 的改动（分布口径、独立下注、前向窗口……）见 [CHANGELOG](./CHANGELOG.md) 的 `[2.0.1]` 一节。

---

<p align="center">
  <a href="#-项目概述">项目概述</a> •
  <a href="#-量化策略">量化策略</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-常用命令">常用命令</a> •
  <a href="#-目录结构">目录结构</a> •
  <a href="#-文档地图">文档地图</a> •
  <a href="#-诚实声明实现边界">诚实声明</a> •
  <a href="#-贡献">贡献</a>
</p>

---

## ⚡ 项目概述

**GoldMind** 是一个黄金市场分析看板：自动采集金价与美元指数，用大语言模型基于最近的新闻生成
多空对照、机构观点、投资策略与市场总结，并以量化引擎基于四类影响因素（货币政策与利率 /
避险与信用 / 供需结构 / 市场与技术面）预测 1 / 5 / 20 / 60 / 250 个交易日（日内～一周、
1～3 个月、6～18 个月）的方向、目标价与情景（全部出自同一份校准分布，未校准的因子偏向折进
详情作对照），以一张单页的**浅色研究简报**呈现 —— 七节（行情 / 多空对照 / 机构观点 / 消息 /
投资策略 / 量化预测 / 总结）全部左对齐，无渐变、无阴影、无卡片套件；数字表格化，红涨绿跌，
且方向同时给符号与文字。「消息」板块从央行 / 通讯社 / 行业机构 / 专业财经等高权威来源抓取
黄金相关消息，按重要性与置信度确定性排序，24 小时 / 7 天 / 30 天三个窗口各取前 10 条。
另有一张独立的**研究页**（`/research.html`）：把预注册候选 × 尺度的全档评估、
覆盖率、可靠性分桶与逐因子拆解直接摆出来，**包括没有过线的结论**。

LLM 供应商**不写死**：任何 OpenAI 兼容端点（OpenAI / DeepSeek / 通义 / Kimi /
Ollama 本地模型 / 小米 MiMo ……）都能接 —— 改 `backend/.env` 里的
`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 三项即可，所有 LLM 客户端统一经
`backend/app/services/llm_provider.py` 构造。三项缺任意一项都算「未配置」，
各区块如实显示「暂不可用」，不会退回任何内置内容。

付费调用有空门控（`backend/app/services/llm_gate.py`）：prompt 去掉易变的
时间戳后做 sha256 指纹，**输入没变且缓存还在时直接复用，不再调用模型**；
`POST .../refresh` 是显式刷新，不受指纹限制。每日调用次数由
`LLM_DAILY_CALL_BUDGET` 封顶（默认 200，设 0 表示不设上限）——超限时该轮分析
如实显示「暂不可用」并说明原因，不会为了填满页面继续花钱。状态文件在
`backend/cache/llm_gate.json`（gitignored，不入库）。

> 你只需：打开页面
> GoldMind 将返回：当天金价、美元指数，以及基于最近新闻生成的多空分析与策略建议，
> 外加一份可回测的量化预测。

> 📌 产品边界与已知限制见 [`docs/00-产品方向.md`](docs/00-产品方向.md)。
> **该文档中标记为「目标」的能力尚未实现，请勿当作已有功能。**

### 🧩 实际的分析链路

```
行情采集 ──► SQLite ──┐
RSS 新闻 ──► SQLite ──┼──► 拼装 prompt ──► llm.invoke() ──► 解析 JSON ──► 缓存 ──► 前端看板
                     │
                     └──► （可选）插件式 web_search（LLM_SEARCH_ENABLED，默认关）

公开数据源 ──► 因子观测表 ──► 滚动 z 分数 ──► 分尺度权重合成 ──► 一份校准分布 ──► 量化预测
（财政部 / 纽联储 / CFTC /        │（当前值 + 追加式修订流水，--as-of 可重建历史面板）
 Yahoo / RSS，全部免密钥）        │
                                  ├──► 走查式回测（独立下注 / HAC / 四段样本期 / 分档覆盖率）
                                  └──► 监测仪表盘（22 行水位，含 6 条不给方向的信息行）
```

| 分析服务 | 输入 | 输出 |
|---|---|---|
| 看涨因子 | 最近 24h 新闻（高权威消息 + RSS，去重合并）+ 金价 | 5 个看涨因子 |
| 看跌因子 | 最近 24h 新闻（高权威消息 + RSS，去重合并）+ 金价 | 5 个看跌因子 |
| 机构观点 | 最近 30 天新闻（同上）+（搜索） | 四家机构最近一次可核实的预测（含日期与来源） |
| 投资建议 | 市场状态 + 多空因子 + 机构观点 + 最近新闻（同上） | 保守/均衡/机会三档策略 |
| 市场总结 | 上述全部 | 核心逻辑、风险、综合判断 |

> 新闻输入 = `gold_news` 与消息板块（13 个高权威源）按规范化 URL 去重合并，消息板块优先；
> prompt 里每条给「标题 + 清洗截断后的摘要」。新闻、价格上下文与能力声明由同一份
> 「分析输入包」组装（`build_analysis_input`，同窗口、同口径），见 `backend/app/services/analysis_input.py`。

---

## 🌟 我们的愿景

**GoldMind** 致力于通过社区共同努力，打造一个**真实可用的 AI Agent 国际黄金市场数据分析与价格预测平台**。

我们希望通过技术创新：

- 📉 **减少信息差** - 让每位投资者都能获取专业级的市场分析
- 🛡️ **增强风险抵抗能力** - 提供多维度的风险评估和预警
- 💡 **切实可行的投资建议** - 基于数据和逻辑，给出可操作的投资策略

> 🤝 **期望您的加入！** 无论是代码贡献、功能建议还是使用反馈，都将成为推动项目前进的重要力量。

如果该项目对您有所帮助或启发，您的一个 ⭐ **Star** 是对我们最好的肯定！

---

## 📸 系统展示

> 以下 14 张截图全部拍摄于 **2026-10-02 的真实运行栈**（真后端 + 真实数据 + 真实 LLM 端点），
> 由 [`app/scripts/capture_screenshots.mjs`](app/scripts/capture_screenshots.mjs) 生成：
> 脚本在保存前逐块检查「必须有实质内容、且不含空态标记」，任何一块退化成「暂无 / 加载中」
> 就直接报错退出，**不写出半张空图**。截图可原样复现（见「常用命令」）。

### 报头与行情
<p align="center">
  <img src="docs/images/screenshots/dashboard.png" alt="报头与行情" width="800">
</p>

### 走势与关键数据
<p align="center">
  <img src="docs/images/screenshots/price-chart.png" alt="走势图与关键数据" width="800">
</p>

### 多空对照
<p align="center">
  <img src="docs/images/screenshots/news-analysis-up.png" alt="看涨因素" width="400">
  <img src="docs/images/screenshots/news-analysis-down.png" alt="看跌因素" width="400">
</p>

> 两侧独立取数、独立刷新，一侧取不到结果不影响另一侧。prompt 明确要求「宁可少给几个，
> 也不要为了凑满数量而凭常识编造」；一条都取不到时页面如实显示「暂不可用」，点「重新分析」
> 重试，不摆内置文案。模型返回后还有一层确定性结构校验（最多 5 条 / id 去重 /
> 允许的 id 枚举 / best-effort 数字引用），不合格的因子整条丢弃（`services/factor_validation.py`）。

### 机构观点
<p align="center">
  <img src="docs/images/screenshots/institutional-views.png" alt="机构观点" width="800">
</p>

> 截图当天唯一一条可核实的预测是**摩根士丹利：$4,000 是金价回落后的底部支撑，
> 长期看至 2027 下半年 $5,000**（预测日期 2026-10-01，来自 30 天新闻窗口里的真实报道）；
> 高盛、瑞银、花旗在窗口期内没有可核实的目标价，页面如实显示「暂无最新预测」——
> 四家机构一起变成「暂无」或一起被编上数字，都是这个项目明确不要的行为。
> 联网搜索默认关闭（`LLM_SEARCH_ENABLED=false`）：它用的是 MiMo 插件式的 `web_search`
> 工具，不是通用 OpenAI 能力，端点未开通时实测返回
> `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`
> （可用 `backend/scripts/smoke_llm.py` 复现）。

### 投资策略
<p align="center">
  <img src="docs/images/screenshots/investment-advice.png" alt="投资策略" width="620">
</p>

> 三档策略由一次 LLM 调用生成，输出预算由 `LLM_MAX_TOKENS` 控制（默认 8192，可按端点调大）。
> 预算太小会把这份大 JSON 截断、解析失败 —— 页面如实显示「暂不可用」，而不是摆一份
> 内置策略；解析失败时后端日志会记下 `finish_reason` 与 token 用量，便于下次定位。

### 量化预测
<p align="center">
  <img src="docs/images/screenshots/quant-prediction.png" alt="量化预测：1 年尺度的方向、概率与三情景" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/quant-fair-value.png" alt="公允价值分解" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/quant-monitor.png" alt="监测仪表盘（22 行水位表）" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/quant-accuracy.png" alt="回测命中率、基准对照与覆盖率（1 季）" width="800">
</p>

> 量化引擎不调用大模型：14 个因子全部来自免费公开数据源，取不到的因子与指标如实标「不可用」
> 并说明原因，可用因子少于 3 个时直接显示「预测不可用」。截图拍摄当天 12/14 个因子可用
> （地缘风险强度与 GLD 份额样本不足）；预测与回测挂在同一组尺度 tab 上，拍的是 1 年与 1 季，
> 口径见「量化策略」一节。监测表 22 行水位里有 6 行是**信息行**（第二轮接入的五条 + 2.0.2
> 接入的高权威消息强度）—— 它们都没过闸门，因此只给数值与观测日，不给多空标签；
> 预测落库同天同尺度只留一行（键为模型版本 + 尺度 + 截止日），
> 当天重算就地更新、跨天追加保留 —— 库里的历史就是预测存档。

### 研究页（预注册裁决 + 技能总览）
<p align="center">
  <img src="docs/images/screenshots/research-verdict.png" alt="研究页：版本与裁决（前向窗口尚不可判）" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/research-forward-window.png" alt="研究页：前向留出期还差多少个交易日" width="800">
</p>

<p align="center">
  <img src="docs/images/screenshots/research-overview.png" alt="研究页：五个尺度的技能总览" width="800">
</p>

> 研究页把「为什么现在还不能说模型有优势」摊开写：裁决只认前向留出期（2026-10-02 起）的
> 独立下注，1 日尺度目前只有 1/20 注、还差约 19 个交易日，5 日尺度还差约 99 个。历史留出期
> 那一列被明确标注为「已被前两轮裁决看过，只作记录」，不拿来顶替结论。页头还显著标注
> **数据窗口**（起止 + 交易日数 + 年数）：所有数字都由当前数据库这个窗口现算（缓存 1 小时），
> 与 README / 历史研究台报告引用的快照样本数对不上时，以研究页为准。

### 总结
<p align="center">
  <img src="docs/images/screenshots/market-summary.png" alt="市场总结" width="800">
</p>

---

## 📐 量化策略

本节讲清**「影响国际金价的四类因素」是怎么变成页面上那几个数字的**，以及这些数字**在哪里会错**。
因子清单、权重、方向先验与新鲜度上限只在 `backend/app/services/quant/definitions.py` 定义一处，
本节不另抄一份口径 —— 数字若与代码不符，以代码为准。

### 一、四层驱动与 14 个因子

框架是「影响国际金价的主要因素」的四层分类：

| 层 | 对应现实 | 因子数 | 这一层回答的问题 |
|---|---|---|---|
| 货币政策与利率 | 实际利率、政策路径、美元 | 4 | 持有黄金的机会成本在升还是在降？ |
| 避险与信用 | 波动率、信用压力、地缘冲突 | 3 | 市场在怕什么？钱在往哪里躲？ |
| 供需结构 | 央行购金、投机仓位、ETF 申赎 | 3 | 谁在真实地买，买多少？ |
| 市场与技术面 | 动量、季节性、替代品、风险偏好 | 4 | 价格自己的惯性怎么说？ |

14 个因子的完整定义（方向先验 `+1` = 该因子上升利多黄金，`-1` = 上升利空）：

| 因子 | 层 | 单位 | 来源 | 先验 | 权重 1日/1周/1月/1季/1年 | 新鲜度上限 |
|---|---|---|---|---|---|---|
| 美债 10 年期实际利率 | 货币政策与利率 | % | 美国财政部（TIPS 实际收益率曲线） | −1 | 0.25 / 0.5 / 1.0 / 1.0 / 0.8 | 7 天 |
| 市场隐含政策预期 | 货币政策与利率 | % | 美国财政部（2 年期）− 纽约联储（EFFR） | −1 | 0.2 / 0.4 / 1.0 / 0.8 / 0.6 | 7 天 |
| 10 年期通胀预期 | 货币政策与利率 | % | 美国财政部（名义 − 实际收益率） | +1 | 0.1 / 0.2 / 0.5 / 0.5 / 0.4 | 7 天 |
| 美元指数 | 货币政策与利率 | 点 | Yahoo Finance（DX-Y.NYB） | −1 | 0.3 / 0.5 / 0.9 / 0.7 / 0.5 | 7 天 |
| VIX 波动率指数 | 避险与信用 | 点 | Yahoo Finance（^VIX） | +1 | 0.6 / 0.5 / 0.4 / 0.3 / 0.2 | 7 天 |
| 信用市场风险偏好 | 避险与信用 | %（20 日） | Yahoo Finance（HYG/IEF 比值） | −1 | 0.5 / 0.4 / 0.3 / 0.2 / 0.2 | 7 天 |
| 地缘风险强度 | 避险与信用 | %（新闻占比） | 本系统 RSS 语料（关键词强度代理指标） | +1 | 0.5 / 0.5 / 0.4 / 0.3 / 0.3 | 3 天 |
| 央行购金（中国官方储备） | 供需结构 | 万盎司 | 新浪财经宏观数据（中国人民银行官方储备资产） | +1 | 0.2 / 0.4 / 0.7 / 1.0 / 1.0 | 62 天 |
| COMEX 投机净多头 | 供需结构 | 张 | CFTC 持仓报告（合约代码 088691） | +1 | 0.8 / 0.7 / 0.4 / 0.3 / 0.2 | 14 天 |
| 黄金 ETF 份额（GLD） | 供需结构 | 份 | Yahoo Finance（GLD 份额快照，自采集日起积累） | +1 | 0.3 / 0.4 / 0.5 / 0.7 / 0.8 | 7 天 |
| 黄金趋势动量 | 市场与技术面 | %（60 日） | Yahoo Finance（GC=F 收盘） | +1 | 1.0 / 1.0 / 0.4 / 0.3 / 0.2 | 7 天 |
| 季节性（当月历史平均） | 市场与技术面 | %（历史均值） | 自有价格序列（按公历月份，只用往年的数据） | +1 | 0.2 / 0.3 / 0.2 / 0.2 / 0.2 | 7 天 |
| 比特币（数字黄金叙事） | 市场与技术面 | 点 | Yahoo Finance（BTC-USD） | −1 | 0.2 / 0.2 / 0.2 / 0.2 / 0.3 | 7 天 |
| 股市风险偏好 | 市场与技术面 | 点 | Yahoo Finance（SPY） | −1 | 0.5 / 0.4 / 0.3 / 0.2 / 0.2 | 7 天 |

方向先验来自经济机理，**不保证成立** —— 回测逐因子报告单独命中率与 IC（研究页的「因子拆解」
一节），方向与实际相反时页面照样如实展示。除这 14 个因子外，库里的
`factor_observations` 表还存着 12 条**监控专用**序列（美元兑人民币、人民币金价换算、
TGA 余额、RRP、未平仓合约、GVZ、金银比、铜金比、CFTC 净多头占未平仓比、GPR 官方日度、
GLD 收盘（基准对照）、高权威消息强度（每日条数）），
它们不参与信号合成，见第八节。

### 二、五个尺度与各自的「主导层」

方法论的第一步是**先选时间尺度，再选变量** —— 同一份因子在不同周期上的权重并不相同：

| 尺度 | 标签 | 对应现实周期 | 主导层 | 说明 |
|---|---|---|---|---|
| 1 个交易日 | 1 日 | 日内～一周 | 市场与技术面 → 供需结构 | 资金流、技术面、仓位拥挤度主导，宏观基本面权重最低 |
| 5 个交易日 | 1 周 | 日内～一周 | 市场与技术面 → 避险与信用 | 一周资金流与事件脉冲主导，宏观仍居次席 |
| 20 个交易日 | 1 月 | 1～3 个月 | 货币政策与利率 → 供需结构 | 政策预期、经济数据、美元指数主导 |
| 60 个交易日 | 1 季 | 1～3 个月 | 货币政策与利率 → 供需结构 | 政策路径与需求结构并重 |
| 250 个交易日 | 1 年 | 6～18 个月 | 供需结构 → 货币政策与利率 | 实际利率周期、降息路径、央行购金趋势主导；**停发方向**（留出期与「永远看多」逐日一致），只发布公允价值偏离与年度校准区间 |

这也是为什么 14 个因子各带一组五维权重，而不是一个全局权重 —— 拿「央行购金」去解释明天
的金价，和拿「VIX」去解释明年的金价，都是把尺度搞反了。

### 三、一份校准分布，所有出口都由它派生（`quant-v7`）

因子合成的得分 `score` 是**未校准**的输入 —— 它只在因子表与「因子偏向（未校准）」的折叠详情里展示。
页面上所有结论都出自同一个 `engine.build_prediction_frame` 出口：

```
signed_z_i = sign_i × z(x_i)                    逐因子方向对齐（z 用 5 年滚动窗口）
score_h    = Σ w_i(h) · signed_z_i / Σ w_i(h)   按尺度取权重归一

μ_h        = α + β · score_h                    扩展窗口 OLS，样本对满足 s + h ≤ t
scale_h    = std(e_s | s + h ≤ t)               走查预测误差的标准差
F̂_h        最近一段已实现 e_s/scale_h 的加权经验分布；名义错失率 α 由 ACI 在线递推

区间       = μ + scale · [ F̂⁻¹(α/2),  F̂⁻¹(1−α/2) ]
情景区间   = μ + scale · [ F̂⁻¹(0.25), F̂⁻¹(0.75) ]
p_up       = 1 − F̂( −μ / scale )               与区间、情景同一个分布
目标价     = 基准价 × (1 + μ)                    基准价 = COMEX 主力期货日收盘（gold_close）
方向       = sign(μ)                            恰为 0 记「持平」
```

模型版本 **`quant-v7`**。六条硬口径：

1. **无前视**。滚动统计与回归样本全部 `shift` 到 t 之前；在黄金收盘之后才发布的
   数据源在因子表里带 `publication_lag_days`（财政部收益率曲线、纽约联储 EFFR 各
   1 个工作日），CFTC 持仓与央行储备在源层就按可用日打标 —— 引擎先按可见时点对齐，
   展示层的年龄用同一口径。守卫：`backend/tests/unit/quant/test_no_lookahead.py` 与
   `backend/tests/unit/quant/test_engine.py::test_publication_lag_delays_visibility`。
2. **不退回「预期不变」**。回归样本不足 60 组时该尺度整体「不可用 + 原因」，
   不拿得分符号顶替方向，也不假装 μ = 0。已实现误差不足 60 组时，scale 退回
   「已实现 h 日收益的扩展标准差」，仍然只用过去的数据。
3. **期望收益封顶**。`|μ| ≤ EXPECTED_CAP_SIGMAS × 同期已实现 h 日收益的扩展标准差`。
   一元 OLS 在得分几乎不动的窗口里分母接近 0，β 可以冲到 10⁴ 量级 —— 真实 20 年面板上
   实测过 60 日 +126167% 这种值；封顶让展示的目标价与区间不会飞出去。
4. **缺失因子按剩余权重归一**，不会被当成 0；可用因子少于 3 个直接「预测不可用」。
5. **陈旧即停用**。超过 `max_age_days` 的观测在 `align_series` 里就变成 NaN，
   既不进 z、也不进合成，也不计入回测的可用因子数 —— 不再拿三个月前的数当今天的水位。
6. **时间只走一个时区**（`app.utils.timeutil`，默认 `Asia/Shanghai`）。

概率**不是** `Φ(μ/σ_display)` —— 那等于把「为区间宽度放大过的尺度」当分母，会把每个概率都压向
50%。2.0.1 之前这正是 Brier 技能分全线为负的机制；现在概率与区间同源，只是同一张分布的不同取法。
`σ_display` 仍然存在，只用于展示「等效正态尺度」。

**区间口径是 ACI（自适应保形推断）非对称经验分位**：名义错失率 α 在每发出一次预测时在线递推。
2.0.1 修掉了一个会系统性压低覆盖率的错位 —— α 的更新原先拿「现在这一行」的区间去判
「h 天前发出的那一注」，尺度越长偏得越狠、方向正好是覆盖不足；修复后开发期 20 日覆盖率
76.7% → 79.3%、60 日 72.6% → 73.6%（本轮研究接口实测）。

### 四、公允价的四层分解

`decompose.py` 用走查式扩展窗口 OLS：

```
log 金价 ~ 实际利率 + log 美元指数 + log 央行储备 + VIX
```

把金价拆成 **宏观锚 ＋ 需求溢价 ＋ 风险溢价 ＋ 情绪残差**。展示口径只写在 `decompose.py`
一处：需求与风险溢价按链式相乘（风险溢价以「中枢＋需求溢价」为基数），使
「中枢＋需求溢价＋风险溢价 = 公允价」与「三块＋情绪残差 = 市场价」都按构造成立。
t 时刻的回归系数只用 `s ≤ t−1` 的已实现样本；样本不足 120 组或缺任一回归量时返回
「不可用 + 原因」。偏离度 = 市场价 / 公允价 − 1。

2.0.1 起分解**不再往回归支持域之外硬外推**：这一步的拟合值一旦超出 `6 个 σ` 或
`12 个 log 溢价`，该块单列 `unsupported_by` 并拒绝给数 —— 回归方程在历史样本没覆盖过的
输入上「算出」的溢价不是信息，是外推噪声。

> 有了它，「现在贵不贵」就不是一句感觉 —— 而是「市场价比模型算出的公允价高/低几个百分点，
> 其中多少来自需求、多少来自风险、多少是情绪」，以及「这个判断有没有超出模型见过的范围」。

### 五、情景的触发与失效条件

三个情景不是拍脑袋写的：Base 取分布中间的 50%（F̂ 的 q25～q75），Bull 与 Bear 各取上下 25%，
因此三者的概率之和恒为 100%。每个情景另外给出**触发条件**与**失效条件** ——
由该尺度**最重因子**与 **200 日均线**生成，是可以在页面上逐条核对的句子，而不是形容词。
scale 非正、基准价缺失或没有可用因子时返回「不可用 + 原因」，不阻塞预测主输出。

### 六、回测口径：四段样本期、独立下注、三个基准

回测（`backtest.py`）是**走查式**的：每个历史时点只用当时可得的数据。2.0.1 起先把样本期切成
四段，混用等于偷换证据：

| 样本期 | 起点 | 用途 |
|---|---|---|
| 开发期 `development` | 数据起点 | 唯一可以调参、挑候选的一段 |
| 历史留出期 `holdout` | 2023-10-02 | 已被前两轮裁决看过，**只作记录，不作为入选依据** |
| 前向留出期 `forward` | 2026-10-02（预注册封板日） | **唯一**的裁决窗口；没攒够 20 次独立下注就报 `pending` 并写明还差多少个交易日 |
| 全样本 `full` | 数据起点 | 展示用，不用于裁决 |

第二件是真话：**重叠样本不是独立证据**。250 日尺度的历史留出期有 754 个重叠观测，
按 `stride = h` 抽成互不相干的下注后其实只有 **3 次**。所有技能判断都同时给出
`independent_bets`（各尺度：754 / 151 / 37 / 12 / 3 次），样本不够就标「不可判定」。
命中率永远与三个基准并排展示：

| 基准 | 含义 |
|---|---|
| 永远看多 | 无视一切信号，每天都猜涨 |
| 动量 | 沿最近一段的趋势外推 |
| 抛硬币 | 50% |

2026-10-02 实测（`quant-v6` 口径，26 年面板；v7 发布滞后修正后待真实栈重算）：

| 尺度 | 开发期命中 | 历史留出期命中 | 永远看多（留出） | 差 | 开发期覆盖率 | 历史留出覆盖率 | 全样本覆盖率 |
|---|---|---|---|---|---|---|---|
| 1 日 | 52.5% | 54.6% | 56.4% | −1.7pp | 79.9% | 78.4% | 79.7% |
| 1 周 | 53.4% | 60.9% | 62.1% | −1.2pp | 80.0% | 77.9% | 79.7% |
| 1 月 | 54.6% | 68.1% | 68.1% | +0.0pp | 79.0% | 76.9% | 78.8% |
| 1 季 | 60.8% | 83.4% | 83.4% | +0.0pp | 74.5% | 65.3% | 73.5% |
| 1 年 | 71.8% | 100.0% | 100.0% | +0.0pp | 61.2% | 28.4% | 58.4% |

读法要小心：历史留出期是黄金单边上涨的三年，「永远看多」本身就是 56～100% 命中。
20 日及更长的尺度上模型逐日与它一致（差 +0.0pp）；**1 日与 1 周反而低于它**
（−1.7pp / −1.2pp）—— 短尺度上模型会喊跌，而这段行情里喊跌就是错的。
Brier 技能分为负（−0.006 / −0.029 / −0.096 / −0.388）；1 年尺度上基准率是 100%，
常数基准的损失为 0，技能分**无定义**，所以那里不印数字。分布级的 CRPS 另有一列：
同样对「零漂移」基准给技能分，研究页与 `scripts/quant_lab.py` 报告并排展示
（Brier 评涨/跌，CRPS 评整张分布的幅度匹配）。

2.0.2 起，研究页把两个**一级指标**放在命中率旁边，不再只报「命中多少」：

- **相对永远看多的增量 + 95% 置信区间**（`direction_edge_vs_up_ci95`）：点估计在单边
  行情里几乎总是负的，区间跨不跨 0 才决定这个增量能不能当结论；区间用按尺度分块的
  自助法（块长 = 预测天数），重叠样本不会把区间算窄。
- **敢喊跌质量**（`down_call_edge_vs_up`）：喊跌次数、喊跌命中率，以及**同一批喊跌日**
  上「永远看多」的命中率之差 —— 熊市里喊跌当然容易对，差额才说明模型敢在基准靠
  上涨赚钱的日子里下反向注。喊跌次数不足 30 次时不评命中率（给 `None`），
  不许把「从没喊过跌」算成「喊跌全对」。

前向裁决另外并排给出 **Beta 后验**与 **CRPS**：命中数的后验用写死的均匀先验 Beta(1,1)
加**独立下注**计数得到（均值、95% 可信区间、P(优于永远看多)），CRPS 技能分评整张分布。
入选规则一个字没动 —— 后验只是让「这点命中率有多少独立证据」一眼可见。
**这段成绩不能证明模型有方向优势，也不能证明没有 —— 它只说明历史留出期已经被看过了。**
所以 2.0.1 把裁决窗口前移，覆盖率缺口也如实分档展示（按预测当天已实现波动率分档、
每档再抽独立下注，不够 30 次只报次数）。

### 七、研究台与预注册：改进必须先在留出期上过线

`scripts/quant_lab.py` 把**候选清单与通过线在跑数之前写死**，再拿三个样本期去评。
候选不是拍脑袋：基线族 B0、漂移族 D1/D3/D5、合成族 S1–S4、分布族 P1–P4、校准族 C0/C1/C2、
因子集族 F1–F4、集成族 E0、多因子直接建模族 M1/M2，共 27 个（第四轮 +5：见本节末尾；定义只在
`scripts/quant_lab.py` 一处）。M 族（多因子 walk-forward Ridge）只进研究台、
与「先合成再一元回归」对照，不改动线上 `quant-v7`。

**第一轮（2.0 之前的 17 个候选）的结论是「没有结论」**：17 个候选 × 5 个尺度，
留出期上一个都没过线，且修好引擎之后它们在统计上彼此不可区分
（全档见 [`docs/specs/2026-10-02-研究台报告.md`](docs/specs/2026-10-02-研究台报告.md)）。
**这是本轮最重要的一条阴性结果**：它把预算从「继续调参数」指向了「新信息源与更长历史」——
数据回填扩到 20 年、评估口径换成独立下注 + HAC，并接入五条新序列（见第八节）。

同一条纪律也被写进了**因子闸门层**（`backend/app/services/quant/screen.py`，
配套 `scripts/screen_factors.py`）：任何新因子想进合成，必须先过三道闸门 ——

1. **显著性**：去均值后的协方差（不是裸相关）+ HAC（Newey–West）稳健 t，
   再叠 Bonferroni 校正与硬阈值 `|t| ≥ 3`（只靠 p 值会被擦边抽样骗过）；
2. **跨尺度同号**：短中长至少几个尺度的方向得一致，不能只有一格显著；
3. **前向窗口确认**：预注册封板日（`ACTIVE_HOLDOUT_START = 2026-10-02`）之后
   要攒够 `max(20, ⌈300/h⌉)` 次独立下注，没攒够就 `pending`，并写明还差多少个交易日。

在 26 年面板的 255 个格子上跑完的实测结果：**没有任何一个信号同时过闸门①②**；
「反向显著」只登记、不采纳（这是事先写死的方向纪律 —— 不能事后翻号），实测名单为空，
最接近的一条 `|t| = 2.98`；闸门③全部 `pending`（1 日 / 5 日各还差约 299 个交易日、
20 日 399、60 日 1199、250 日 4999）。换句话说：现在没有任何新序列配得上一个多空标签。

**第三轮（2.0.1）**预注册了一个候选 C2（校准样本改成「每注计一次」+ 回看窗），
判据同样先写死：目标尺度 60 日开发期覆盖率必须落在 [0.78, 0.82]，且**目标尺度的**
宽度不放大、按波动分档的覆盖率差 ≤ **5pp**。实测：

| 尺度 | 线上 B0 覆盖率 | C1（每注） | **C2（每注+窗）** | 宽度比（C2/B0） |
|---|---|---|---|---|
| 5 日 | 0.7997 | 0.8097 | 0.8161 | 1.054× |
| 20 日 | 0.7895 | 0.8055 | 0.7984 | 0.991× |
| 60 日 | 0.7437 | 0.7720 | **0.7679** | 0.881× |

**裁决：C2 淘汰。** 三条判据里第 2、3 条都过（60 日宽度是线上的 0.881 倍、分档差
+1.7pp），第 1 条没过：60 日覆盖率 0.7679 差预注册线 0.78 有 1.2pp —— 阈值不为它让路。
（宽度判据只针对**目标尺度 60 日**，所以 5 日那一档的 1.054× 不构成否决理由。）
控制候选 C0 与线上 B0 逐值相同（证明改动本身没有副作用）。裁决记录见
[`docs/specs/2026-10-02-量化引擎第三轮预注册.md`](docs/specs/2026-10-02-量化引擎第三轮预注册.md)。
复现：`python scripts/quant_lab.py --group calibration --horizons 20,60`。
注意：研究台现在按**前向留出期**裁决（`ACTIVE_HOLDOUT_START` 起），窗口没攒够
独立下注时报告写「不可判定」而不是「未过线」；上面这些开发期数字是历史记录。

**第四轮（2.0.2）**预注册了两组只进研究台的候选（登记文本在
[`docs/specs/2026-10-03-2.0.2-整改与自动化.md`](docs/specs/2026-10-03-2.0.2-整改与自动化.md)
「第四轮预注册」，口径实现在 `backend/app/services/quant/regimes.py`）：

- **Regime 三档**（状态切换）：R1 实际利率周期 / R2 美元周期（序列低于其 504 个交易日
  滚动中位数时持仓）、R3 央行购金时代（官方储备 252 个交易日变化为正时持仓）。
  状态不成立记中性 0 分（不反向）；滚动窗口最少 252 个观测，只用当日及以前的数据。
- **基准对照两档**：G1 = 生产基准 GC=F（控制）；G2 = GLD 收盘（ETF，无展期影响）。
  换基准只换评估目标，因子与信号一字不动 —— 回答「换一把尺子结论会不会变」。

基准口径本身也必须在页面与文档里说清楚：**生产基准是 GC=F 连续合约，含展期**
（换月价差直接进收益，未做展期调整；研究页有专门字段展示这句话）。两个「看起来更干净」
的替代本轮**未落地**：XAUUSD 现货（Yahoo 图接口 2026-10-03 实测 404）与展期调整连续序列
（需要逐月合约与展期价差，无免费合规来源）—— 原因记在 `regimes.BENCHMARK_CHOICES`，
不构造替代数字。复现：`python scripts/quant_lab.py --group regime --group benchmark`。
两组过前向窗口闸门之前，一律不进生产信号或基准。

> 这一节的诚实结论：2.0.1 没有把模型换成「看起来更强」的版本，因为证据不支持；
> 它做的是**让未来的每一次改进都必须先过线**，并且让「还没过线」这件事自己会说话。

### 八、监测仪表盘：22 行水位表

`monitor.py` 覆盖 **22 行**指标，每行给出频率、来源、当前值、信号（看涨 / 看跌 / 中性 / 信息）
与数据截至日。信号规则是确定性阈值，集中在 `_rule` 一处；取不到数据或历史不足的行如实返回
「不可用 + 原因」。每行的更新频率跟随它自己的数据源（日 / 周 / 月），不是统一刷新：

| # | 指标 | 频率 | 单位 | 来源 | 信号规则 / 备注 |
|---|---|---|---|---|---|
| 1 | 美债 10 年期实际利率（TIPS） | 日 | % | 美国财政部 TIPS 曲线 | 5 个观测变化 ≤ −0.10pp 看涨、≥ +0.10pp 看跌 |
| 2 | 盈亏平衡通胀（10Y 名义 − 实际） | 日 | % | 美国财政部收益率曲线 | 5 个观测变化 ≥ +0.10pp 看涨（通胀对冲）、≤ −0.10pp 看跌 |
| 3 | 美元指数（DXY） | 日 | 点 | Yahoo Finance（DX-Y.NYB） | 5 个观测涨跌 ≥ +1% 看跌、≤ −1% 看涨 |
| 4 | 市场隐含政策预期（2Y − EFFR） | 日 | % | 美国财政部 − 纽约联储 | 5 个观测变化 ≥ +0.10pp 看跌、≤ −0.10pp 看涨 |
| 5 | 央行黄金储备 | 月 | 万盎司 | 新浪财经（官方储备数据） | 环比增加看涨、减少看跌 |
| 6 | 黄金 ETF 份额（GLD） | 日 | 份 | Yahoo Finance | 最近两次观测增加看涨（申购）、减少看跌 |
| 7 | CFTC 净多头（拥挤度） | 周 | 张 | CFTC 持仓报告 | 净头寸 z ≥ +1.5 看跌、≤ −1.5 看涨 |
| 8 | 上海金溢价 | 日 | 元/克 | 上海黄金交易所 Au99.99（实测可达） | 信息行：SGE 收盘 − 国际金价折算（黄金 × USDCNY ÷ 31.1035）；溢价未过预注册检验，不给方向 |
| 9 | VIX 恐慌指数 | 日 | 点 | Yahoo Finance（^VIX） | ≥ 25 看涨、≤ 15 看跌 |
| 10 | 信用偏好（HYG/IEF 20 日变化） | 日 | % | Yahoo Finance | ≥ +2 看跌、≤ −2 看涨 |
| 11 | 金价 vs 200 日均线 | 日 | 美元 | 自有价格序列 | 偏离 ≥ +0.5% 看涨、≤ −0.5% 看跌 |
| 12 | 美元兑人民币（USDCNY） | 日 | 元 | Yahoo Finance（CNY=X） | 信息行：只作换算参考，不参与多空 |
| 13 | 人民币金价参考 | 日 | 元/克 | 黄金收盘 × USDCNY ÷ 31.1035 | 信息行：国内投资者视角的价格锚 |
| 14 | 美国财政部 TGA 余额 | 日 | 百万美元 | 美国财政部 Fiscal Data | 20 个观测增加 ≥ 500 亿看跌、减少 ≥ 500 亿看涨 |
| 15 | 纽约联储逆回购（RRP） | 日 | 亿美元 | 纽约联储公开市场操作结果 | 20 个观测增加 ≥ 50 亿看跌、减少 ≥ 50 亿看涨 |
| 16 | COMEX 黄金未平仓合约 | 周 | 张 | CFTC 持仓报告 | 信息行：衡量参与度，不直接给方向 |
| 17 | 黄金隐含波动率（^GVZ） | 日 | 点 | Yahoo Finance（^GVZ） | 信息行：18 年面板五个尺度 \|t\| 全 < 0.6 |
| 18 | 金银比（金价 ÷ 银价） | 日 | 倍 | Yahoo Finance（GC=F ÷ SI=F） | 信息行：26 年最好一格 60 日 t=+2.30（iid +10.76），未过闸门 |
| 19 | 铜金比（铜价 ÷ 金价） | 日 | 倍 | Yahoo Finance（HG=F ÷ GC=F） | 信息行：26 年实测 250 日 t=+1.27，未过闸门 |
| 20 | CFTC 净多头占未平仓比 | 周 | % | CFTC 持仓报告 | 信息行：拥挤度的占比口径，250 日 t=+0.73，未过闸门 |
| 21 | 地缘风险指数（GPR 官方日度） | 日 | 点 | Iacoviello & Papaioannou GPR | 信息行：20 日 t=−2.64（反向），离 \|t\| ≥ 3 还差，不给方向 |
| 22 | 高权威消息强度（每日条数） | 日 | 条 | 消息板块（13 个高权威源，本库统计） | 信息行：第四轮预注册候选，不进本轮信号合成 |

> 第 17–21 行是第二轮新接入的五条信息源、第 22 行是 2.0.2 接入的高权威消息强度 ——
> 六条都还没过严格闸门（第七节），因此**一律不给多空**，只当水位展示。
> 等前向窗口攒够观测、真过了闸门，再谈加规则。第 12–16 行同样是监控专用序列，
> 与因子同表（`factor_observations`）存储但不参与信号合成，顺序与数量由
> `monitor.ROW_SPECS` 唯一确定（`backend/tests/unit/quant/test_monitor.py` 逐行守住）。

### 九、数据源与新鲜度

- **全部免费、无需密钥**：美国财政部收益率曲线与 Fiscal Data（TGA）、纽约联储 RRP 与 EFFR、
  CFTC 持仓报告、Yahoo Finance（DXY / GC=F / SI=F / HG=F / GLD / SPY / BTC-USD / ^VIX /
  ^GVZ / HYG / IEF / CNY=X）、Iacoviello & Papaioannou 的 GPR 官方日度序列、
  新浪财经（央行官方储备）、上海黄金交易所 Au99.99 日行情、本系统自己的 RSS 语料。
- **按源节流**：同步器给每个源单独设 6h～24h 的节流窗口，增量抓取；某个源失败不影响其它源，
  失败原因写进同步报告。页面把逐个源的状态（正常 / 未到期 / 不可用）收在折叠的「数据源状态」区，
  默认不占版面。
- **按因子设新鲜度上限**（第一节表最后一列）：日频 7 天覆盖长假，月度 62 天覆盖发布推迟。
  超过上限的因子在**合成阶段**就变 NaN（不是先填一个旧值再标注），如实标「陈旧」并排除出合成。
- **观测有修订流水，历史面板可重建**。`factor_observations` 只追加、不覆盖：同一
  `(factor_key, obs_date)` 重复抓取是幂等的，值一旦修订会追加一条新观测。因此任何一次
  历史裁决都能用 `--as-of 2026-09-01` 按「那天看到的修订状态」重算 —— 预注册要能被复核，
  否则只是句口号。老库升级时 `migrate_quant.py` 会自动把既有观测回填进流水；
  不补流水的话 `--as-of` 会静默返回空面板 —— 所以迁移脚本宁可把回填行数打印出来。
- **拒收未来观测**：任何 `obs_date` 晚于「今天」的记录在入库前被拒绝（时区口径见红线五），
  保证回测不会读到「当天还没发生的数据」。
- **首次回填默认 10 年**（`QUANT_HISTORY_YEARS`，可调大），之后只抓增量；
  想把面板一次拉长到 20 年用 `backend/scripts/backfill_quant.py --apply --years 20`，
  `--dry-run` 只打印每个序列还缺多少，不写库。
- **同一个「金价」有三个口径，接口逐处标注**（2.0.2 起每个价格都带 `basis`）：
  `realtime` 实时报价（腾讯 / 新浪 / 东方财富；只有被实时价替换或追加的那一点）、
  `close` 日收盘（`gold_prices` 表与 `gold_close` 序列；统计窗口、回测与量化基准都用它）、
  `quant_basis` 量化基准（量化引擎的目标价、区间与情景都派生自 `gold_close` 的最后一点）。
  每个价格同时给 `basis_label`（中文）、`source`（来源）与 `as_of`（截至时间）；
  实时源全挂、退回库里的收盘时口径自动降级为 `close` —— **不把兜底价说成实时**。
  同一天里实时报价与最新收盘偏差超过 3% 时，`check_data_sanity.py` 会点名
  「报价背离」，要求先核对两路口径再展示（`--offline` 可跳过对账、只查库内数据）。

### 十、已知限制（我们不加修饰地写在这里）

1. **1 年尺度的覆盖率仍明显低于名义值**。开发期 55.9%、全样本 52.8%、历史留出期 28.8%
   （名义 80%）；宽度校准补不回中心（μ）的偏差，缺口随尺度单调变大
   （1/5/20/60/250 日的开发期覆盖率为 80.2 / 80.1 / 79.3 / 73.6 / 55.9%）。
   这是下一轮的头号攻关点（本轮 20 个候选、含第三轮 C2 都没改变这个结论）。
2. **前向窗口尚不可判**。裁决只认 2026-10-02 起的独立下注：1 日尺度 1/20 注、还差约
   19 个交易日；5 日 0/20、还差约 99；20 日还差约 399；60 日约 1199；250 日约 4999。
   在那之前，页面与研究页不给「有优势 / 无优势」的结论。
3. **历史留出期方向无信息优势**。2023-10-02 起的历史留出期里，五个尺度的方向与
   「永远看多」逐日一致（+0.0pp），Brier 技能分为负 —— 这段成绩不能当入选依据。
4. **上海金溢价已接通，但它只是水位不是信号**。上海黄金交易所 Au99.99 的 `Dailyhq`
   公开端点经实测（2026-10-03）可达：返回 2016-12-19 起的日行情；行内数值 = SGE 收盘 −
   国际金价折算（黄金 × USDCNY ÷ 31.1035）。溢价本身未过预注册检验，所以只展示、不给方向、
   不参与信号合成；SGE 源临时不可达时该行如实退回「不可用 + 原因」。
5. **联网搜索默认关闭**。它用的是 MiMo 插件式的 `web_search` 工具，不是通用 OpenAI 能力；
   端点侧未开通时返回 `HTTP 400 · web search tool found in the request body, but
   webSearchEnabled is false`（实测可复现）。开启方式：`LLM_SEARCH_ENABLED=true`
   且端点侧已开通插件；未开启时机构观点回退到 RSS 新闻窗口，不发起无效请求。
6. **地缘风险强度是语料代理指标**（最近新闻中相关报道占比），不是官方指数 ——
   官方 GPR 日度序列已进监测表（信息行），但在过闸门之前不参与合成，两者不混用。
7. **无鉴权、无多租户**。所有接口公开可访问，包括会触发付费 LLM 调用的 `POST .../refresh`。
8. **不是交易系统**。不下单、不接券商、不托管资金；所有产出都带免责声明。

---

## 🚀 快速开始

### 前置要求

| 依赖 | 版本 | 用途 | 检查 |
|---|---|---|---|
| Node.js | ≥22.22.2（或 24.15+/26+） | 前端运行环境，包含 npm。下限来自 lockfile 里最严的依赖（jsdom `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0`）；Node 22.2.0 能跑起来，但 Vite 会打印版本告警 | `node -v` |
| Python | 3.11 - 3.12 | 后端运行环境 | `python --version` |
| SQLite | Python 内置 | 数据存储：单文件 `backend/goldmind.db`，**零安装、零配置** | 无需检查 |
| Google Chrome（或 Edge） | 任意近期版本 | 前端端到端测试复用本机已装的 Chrome；没有 Chrome 可用 Windows 自带的 Edge（`E2E_BROWSER=msedge`），两者都**不下载** Playwright 自带浏览器 | 打开 Chrome → `chrome://version` |

### 本地开发（文档化路径：SQLite 零配置）

#### 1. 获取代码

```bash
git clone https://github.com/JasonBuildAI/GoldMind.git
cd GoldMind
```

#### 2. 安装依赖

**后端依赖：**

```bash
cd backend

# 创建虚拟环境（推荐；下文命令里的 .venv 即此处创建）
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

> **版本是钉死的**（`==`，不是 `>=`），钉的是测试实际跑过的版本。
> 松散范围意味着 `pip install` 随时可能拉到带破坏性变更的新大版本，
> 而问题要到部署时才暴露。前端同理 —— `package-lock.json` 已入库，
> 用 `npm ci` 而不是 `npm install`。

**前端依赖：**

```bash
cd app

# 安装依赖（用 ci 而不是 install：严格按 lockfile，可重现）
npm ci
```

#### 3. 配置（只有 LLM 三项是必填）

```bash
cd backend
copy .env.example .env      # macOS/Linux: cp .env.example .env
```

打开 `backend/.env`，填三项即可（数据库**不用动** —— 默认就是 SQLite 单文件）：

```ini
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://api.deepseek.com/v1   # 任选一家 OpenAI 兼容端点
LLM_MODEL=deepseek-chat
```

常见供应商（任选其一；端点须兼容 OpenAI 协议）：

| 供应商 | `LLM_BASE_URL` | `LLM_MODEL` |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Ollama（本地） | `http://localhost:11434/v1` | `qwen2.5:14b` |
| 小米 MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v2.6-flash` |

> ⚠️ 密钥只放 `.env`（已被 `.gitignore` 忽略），永不入库、进日志或提交。
> 想确认自己的环境是否干净，跑 `python scripts/verify_setup.py`（只读、不连库、不出网）。
> 其它可选配置（定时任务、限流、量化回填年数、联网搜索开关）都在
> `backend/.env.example` 里逐项注释，**默认值即可直接使用**。
>
> 公开部署建议设 `REFRESH_TOKEN=<一段随机串>`：七个 `POST .../refresh` 接口此后
> 必须携带 `X-Refresh-Token` 请求头才执行（缺失/不匹配返回 401，且在任何副作用之前
> 拒绝）；不设则保持旧行为。开启后调用方（如 `curl`、部署脚本）要自行带上该头，
> 详见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 第九节。

#### 4. 启动（不需要任何初始化命令）

```bash
cd backend

# 建表、自动迁移、历史回填与首轮分析全部由启动引导完成（幂等，可随时重启）
python -m uvicorn app.main:app --port 8000
```

打开 `http://localhost:8000/health`：`bootstrap.status` 会从 `running` 走到 `done`，
`bootstrap.step` 显示当前进度（第 N 步 / 共 M 步）。数据缺口（空库、历史不足、
新闻过期）会被自动回填；库已经最新时各阶段如实标「skipped」并说明原因。
手工脚本（`init_db.py` / `migrate_*.py` / `backfill_quant.py` / 体检 / 备份）
仍然保留，但都降级为**可选运维工具** —— 见「全自动运行」一节。

#### 5. 启动服务

前后端各占一个终端 —— 仓库里**没有** `start_all.ps1` 这类一键脚本：

```bash
# 终端 1：后端（在 backend 目录）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：前端（在 app 目录）
npm run dev
```

> 想省掉第二个终端也可以只开前端：后端没起来时页面会如实报「接口不可用」，
> 不会展示任何内置数字。

**冷启动预期（第一次打开页面时）：**

- 页面顶部显示「初始化中（第 N 步 / 共 M 步）」；数据阶段完成后会自动开始首轮
  AI 分析（首次通常几分钟，期间各区块显示「进行中」而不是错误）。
- 全部完成后内容自动出现，**不需要**点任何「重新分析 / 重新抓取」；量化预测所需的
  多年因子历史也由同一次启动引导回填。
- 页面每 30 秒轮询行情接口（标签页隐藏时暂停、切回立即补一次）；默认限流 60 次/分
  （LLM 接口 6 次/分）。429 / 5xx / 网络错误会自动退避重试（429 尊重 `Retry-After`），
  正常浏览不会把页面打成「整片失败」。

**服务地址：**
- 前端: http://localhost:5173
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

#### 6. 零密钥自检跑通（不需要任何 LLM key）

不想申请 LLM key，也想先把系统跑起来：仓库自带一个假的 OpenAI 兼容服务，
配 SQLite 就能把「新闻 → 分析 → 缓存 → 页面」整条链路走通，不消耗额度、不联网。

```powershell
# 终端 1：假 LLM（OpenAI 协议兼容，端口自选）
cd backend
.venv\Scripts\python.exe scripts\dev_mock_llm.py --port 8099

# 终端 2：SQLite 建表 + 确定性种子数据（离线、可重复），然后把后端指向假 LLM
cd backend
$env:DATABASE_URL = "sqlite:///./goldmind.db"
.venv\Scripts\python.exe scripts\dev_seed_sqlite.py --db goldmind.db
$env:LLM_API_KEY  = "zero-key"                          # 占位符即可，不是真 key
$env:LLM_BASE_URL = "http://127.0.0.1:8099/v1"
$env:LLM_MODEL    = "dev-mock"
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

# 终端 3：前端
cd app
npm run dev
```

打开 http://localhost:5173 ：五个分析区块会拿到假 LLM 的样例内容。量化区块走
真实计算，需要真实公开行情（不需要 key）—— 没有数据时按页面提示点「重新抓取」，
或按第 4 步用 `python init_db.py` 灌入真实历史。

> 这套流程也是 `npm run test:e2e` 在自动化跑的东西；真实 LLM 只要把 `backend/.env`
> 的三项配置填上即可。环境变量优先于 `.env`，所以自检不会碰你的真实配置。

### 可选：MySQL / Docker（未随本仓库实测）

本 README 的快速开始、闸门命令与 CI **只走 SQLite** —— 这是唯一被仓库实测覆盖的复现路径。
仓库里仍保留两处可选的 MySQL / 容器化资产，供确实需要的人参考，但**不保证在当前版本下
开箱可用**：

- `docker-compose.yml` + `backend/schema.sql`：三容器（mysql / backend / frontend）编排。
  MySQL 首次启动会用 `schema.sql` 建表；容器内后端的 `DATABASE_URL` 由 compose 注入。
- 改用本机 MySQL：在 `backend/.env` 里写
  `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/gold_analysis`，
  然后 `python init_db.py`（MySQL 路径会先建库、再执行 `schema.sql`）。
- 备份：`python scripts/backup_db.py` 对 MySQL **不代跑** —— 只打印 `mysqldump`
  命令模板并退出码 2（`-p` 回车后再输密码，密码不进命令历史、不进脚本）。
  SQLite 路径会直接备份并逐表校验行数。

> ⚠️ 这两条路径与本轮的 SQLite 默认路径**没有跑过同一套闸门**，行为差异（ENUM 存储、
> 字符串比较大小写、事务语义）已知存在。用之前请先跑一遍
> `GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" python -m pytest`，
> 确认基线再上线。

---

## 🤖 全自动运行（2.0.2）

**唯一的人工输入是 `backend/.env`**（LLM 三项必填，其余可选项都有默认值）。填好启动后，
建表、迁移、回填、抓取、分析、备份与体检全部由系统自己完成 —— 不需要再跑任何命令。

| 时机 | 自动完成 | 进度在哪看 |
|---|---|---|
| 每次启动 | 建表 → 应用迁移注册表（`schema_migrations` 记账、只应用一次；SQLite 改表前自动备份到 `backend/backups/`） | `/health` → `bootstrap.migrations` |
| 启动时发现数据缺口 | 对齐本地研究长库 → 回填金价 / 美元指数历史 → 抓 RSS 新闻与高权威消息 → 回填量化因子（默认 20 年，可断点续跑） → 补齐因子修订流水 | `/health` → `bootstrap`（阶段 / 进度 / 缺口） |
| 启动时 LLM 已配置 | 首轮五个 AI 分析（看涨 / 看跌 / 机构 / 策略 / 总结），受输入指纹与 `LLM_DAILY_CALL_BUDGET` 约束 | 各页面区块、`/health` → `services.ai_config` |
| 运行中每 10 秒 | 监听 `.env`：`LLM_*` 一出现 / 变化就热生效（重置客户端与缓存指纹）并立刻补一轮分析，**无需重启** | `/health` → `config_watch` |
| 运行中按调度 | 错过窗口自动补跑（coalesce + misfire）；启动约 20 秒先跑一轮「补差」（行情 / 新闻 / 消息） | `/health` → `services.scheduler` |
| 每日 04:00 | SQLite 自动备份（保留最近 7 份）→ 数据体检；自动修复仅限「未来日期清理」，且只在前一步**真正备份成功后**执行 | 服务端日志 `[维护]`；MySQL 不支持自动备份，如实标注 |

- **降级语义**：LLM 未配置时数据层照常运行，各分析块显示「暂不可用 + 原因」；
  之后把 LLM 三项填进 `.env`，监听器会自动重载并补一轮分析。
- **需要重启的项**：`DATABASE_URL` 等非 `LLM_*` 的变化不会被中途热应用，
  `/health` 的 `config_watch.note` 会明确提示「需重启生效」。
- **MySQL**：自动迁移同样生效；自动备份不代跑 `mysqldump`（如实标注为不支持）。
- **Docker**：`backend/docker-entrypoint.sh` 只做「等库就绪 → 直接起 uvicorn」，
  初始化同样交给启动引导。

**可选运维工具**（保留但不再是运行必经步骤，不使用不会缺任何功能）：

| 工具 | 用途 |
|---|---|
| `python init_db.py` | 只建表（离线用 `SKIP_SEED=1`） |
| `python scripts/backfill_quant.py --apply --years 20` | 手工把因子面板一次拉长到 20 年 |
| `python scripts/migrate_*.py` | 手工迁移（启动引导自动应用同一份实现） |
| `python scripts/check_data_sanity.py [--fix] [--strict]` | 数据体检（每日自动跑一遍） |
| `python scripts/backup_db.py` | 手工备份（每日自动备份 SQLite，保留 7 份） |
| `python scripts/verify_setup.py` | 只读配置自检（不连库、不出网） |

> 修订流水是 `--as-of` 复现历史面板的前提。回填出来的流水，`recorded_at` 是那一行
> **进入本系统**的时间；历史回填是一次性写进来的，所以问更早的日期得到空面板是
> **正确**的答案，不是 bug。

## 🧪 常用命令

**闸门命令的唯一真源。** 改完代码必须全部跑绿（规矩见 [`AGENTS.md`](AGENTS.md)）。

### 后端

```bash
cd backend

# 安装依赖（首次）
pip install -r requirements.txt -r requirements-dev.txt

# 配置级自检（只读：不连库、不出网；失败项会给出修复命令，退出码 0/1）
python scripts/verify_setup.py

# 备份数据库：SQLite 用 backup API 全量复制并逐表校验行数（默认 backend/backups/，已进 .gitignore）
# MySQL 路径不代跑：打印 mysqldump 命令模板并以退出码 2 提示人工执行（失败不会装成成功）
python scripts/backup_db.py
python scripts/backup_db.py --out D:/goldmind-backups

# 数据体检：未来日期 / 非法数值 / 跨库一致性（只报告，退出码 0/1）
python scripts/check_data_sanity.py
python scripts/check_data_sanity.py --strict   # 跨库偏差也算失败
python scripts/check_data_sanity.py --fix      # 删除未来日期行（不可逆：先备份！）

# 测试 —— 全档闸门
python -m pytest

# 只跑某一层
python -m pytest tests/unit          # 单元：不依赖数据库与网络
python -m pytest tests/integration   # 集成：内存 SQLite + 假 LLM
python -m pytest tests/e2e           # 端到端：按真实使用顺序串起整条链路

# 可选：换 MySQL 方言再跑一遍（**仅在你确实要验 MySQL 时**；SQLite 是默认与 CI 的口径）
# 两者在枚举存储、JSON 列、字符串比较大小写上都有差异。必须指向**独立的测试库**：用例会清空所有表。
GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" \
    python -m pytest

# 测试库护栏：上面这个 URL 的**库名必须含 "test"**，否则测试直接拒跑。
# 用例会 drop_all / 清空它连上的所有表；2026-10-02 的事故就是它被指向了开发库
# gold_analysis，会话结束删光 9 张业务表。留空则用内存 SQLite（默认、安全）。

# 静态检查：全量语法
python -m compileall -q app

# 接口文档（中英两份）是否与路由表一致
python scripts/gen_api_doc.py --check     # 不一致时退出码 1
python scripts/gen_api_doc.py             # 重新生成 docs/API.md 与 docs/en/api.md

# 数据库初始化（SQLite：建表 + 灌历史数据；库文件自动创建）
python init_db.py
SKIP_SEED=1 python init_db.py        # 只建表，不灌数据（离线可用）

# 修正旧库里的枚举列取值（幂等；只影响 schema.sql 早期版本建出来的库）
python scripts/fix_enum_columns.py --dry-run
python scripts/fix_enum_columns.py

# 手动跑一轮因子抓取（首次回填 QUANT_HISTORY_YEARS 年、默认 10；之后是增量）
python -c "from app.database import SessionLocal; from app.services.quant.sync import run_sync; db=SessionLocal(); print(run_sync(db, force=True).to_dict()); db.close()"

# 把历史面板拉长：默认 20 年；--dry-run 只打印每个序列缺多少，不写库（需要联网）
python scripts/backfill_quant.py --dry-run
python scripts/backfill_quant.py --apply --years 20

# 量化研究台：预注册候选 × 尺度 × 三个样本期的全档评估（默认读库，不重算）
python scripts/quant_lab.py
python scripts/quant_lab.py --out docs/specs       # 输出目录（quant_lab.md / quant_lab.csv）
python scripts/quant_lab.py --horizons 20,60       # 只跑部分尺度
python scripts/quant_lab.py --group calibration    # 只跑某一组候选（可重复）
python scripts/quant_lab.py --as-of 2026-09-01     # 按修订流水重建那一天看到的面板
python scripts/quant_lab.py --holdout-start 2023-10-02   # 复现某次历史裁决

# 因子闸门：三道闸门筛候选（--include-holdout 默认关闭，避免污染事前承诺）
python scripts/screen_factors.py
python scripts/screen_factors.py --horizons 20,60 --as-of 2026-09-01
```

### 前端

```bash
cd app

# 安装依赖
npm ci

# 构建 + 类型检查 —— 全档闸门
npm run build

# 静态检查
npm run lint

# 单元 + 集成测试（vitest + Testing Library）
npm test

# 浏览器端到端测试（Playwright）—— 需要先 npm run build
npm run test:e2e

# 本地开发
npm run dev

# 重拍 README 里的 14 张截图（需要真实栈在跑：后端 8000 + 前端 5173）
node scripts/capture_screenshots.mjs
# 可选：SCREENSHOT_BASE_URL / SCREENSHOT_OUT / SCREENSHOT_BROWSER=chrome|msedge|chromium
```

### 浏览器端到端测试

`npm run test:e2e` 会真的把三个服务拉起来，再由真实浏览器访问：

1. 假 LLM 服务（`backend/scripts/dev_mock_llm.py`，OpenAI 协议兼容，不消耗额度）
2. 真后端（uvicorn + SQLite，数据由 `backend/scripts/dev_seed_sqlite.py` 准备）
3. 构建产物（`vite preview`，经代理把 `/api` 转发给后端）

它复用本机已安装的 Chrome，**不下载** Playwright 自带浏览器；Windows 上没有 Chrome
时可用系统自带的 Edge（`E2E_BROWSER=msedge`）。若你的 Python 不在 `PATH` 上，
用 `E2E_PYTHON` 指定解释器：

```powershell
$env:E2E_PYTHON = "path\to\python.exe"
cd app
npm run build
npm run test:e2e              # 默认：复用本机 Chrome

$env:E2E_BROWSER = "msedge"   # 没有 Chrome：改用本机 Edge
npm run test:e2e
```

> 端到端测试用独立的数据库与缓存目录（`backend/e2e.db`、`backend/e2e-cache/`），
> 不会碰你的开发数据；两者都已被 `.gitignore` 忽略。

### 端到端冒烟（真实调用 LLM）

```bash
cd backend
python scripts/smoke_llm.py
```

> ⚠️ 需要 `backend/.env` 已配置 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`，
> 且会真实消耗额度。脚本先探测鉴权、`max_tokens` 与中文 JSON 输出；联网搜索
> 只在 `LLM_SEARCH_ENABLED=true` 时才探测（默认跳过）。结果写入
> `backend/scripts/smoke_llm_result.json`（已被 `.gitignore` 忽略）。

### 持续集成（GitHub Actions）

默认分支只接受全绿的合并：`.github/workflows/ci.yml` 在 PR 与 push 到 `main` 时
跑三组并行任务，命令就是上面这几条闸门命令 ——

| 任务 | 跑什么 | 环境 |
|---|---|---|
| `Backend (pytest)` | `python -m pytest` | Python 3.11 + 内存 SQLite（不需要 MySQL） |
| `Frontend (lint + test + build)` | `npm run lint` / `npm test` / `npm run build` | Node 22 |
| `Browser E2E (Playwright)` | `npm run test:e2e` | Python 3.11 + Node 22 + Chromium + 假 LLM |

浏览器端到端在 CI 里把 `E2E_BROWSER=chromium` 传进 `app/playwright.config.ts`，
用 `npx playwright install --with-deps chromium` 装浏览器；本机跑时该变量留空，
仍复用已安装的 Chrome，也可以设为 `msedge` 改用 Windows 自带的 Edge。

依赖更新交给 `.github/dependabot.yml`：pip / npm / github-actions 三个生态每周
各开少量 PR，**不自动合并** —— 每个 PR 仍要过上面三组检查，由人决定合并时机。

> 分支保护（required checks、必须走 PR）是 GitHub 仓库设置，不在版本控制里，
> 需要在仓库的 Settings → Branches 里手动开启。工作流第一次成功跑过后，
> 把三项检查勾成必需即可。

### 排障

- **httpx 报 `Invalid port: ':1]'` 或 `Missing dependencies for SOCKS support`**
  —— 本机设置了系统代理（`ALL_PROXY` / `HTTP_PROXY` 等），或 `NO_PROXY` 里含
  `[::1]`，httpx 无法解析这些值。跑测试前先清掉：

  ```powershell
  $env:ALL_PROXY=''; $env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:NO_PROXY=''
  ```

- **测试报 `no such table`** —— 测试用的是内存 SQLite，正常不该出现；
  若出现，检查是否绕过了 `backend/tests/conftest.py` 的夹具。

- **Windows 控制台报 `UnicodeEncodeError: 'gbk' codec can't encode ...`**
  —— GBK 控制台打印非 GBK 字符（如 `−`、`≈`）会炸。仓库入口脚本已按 GBK 契约
  处理过；自己写一次性脚本时用 `python -X utf8 script.py`，或把结果写进 UTF-8 文件。

- **`--as-of` 返回空面板** —— 先确认修订流水已回填：
  `python scripts/migrate_quant.py --dry-run` 会打印还缺多少行。历史回填的流水
  落在回填那天，问更早的日期得到空面板是正确的。

- **整片区块「分析 / 抓取失败」，刷新一下又好了** —— 现在页面上的错误文案会区分原因：
  - *请求过于频繁*：看板每 30 秒才轮询一次（隐藏暂停），429 会自动退避重试。持续出现
    说明同时开着多个页面、或别的客户端在共用同一后端的限流额度；可调大
    `RATE_LIMIT_PER_MINUTE`。
  - *数据表缺失 … 运行 `python init_db.py`*：接口返回 503（不再是裸 500）并附修复命令，
    启动日志里也有一条 `[启动自检]`。重建后按需回填历史。
  - 量化区块的「缺少黄金价格序列」还有一类原因：Yahoo Finance 对本机限流
    （`YFRateLimitError: Too Many Requests`）。此时引擎自动改用本地 `gold_prices` /
    `dollar_index` 表兜底基准价与美元因子（来源标注为「本地行情表…兜底」），不再整片停摆。

- **测试拒绝启动并提示「库名里不含 test」** —— 这是护栏，不是故障：测试套件会
  `drop_all` 它连上的所有表。把 `GOLDMIND_TEST_DATABASE_URL` 指向名字含 `test` 的
  独立库，或留空使用内存 SQLite。

---

## 🗂️ 目录结构

```
GoldMind/
├── app/                          # 前端（React 19 + TypeScript + Tailwind）
│   ├── src/
│   │   ├── sections/            # 七个页面区块 + 各自的测试
│   │   ├── research/            # 「研究」页：预注册评估、裁决窗口、可靠性分桶
│   │   ├── components/          # 可复用组件（含机构观点的预测日期列）
│   │   ├── layout/              # 报头 / 页脚
│   │   ├── services/            # API 客户端与类型定义（api.ts）
│   │   └── test/                # 测试夹具
│   ├── scripts/
│   │   └── capture_screenshots.mjs  # README 截图：逐块检查真实内容，不写空图
│   └── package.json
├── backend/                      # 后端（FastAPI + SQLAlchemy；默认 SQLite 单文件）
│   ├── app/
│   │   ├── services/            # 业务逻辑
│   │   │   ├── llm_provider.py                     # **LLM 调用的唯一入口**
│   │   │   ├── institution_prediction_service.py   # 机构观点（含机构注册表）
│   │   │   ├── news_digest.py                      # 消息板块：抓取 / 确定性评分 / 三窗口 Top10（不调用 LLM）
│   │   │   ├── analysis_input.py                   # 分析输入包：新闻去重合并 + 价格上下文 + 能力声明
│   │   │   └── quant/                              # 量化引擎：sources / derive / storage /
│   │   │                                           #   sync / engine / decompose / scenarios /
│   │   │                                           #   backtest / monitor / screen /
│   │   │                                           #   preregistered / stats / service
│   │   ├── routers/             # API 路由
│   │   ├── models/ schemas/     # 数据模型与响应契约
│   │   ├── tasks/ scheduler.py  # 定时任务（含唯一时区口径）
│   │   └── utils/timeutil.py    # **「现在」与「今天」的唯一来源**
│   ├── scripts/                 # 迁移、回填、研究台、因子闸门、文档生成、冒烟与开发工具
│   ├── tests/                   # unit / integration / e2e
│   ├── schema.sql               # MySQL（可选路径）建表脚本；SQLite 走模型 create_all
│   ├── goldmind.db              # 默认 SQLite 库（运行时生成，已被 .gitignore 忽略）
│   └── requirements*.txt
├── docs/                         # 中文文档
│   ├── en/                      # 英文镜像（与中文版一一对应）
│   ├── specs/                   # 各轮改动的 spec 与 plan（过程记录，不是第二权威）
│   ├── 00-产品方向.md · 10-密钥与隐私.md · 20-前端设计规范.md
│   ├── ARCHITECTURE.md · API.md
│   └── images/screenshots/      # README 截图（由 capture_screenshots.mjs 生成）
├── .github/
│   ├── workflows/ci.yml          # CI 闸门：后端 / 前端 / 浏览器端到端
│   └── dependabot.yml            # 依赖更新机器人
├── AGENTS.md                     # 怎么干活：规矩、闸门、流程
├── CHANGELOG.md / CHANGELOG_EN.md
├── CONTRIBUTING.md / CONTRIBUTING_EN.md
├── README.md / README_EN.md
└── docker-compose.yml            # 可选路径（未随本仓库实测）
```

---

## 🗺️ 文档地图

「改什么 → 读哪份」的唯一映射表。中英两份互为镜像：中文是权威版本，英文是同一份内容。

| 文档 | English | 讲什么 | 什么时候读 |
|---|---|---|---|
| [`AGENTS.md`](AGENTS.md) | —（保持中文） | 怎么干活：规矩、闸门、流程 | 动手前必读 |
| [`docs/00-产品方向.md`](docs/00-产品方向.md) | [`docs/en/product-direction.md`](docs/en/product-direction.md) | 产品要做什么；**现状 vs 目标** | 改需求、加功能前 |
| [`README.md`](README.md) | [`README_EN.md`](README_EN.md) | 目录、命令、配置（本文件） | 找命令 / 配置时 |
| [`docs/10-密钥与隐私.md`](docs/10-密钥与隐私.md) | [`docs/en/secrets-and-privacy.md`](docs/en/secrets-and-privacy.md) | 密钥规则与历史泄漏处理 | 动配置 / 密钥前 |
| [`docs/20-前端设计规范.md`](docs/20-前端设计规范.md) | [`docs/en/frontend-design.md`](docs/en/frontend-design.md) | 前端视觉语言：令牌、排版、组件、界面文案规则 | 改前端界面前 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | [`docs/en/architecture.md`](docs/en/architecture.md) | 架构设计（第十一节是量化引擎） | 动系统结构前 |
| [`docs/API.md`](docs/API.md) | [`docs/en/api.md`](docs/en/api.md) | 接口规范（**两份都由路由表生成**） | 改接口前 |
| [`CHANGELOG.md`](CHANGELOG.md) | [`CHANGELOG_EN.md`](CHANGELOG_EN.md) | 每个版本改了什么 | 升级前 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | [`CONTRIBUTING_EN.md`](CONTRIBUTING_EN.md) | 贡献流程 | 提 PR 前 |
| [`docs/specs/`](docs/specs/) | —（保持中文） | 各轮改动的 spec 与 plan（过程记录，不是第二权威）。本轮量化主线：`2026-10-02-量化策略提升路线图.md`、`2026-10-02-研究台报告.md`、`2026-10-02-量化引擎第三轮预注册.md`、`2026-10-02-量化引擎口径一致性修正.md` | 追溯某轮决定时 |

> 📌 `docs/API.md` 与 `docs/en/api.md` **不是手写的** —— 它们由
> `backend/scripts/gen_api_doc.py` 从 FastAPI 路由表生成，`backend/tests/integration/test_api_doc.py`
> 会在闸门里比对；路由改了、文档没改，闸门直接红。

---

## 🔄 工作流程

1. **数据采集**：腾讯财经实时金价、新浪财经 ICE 美元指数；历史数据回填支持新浪 / 东方财富 / Yahoo 三源；新闻经 RSS 抓取
2. **持久化**：金价、美元指数、新闻写入 SQLite（默认单文件；`DATABASE_URL` 可切 MySQL）
3. **分析**：5 个分析服务各自拼装 prompt → 调用一次 LLM（端点由 `LLM_*` 决定）→ 解析 JSON
4. **量化**：公开数据源 → 因子观测（当前值 + 修订流水）→ 滚动 z → 分尺度权重 → 一份校准分布 → 走查式回测与监测表
5. **缓存**：结果写入内存 + JSON 文件两级缓存（TTL 2 小时），供重启与多进程共享
6. **展示**：前端每 30 秒轮询行情接口（页面隐藏时暂停），分析结果按需拉取；量化预测落库时一并写入它那个尺度的实测技能状态

---

## 🤖 分析服务说明

早期文档把这 5 个服务描述为「LangChain Agent」，与实际实现不符。它们是**独立的单轮
LLM 调用**：彼此不通信、不共享状态，仅通过缓存与数据库间接关联。所有客户端统一经
`backend/app/services/llm_provider.py` 构造。

| 服务 | 代码位置 | 输入 | 输出 |
|---|---|---|---|
| 看涨因子 | `app/services/bullish_factor_service.py` | 最近 24h 新闻 + 金价 | 5 个看涨因子 + 总结 |
| 看跌因子 | `app/services/bearish_factor_service.py` | 最近 24h 新闻 + 金价 | 5 个看跌因子 + 总结 |
| 机构观点 | `app/services/institution_prediction_service.py` | 最近 30 天新闻 + 联网搜索 | 四家机构最近一次可核实的预测（含日期与来源） |
| 投资建议 | `app/services/investment_advice_service.py` | 市场状态 + 多空因子 + 机构观点 | 三档策略 + 风险提示 |
| 市场总结 | `app/services/market_summary_service.py` | 上述全部 | 核心逻辑 + 风险 + 综合判断 |

**模型**：由 `backend/.env` 的 `LLM_MODEL` 决定（供应商同理，见「本地开发」的环境变量）；
页面页脚显示的型号来自 `/health` 的 `ai_config`，不写死在代码里。

**降级行为**：任一服务在数据源或联网搜索不可用时，返回明确的「不可用」状态并回退到
数据库 / RSS 内容，**不会**编造数据。

前端在拿不到数据时**显示「暂不可用」并说明原因**，不摆任何内置的数字或结论。
这条以前只是写在文档里：各 section 其实各自带了一份写死的兜底数据
（金价 2823、机构目标价 5400/5000/4500/2700、14 个点的价格序列……），
接口一失败就把它们当成真实内容渲染出来。那些常量已全部删除，
并由测试钉住「失败时不得出现内置文案」。

**已删除**：早期存在的 `backend/app/agents/` 包（`BaseAgent` /
`MarketAnalyzerAgent` / `NewsAnalyzerAgent`）从未被任何地方实例化，已移除。

---

## ⚠️ 诚实声明（实现边界）

这一节是给「看到 README 的项目描述后产生预期」的人看的。以下能力**不存在**，
请不要按它们去理解这个项目：

| 传闻中的能力 | 实际情况 |
|---|---|
| 多 Agent 协作 | 5 个**独立的单轮 LLM 调用**，不是 Agent 协作：拼 prompt → `llm.invoke(prompt)` → 解析 JSON。没有工具调用循环、没有 Agent 间通信 |
| RAG / 向量检索 | 没有向量库、没有 embedding、没有检索步骤。历史价格与新闻是直接拼进 prompt 的上下文 |
| ReAct 推理循环 | 未实现，没有 Thought / Action / Observation 循环 |
| 实时联网搜索 | 默认关闭（`LLM_SEARCH_ENABLED=false`）。它用的是 MiMo 插件式 `web_search`，不是通用 OpenAI 能力；端点未开通时返回 `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`，此时回退到 RSS 新闻窗口 |
| 情感分析 | 不做情感分析：2.0.2 起 `/news` 响应里的死字段与 `/news/sentiment/summary` 端点已移除（DB 列留存历史数据、过滤参数保留），页面不展示情感结论 |
| Redis / 消息总线 / WebSocket / K8s / WAF / 认证中间件 | 都没有。缓存是内存 + JSON 文件两级 |
| 交易执行 | 不接券商、不下单、不托管资金 |
| 量化预测有统计优势 | **前向窗口尚不可判**（1 日 1/20 注，其余尺度 0/20）。历史留出期方向与「永远看多」逐日一致（+0.0pp）、Brier 技能分为负；页面与研究页如实展示，不替模型吹牛 |

**「某一节显示暂不可用」是设计行为，不是 bug**：推理模型的思考与正文共用
`LLM_MAX_TOKENS`（默认 8192）。这份额度太小，投资策略那种三档完整 JSON 会被截断、
解析失败，于是按红线返回空内容 —— 页面如实显示「投资策略暂不可用」，而不是摆一份
编造的策略（旧版本写死 4096，所以这一节长期为空。部署端把 `LLM_MAX_TOKENS` 调大
即可，本仓库开发期实测 32768 可稳定返回）。此外端点自带内容风控，
偶发返回 `finish_reason=content_filter`（正文是 "The request was rejected because it
was considered high risk"）：后端会自动重试一次，仍被拒时如实显示「暂不可用」，
点「重新分析」重试；解析失败时日志里有 `finish_reason` 与 token 用量可查。

**为什么这么啰嗦**：这个项目的核心承诺是「**不编造**」。数据源或联网搜索不可用时，
它返回「不可用」并说明原因，而不是让模型凭印象生成机构目标价、央行购金量或金价点位。
宁可页面显示「数据不可用」。

---

## 🤝 贡献

我们欢迎所有形式的贡献！请查看我们的[贡献指南](./CONTRIBUTING.md)
（[English](./CONTRIBUTING_EN.md)）了解如何参与项目。

### 贡献者

<a href="https://github.com/JasonBuildAI/GoldMind/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=JasonBuildAI/GoldMind" alt="Contributors" />
</a>

---

## 📄 许可证

本项目采用 [MIT 许可证](./LICENSE) 开源。

---

## 🙏 致谢

- 任何 OpenAI 兼容的 LLM 端点（本项目开发期用的是[小米 MiMo](https://platform.xiaomimimo.com/)）- 提供大语言模型与联网搜索能力
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能Web框架
- [React](https://react.dev/) - 前端UI框架
- 美国财政部、纽约联储、CFTC、Yahoo Finance、新浪财经、Iacoviello & Papaioannou（GPR） - 提供免密钥的公开数据源

---

## 📧 联系作者

如果您有任何问题、建议或合作意向，欢迎通过以下方式联系我们：

- 🐛 **问题与建议**：请在 [GitHub Issues](https://github.com/JasonBuildAI/GoldMind/issues) 提出

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/JasonBuildAI">JasonBuildAI</a></sub>
</p>
