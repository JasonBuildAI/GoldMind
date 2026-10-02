<p align="center">
  <img src="docs\images\6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>面向国际黄金市场的 AI 数据分析引擎</strong><br>
  <em>An AI Data Analysis Engine for the International Gold Market</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v2.0.0-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/released-2026--10--01-success?style=flat-square" alt="Release date">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/SQLite-零配置复现-003B57?style=flat-square&logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <a href="./README_EN.md">English</a> | <strong>中文文档</strong>
</p>

---

<!-- ⬇️⬇️⬇️ 2.0 发布横幅：以下三行是本次发布的「大字」部分，改版本时一起改 ⬇️⬇️⬇️ -->

<h1 align="center">🎉 GoldMind 2.0 正式发布</h1>

<h2 align="center">GoldMind 2.0 is here</h2>

<p align="center">
  <img src="https://img.shields.io/badge/release-v2.0.0-FFD700?style=for-the-badge" alt="v2.0.0">
  <img src="https://img.shields.io/badge/released-2026--10--01-2EA043?style=for-the-badge" alt="2026-10-01">
</p>

<p align="center">
  <strong>每一个数字都出自同一份经过校准的概率分布。</strong><br>
  <em>Every number on the page now comes from one calibrated distribution.</em><br><br>
  📋 <a href="./CHANGELOG.md">更新日志 CHANGELOG</a> ·
  🌍 <a href="./CHANGELOG_EN.md">Changelog (EN)</a> ·
  🚀 <a href="https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.0">GitHub Release v2.0.0</a>
</p>

<!-- ⬆️⬆️⬆️ 2.0 发布横幅结束 ⬆️⬆️⬆️ -->

---

## 🆕 2.0 带来了什么

2.0 不是一次换皮 —— 它修掉了一条会**悄悄吞掉真实数据**的旧规则，并把「预测」从一组各说各话的
数字，收敛成一份可回测、可核对、能自我说明局限的分布。

| 变化 | 之前 | 2.0 |
|---|---|---|
| 机构观点 | 只认「24 小时内发布」的新闻；当天没有新研报，四家机构就一起变成「暂无」 | 每机构给出**最近一次可核实的预测**（附预测日期与来源），扫描窗口 30 天可配；空结果**绝不覆盖**已有真实记录 |
| 预测口径 | 方向、概率、目标价、区间各自算各自的 | 方向 = sign(μ)、概率 = Φ(μ/σ)、目标价 = 基准价×(1+μ)、区间 = μ±1.2816σ、三情景 = N(μ, σ²) 分位数 —— **全部派生自同一份分布** |
| 区间宽度 | 正态分位，长尺度系统性偏窄 | 按**走查预测误差的经验分位**校准；覆盖率与「永远看多 / 动量 / 抛硬币」并排展示 |
| 文档 | 中文为主，API 文档是手写的、且已与实现脱节 | 中英**双版**；`docs/API.md` 与 `docs/en/api.md` 由同一个路由表生成，漂移直接让闸门变红 |
| 可核实性 | 数据没有「截至日」 | 每个因子带来源与数据截至日，每行预测带预测日期与滞后天数，取不到就明说「不可用 + 原因」 |

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
1～3 个月、6～18 个月）的方向、目标价与情景（全部出自同一份校准分布，未校准的因子偏向单列
一行），以一张单页的**浅色研究简报**呈现 —— 六节（行情 / 多空对照 / 机构观点 / 投资策略 /
量化预测 / 总结）全部左对齐，无渐变、无阴影、无卡片套件；数字表格化，红涨绿跌，且方向同时给
符号与文字。另有一张独立的**研究页**（`/research.html`）：把预注册候选 × 尺度的全档评估、
覆盖率与技能分数直接摆出来，**包括没有过线的结论**。

LLM 供应商**不写死**：任何 OpenAI 兼容端点（OpenAI / DeepSeek / 通义 / Kimi /
Ollama 本地模型 / 小米 MiMo ……）都能接 —— 改 `backend/.env` 里的
`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 三项即可，所有 LLM 客户端统一经
`backend/app/services/llm_provider.py` 构造。三项缺任意一项都算「未配置」，
各区块如实显示「暂不可用」，不会退回任何内置内容。

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

公开数据源 ──► 因子库 ──► 滚动 z 分数 ──► 分尺度权重合成 ──► 一份校准分布 ──► 量化预测
（财政部 / 纽联储 / CFTC /                                        │
  Yahoo / RSS，全部免密钥）                                        └──► 走查式回测 + 覆盖率
```

| 分析服务 | 输入 | 输出 |
|---|---|---|
| 看涨因子 | 最近 24h 新闻 + 金价 | 5 个看涨因子 |
| 看跌因子 | 最近 24h 新闻 + 金价 | 5 个看跌因子 |
| 机构观点 | 最近 30 天新闻 +（搜索） | 四家机构最近一次可核实的预测（含日期与来源） |
| 投资建议 | 市场状态 + 多空因子 + 机构观点 | 保守/均衡/机会三档策略 |
| 市场总结 | 上述全部 | 核心逻辑、风险、综合判断 |

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

### 报头与行情
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/dashboard.jpeg" alt="报头与行情" width="800">
</p>

### 走势与关键数据
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/price-chart.jpeg" alt="走势图与关键数据" width="800">
</p>

### 多空对照
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-up.jpeg" alt="看涨因素" width="400">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-down.jpeg" alt="看跌因素" width="400">
</p>

> 两侧独立取数、独立刷新，一侧取不到结果不影响另一侧。截图拍摄当天模型只给出 2 个
> 有新闻支撑的看跌因素 —— prompt 明确要求「宁可少给几个，也不要为了凑满数量而凭常识
> 编造」；一条都取不到时页面如实显示「暂不可用」，点「重新分析」重试，不摆内置文案。

### 机构观点
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/institutional-views.jpeg" alt="机构观点" width="800">
</p>

> 联网搜索默认关闭（`LLM_SEARCH_ENABLED=false`）：它用的是 MiMo 插件式的 `web_search`
> 工具，不是通用 OpenAI 能力，开启前需在端点侧开通，否则返回
> `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`
> （实测，可用 `backend/scripts/smoke_llm.py` 复现）。
> 关闭时回退到新闻窗口，提取每家机构**最近一次可核实**的预测，并在「预测日期」列出该预测
> 最近一次被核实的日期，超过 30 天标注「已滞后 N 天」。一条都找不到才显示「暂无」，
> 而且**空目标价不会覆盖库里已有的真实记录**。
> 截图拍摄时 30 天新闻窗口内没有任何可核实的机构目标价，四家机构都如实显示「暂无最新预测」。

### 投资策略
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/investment-advice.jpeg" alt="投资策略" width="800">
</p>

> 三档策略由一次 LLM 调用生成，输出预算由 `LLM_MAX_TOKENS` 控制（默认 8192）。
> 预算太小会把这份大 JSON 截断、解析失败 —— 页面如实显示「暂不可用」，而不是摆一份
> 内置策略；解析失败时后端日志会记下 `finish_reason` 与 token 用量，便于下次定位。

### 量化预测
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/quant-prediction.jpeg" alt="量化预测：五个尺度的方向、概率与三情景" width="800">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/quant-fair-value.jpeg" alt="公允价值分解" width="800">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/quant-monitor.jpeg" alt="监测仪表盘（周更表）" width="800">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/quant-accuracy.jpeg" alt="回测命中率与基准对照" width="800">
</p>

> 量化引擎不调用大模型：14 个因子全部来自免费公开数据源，取不到的因子与指标如实标「不可用」
> 并说明原因，可用因子少于 3 个时直接显示「预测不可用」。截图拍摄时 12/14 个因子可用；
> 方向、概率、目标价与三情景全部派生自同一份校准分布（口径见「量化策略」一节）。

### 总结
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/market-summary.jpeg" alt="市场总结" width="800">
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
| 黄金 ETF 份额（GLD） | 供需结构 | 份 | Yahoo Finance（自采集日起积累） | +1 | 0.3 / 0.4 / 0.5 / 0.7 / 0.8 | 7 天 |
| 黄金趋势动量 | 市场与技术面 | %（60 日） | Yahoo Finance（GC=F 收盘） | +1 | 1.0 / 1.0 / 0.4 / 0.3 / 0.2 | 7 天 |
| 季节性（当月历史平均） | 市场与技术面 | %（历史均值） | 自有价格序列（只用往年同月） | +1 | 0.2 / 0.3 / 0.2 / 0.2 / 0.2 | 7 天 |
| 比特币（数字黄金叙事） | 市场与技术面 | 点 | Yahoo Finance（BTC-USD） | −1 | 0.2 / 0.2 / 0.2 / 0.2 / 0.3 | 7 天 |
| 股市风险偏好 | 市场与技术面 | 点 | Yahoo Finance（SPY） | −1 | 0.5 / 0.4 / 0.3 / 0.2 / 0.2 | 7 天 |

方向先验来自经济机理，**不保证成立** —— 回测逐因子报告单独命中率与 IC，方向与实际相反时页面
照样如实展示。

### 二、五个尺度与各自的「主导层」

方法论的第一步是**先选时间尺度，再选变量** —— 同一份因子在不同周期上的权重并不相同：

| 尺度 | 标签 | 对应现实周期 | 主导层 | 说明 |
|---|---|---|---|---|
| 1 个交易日 | 1 日 | 日内～一周 | 市场与技术面 → 供需结构 | 资金流、技术面、仓位拥挤度主导，宏观基本面权重最低 |
| 5 个交易日 | 1 周 | 日内～一周 | 市场与技术面 → 避险与信用 | 一周资金流与事件脉冲主导，宏观仍居次席 |
| 20 个交易日 | 1 月 | 1～3 个月 | 货币政策与利率 → 供需结构 | 政策预期、经济数据、美元指数主导 |
| 60 个交易日 | 1 季 | 1～3 个月 | 货币政策与利率 → 供需结构 | 政策路径与需求结构并重 |
| 250 个交易日 | 1 年 | 6～18 个月 | 供需结构 → 货币政策与利率 | 实际利率周期、降息路径、央行购金趋势主导 |

这也是为什么 14 个因子各带一组五维权重，而不是一个全局权重 —— 拿「央行购金」去解释明天
的金价，和拿「VIX」去解释明年的金价，都是把尺度搞反了。

### 三、一份校准分布，所有出口都由它派生

因子合成的得分 `score` 是**未校准**的输入 —— 它只在因子表与「因子偏向（未校准）」一行展示。
页面上所有结论都出自同一个 `engine.build_prediction_frame` 出口：

```
μ    = α + β · score              扩展窗口 OLS，样本对满足 s + h ≤ t
σ    = std(r_s − μ_s | s+h ≤ t) × q80( |r_s − μ_s| / (1.2816 · σ_s) )
                                  走查预测误差的标准差，再按误差的经验分位校准宽度
p_up = Φ(μ / σ)                    上行概率
目标价 = 基准价 × (1 + μ)           基准价 = COMEX 主力期货日收盘（gold_close）
80% 区间 = μ ± 1.2816σ
三情景  = N(μ, σ²) 的分位数          Base [q25, q75] / Bull 上 25% / Bear 下 25%
方向    = sign(μ)                   恰为 0 记「持平」
```

模型版本 **`quant-v4`**。四条硬口径：

1. **无前视**。滚动统计与回归样本全部 `shift` 到 t 之前；在黄金收盘之后才发布的数据源
   （财政部收益率曲线、纽约联储 EFFR、CFTC 持仓）整体右移一个工作日。
   守卫：`backend/tests/unit/quant/test_no_lookahead.py` —— 把 t 之后的数据改成垃圾值，
   t 时刻的信号必须逐位不变。
2. **不退回「预期不变」**。回归样本不足 60 组时该尺度整体「不可用 + 原因」，
   不拿得分符号顶替方向，也不假装 μ = 0。已实现误差不足 60 组时，σ 退回
   「已实现 h 日收益的扩展标准差」，仍然只用过去的数据。
3. **缺失因子按剩余权重归一**，不会被当成 0；可用因子少于 3 个直接「预测不可用」。
4. **时间只走一个时区**（`app.utils.timeutil`，默认 `Asia/Shanghai`）。

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

> 有了它，「现在贵不贵」就不是一句感觉 —— 而是「市场价比模型算出的公允价高/低几个百分点，
> 其中多少来自需求、多少来自风险、多少是情绪」。

### 五、情景的触发与失效条件

三个情景不是拍脑袋写的：Base 取分布中间的 50%（q25～q75），Bull 与 Bear 各取上下 25%，
因此三者的概率之和恒为 100%。每个情景另外给出**触发条件**与**失效条件** ——
由该尺度**最重因子**与 **200 日均线**生成，是可以在页面上逐条核对的句子，而不是形容词。
σ 非正、基准价缺失或没有可用因子时返回「不可用 + 原因」，不阻塞预测主输出。

### 六、回测口径与三个基准

回测（`backtest.py`）是**走查式**的：每个历史时点只用当时可得的数据，评的是**校准后的方向**
（`sign(μ)`），并且永远与三个基准并排展示：

| 基准 | 含义 |
|---|---|
| 永远看多 | 无视一切信号，每天都猜涨 |
| 动量 | 沿最近一段的趋势外推 |
| 抛硬币 | 50% |

另外单列三项：**未校准得分方向**的成绩（`metrics.score_direction_accuracy`，用来回答
「校准到底有没有加分」）、**80% 名义区间的实际覆盖率**（`metrics.interval_coverage_80`）、
以及以 2022-01-01 为界的**分段成绩**（`metrics.regimes`）；逐因子命中率与 IC 也逐条列出，
某段样本不足时只给样本数与原因，不凑数字。

**实测覆盖率与命中率（2026-10-02 重算，页面同源）：**

| 尺度 | 1 日 | 1 周 | 1 月 | 1 季 | 1 年 |
|---|---|---|---|---|---|
| 留出期（2023-10-02 起）方向命中率 | 56.3% | 62.2% | 68.2% | 83.3% | 100% |
| 留出期「永远看多」 | 56.3% | 62.2% | 68.2% | 83.3% | 100% |
| 开发期方向命中率 | 52.2% | 54.0% | 53.5% | 57.5% | 63.1% |
| 留出期 80% 区间覆盖率 | 78.9% | 77.6% | 73.2% | 61.2% | 24.1% |

名义值 80%。**1 年尺度的覆盖率仍未达标（24.1%，方案段验收线 ≥70%）**，已列进下一轮的头号
问题 —— 见第十节「已知限制」。留出期里模型方向与「永远看多」逐日一致（差 +0.0pp，2023-10
后是黄金单边上涨行情）：这一轮没有把模型换成一个没有证据支持的新版本，裁决过程见第七节。

### 七、研究台与预注册：改进必须先在留出期上过线

「回测好看」不是证据 —— 在同一份数据上反复挑参数，总能挑出一条漂亮的曲线。所以任何
改进都要**先注册、后检验**：候选清单、选择规则与通过线在实验开始前写死
（`docs/specs/2026-10-02-量化策略提升路线图.md` 第 6.1 节；规则的唯一实现是
`backend/app/services/quant/preregistered.py`）。实验工具是 `backend/scripts/quant_lab.py`，
页面入口是「研究」页（`app/research.html` ← `GET /api/gold/quant/research`）。

**2026-10-02 的裁决：17 个候选 × 5 个尺度，没有一条过线。**

| 候选族 | 数量 | 留出期结果 |
|---|---|---|
| 基线族 B0（线上口径） | 1 | 与「永远看多」持平（+0.0pp），Brier 技能分为负 |
| 漂移三档 D1 / D3 / D5 | 3 | 无一过线 |
| 合成四档 S1–S4 | 4 | 无一过线 |
| 分布四档 P1–P4 | 4 | 加宽区间能把覆盖率拉高（如 P3 正态区间 100%），但方向与 Brier 技能没有改善 |
| 因子集四档 F1–F4 | 4 | 无一过线 |
| 集成一档 E0 | 1 | 无一过线 |

按预注册规则**保留 `quant-v4`**，研究页与研究台统一标注「无统计优势」。全档结果（每个候选的
逐尺度数字与失败原因）见 `docs/specs/2026-10-02-研究台报告.md`；复现命令
`python scripts/quant_lab.py`（读缓存约 0.0 秒、全量重算约 6 秒）。

> 这一轮的诚实结论：对预测能力的真实提升是**「评估从此可信」** —— 数据完整（20 年回填）、
> 区间与显著性口径统一（HAC / DM / Brier 技能分 / 分块自助）、结论可复现 —— 而不是换一个
> 没有证据支持的模型。下一轮候选必须重新预注册（先写清单、再看留出期）。

### 八、监测仪表盘：16 行水位表

`monitor.py` 覆盖 **16 行**指标，每行给出频率、来源、当前值、信号（看涨 / 看跌 / 中性 / 信息）
与数据截至日。信号规则是确定性阈值，集中在 `_rule` 一处；汇率、人民币金价与未平仓合约是
**信息型**指标（`signal = null`），不硬套多空；取不到数据或历史不足的行如实返回
「不可用 + 原因」。

每行的更新频率跟随它自己的数据源（日 / 周 / 月），不是统一刷新：

| 频率 | 指标 |
|---|---|
| 日 | 美债 10 年期实际利率、盈亏平衡通胀、美元指数（DXY）、市场隐含政策预期、GLD 份额、上海金溢价、VIX、信用偏好（HYG/IEF）、金价 vs 200 日均线、USDCNY、人民币金价参考、美国财政部 TGA 余额、纽约联储 RRP |
| 周 | CFTC 净多头（拥挤度）、COMEX 黄金未平仓合约 |
| 月 | 央行黄金储备 |

> 仪表盘是「给你看的水位」，不是打分项 —— 其中 `usdcny` / `cny_gold` / `tga` / `rrp` /
> `cftc_oi` 五条序列与因子同表存储，但**不参与**信号合成。

### 九、数据源与新鲜度

- **全部免费、无需密钥**：美国财政部收益率曲线与 Fiscal Data（TGA）、纽约联储 RRP 与 EFFR、
  CFTC 持仓报告、Yahoo Finance（DXY / GC=F / GLD / SPY / BTC-USD / ^VIX / HYG / IEF / CNY=X）、
  新浪财经（央行官方储备）、本系统自己的 RSS 语料。
- **按源节流**：同步器给每个源单独设 6h～24h 的节流窗口，增量抓取；某个源失败不影响其它源，
  失败原因写进同步报告并显示在页面上。
- **按因子设新鲜度上限**（上表最后一列）：日频 7 天覆盖长假，月度 62 天覆盖发布推迟。
  超过上限的因子标「**陈旧**」并被排除出合成，而不是继续拿旧值充数。
- **首次回填 10 年**，之后只抓增量；`factor_observations` 对 `(factor_key, obs_date)` 建唯一
  约束，重复抓取是幂等的。

### 十、已知限制（我们不加修饰地写在这里）

1. **1 年尺度的漂移项系统性偏低**。2023-10 起的留出期是黄金单边上涨行情，μ 系统性低估了
   涨幅，250 日 80% 区间的实际覆盖率只剩 **24.1%**，而加宽区间补不回方向上的偏差。
   这是下一轮的头号攻关点（本轮 17 个候选都没能过预注册线）。页面把覆盖率与
   「永远看多 / 动量」并排展示，让你自己判断。
2. **上海金溢价不可用**。上海黄金交易所 AU9999 没有公开免密钥接口，实测取不到数，
   该行如实显示「不可用 + 原因」，不编数字。
3. **联网搜索默认关闭**。它用的是 MiMo 插件式的 `web_search` 工具，不是通用 OpenAI 能力；
   端点侧未开通时返回 `HTTP 400 · web search tool found in the request body, but
   webSearchEnabled is false`（实测可复现）。开启方式：`LLM_SEARCH_ENABLED=true`
   且端点侧已开通插件；未开启时机构观点回退到 RSS 新闻窗口，不发起无效请求。
4. **地缘风险强度是语料代理指标**（最近新闻中相关报道占比），不是 GPR 官方指数。
5. **无鉴权、无多租户**。所有接口公开可访问，包括会触发付费 LLM 调用的 `POST .../refresh`。
6. **留出期方向无信息优势**。2023-10-02 起的留出期里，五个尺度的方向与「永远看多」逐日
   一致（+0.0pp），Brier 技能分为负 —— 见第七节的预注册裁决与
   `docs/specs/2026-10-02-研究台报告.md`。
7. **不是交易系统**。不下单、不接券商、不托管资金；所有产出都带免责声明。

---

## 🚀 快速开始

### 前置要求

| 工具 | 版本要求 | 说明 | 安装检查 |
|------|----------|------|----------|
| Node.js | ≥22.22.2（或 24.15+/26+） | 前端运行环境，包含 npm。下限来自 lockfile 里最严的依赖（jsdom `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0`）；Node 22.2.0 能跑起来，但 Vite 会打印版本告警 | `node -v` |
| Python | 3.11 - 3.12 | 后端运行环境 | `python --version` |
| SQLite | Python 内置 | 数据存储：单文件 `backend/goldmind.db`，**零安装、零配置** | 无需检查 |
| Google Chrome | 任意近期版本 | 前端端到端测试复用本机已装的 Chrome，**不下载** Playwright 自带浏览器 | 打开 Chrome → `chrome://version` |

### 本地开发（文档化路径：SQLite 零配置）

#### 1. 配置环境变量

```bash
# 复制示例配置文件
cd backend
cp .env.example .env

# 编辑 .env 文件，填入必要的 API 密钥
```

**必需的环境变量：**

```bash
# ============================================
# 数据库配置（默认 SQLite，零安装）
# ============================================
# 不填 DATABASE_URL = 用 backend/goldmind.db（单文件 SQLite），无需安装任何数据库。
# 这一项是**唯一真源**：后端应用、init_db.py、seed_data.py、scripts/*.py 都从这里取。
# 只有想改用 MySQL 时才显式覆盖它（可选；未随本仓库实测）：
# DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/gold_analysis

# ============================================
# LLM 接入（任何 OpenAI 兼容端点，三项必须同时填）
# ============================================
# 供应商不写死 —— 换下面任意一家（或自建、本地 Ollama）都只改这三行：
#   OpenAI        LLM_BASE_URL=https://api.openai.com/v1
#                 LLM_MODEL=gpt-4o-mini
#   DeepSeek      LLM_BASE_URL=https://api.deepseek.com/v1
#                 LLM_MODEL=deepseek-chat
#   通义千问       LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
#                 LLM_MODEL=qwen-plus
#   Kimi          LLM_BASE_URL=https://api.moonshot.cn/v1
#                 LLM_MODEL=moonshot-v1-8k
#   Ollama（本地） LLM_BASE_URL=http://localhost:11434/v1
#                 LLM_MODEL=qwen2.5:14b
#   小米 MiMo      LLM_BASE_URL=https://api.xiaomimimo.com/v1
#                 LLM_MODEL=mimo-v2.6-flash
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
# 仅用于界面展示的供应商标签，可留空
LLM_PROVIDER=
```

**可选的环境变量**（完整清单见 [`backend/.env.example`](backend/.env.example)）：

| 变量 | 默认值 | 作用 |
|---|---|---|
| `INSTITUTION_NEWS_LOOKBACK_DAYS` | `30` | 机构观点扫描新闻的窗口（天）。窗口内取每家机构**最近一次可核实**的预测，可以是较早发布的那条 |
| `DEBUG` | `false` | 只影响 uvicorn 的 `--reload`；本地开发想要热重载就在 `.env` 里设 `true` |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `CACHE_DIR` | `backend/cache` | 两级缓存里文件缓存的落盘目录 |
| `NEWS_RSS_SOURCES` | 内置默认源 | 形如 `名称\|URL,名称\|URL` |
| `LLM_MAX_TOKENS` | `8192` | 单次输出 token 上限；推理模型的思考与正文共用这份额度，调小会让三档策略这类大 JSON 被截断、解析失败 |
| `LLM_SEARCH_ENABLED` | `false` | 是否启用插件式联网搜索（MiMo `web_search`）；开启前需端点侧已开通 |
| `LLM_SEARCH_MODEL` / `LLM_SEARCH_BASE_URL` / `LLM_SEARCH_API_KEY` | 跟随推理配置 | 搜索单独使用另一套模型 / 端点 / 密钥时才填 |
| `LLM_TRUST_ENV` | `false` | 是否让 httpx 读宿主的代理环境变量；走代理访问 LLM 端点时设为 `true` |
| `GOLDMIND_TEST_DATABASE_URL` | 未设置 | 只在跑测试时用：让同一套用例跑在另一个数据库上（默认内存 SQLite；只有你确实要验 MySQL 时才需要） |
| `SCHEDULER_TIMEZONE` | `Asia/Shanghai` | **全项目唯一的时区口径**，定时任务与「今天」都按它算 |

#### 2. 安装依赖

**后端依赖：**

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

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

#### 3. 初始化数据库（SQLite，零配置）

```bash
cd backend

# 建表 + 抓取并填充 2025 年至今的历史数据（需要联网访问公开数据源）
python init_db.py

# 只建表、不抓数据：几秒完成，离线可用
SKIP_SEED=1 python init_db.py
```

**数据初始化说明：**

`init_db.py` 会自动完成以下操作：
1. 创建 SQLite 库文件 `backend/goldmind.db`（不存在时）并建出全部数据表
2. **自动获取并填充历史数据**（2025年1月1日至今）
   - 黄金价格数据：开盘价、最高价、最低价、收盘价
   - 美元指数数据：开盘价、最高价、最低价、收盘价

**数据源优先级（国内优先）：**
- 黄金数据：新浪财经 → 东方财富 → Yahoo Finance
- 美元指数：东方财富 → Yahoo Finance

> 💡 **提示**：脚本会自动尝试多个数据源，确保国内用户也能成功获取数据。如果所有数据源都失败，您可以稍后再运行 `python seed_data.py` 重试。

**跳过数据填充（仅创建表结构）：**
```bash
SKIP_SEED=1 python init_db.py
```

**手动填充数据：**
```bash
# 如果初始化时跳过数据填充，或需要更新数据
python seed_data.py
```

**老库升级**（已经建过库、现在要升到 2.0 的）：

```bash
cd backend

# 机构观点：加 as_of_date / source 两列，并把旧别名行里的真实预测复制到规范行（只加不删）
python scripts/migrate_institution_views.py --dry-run   # 默认就是 dry-run，先看会做什么
python scripts/migrate_institution_views.py --apply
# 回滚（删除这两列，既有数据行不动）
python scripts/migrate_institution_views.py --drop-columns --yes

# 量化因子引擎：升级到带 factor_observations / model_evaluations 的结构（幂等，只加不删）
python scripts/migrate_quant.py --dry-run
python scripts/migrate_quant.py
```

#### 4. 启动服务

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

- 五个分析区块**不会立刻有内容**：无缓存时先返回空结果并在后台跑一次分析
  （页面提示「AI 分析进行中，首次加载可能需要 1-2 分钟」），跑完自动出现；
  也可以点各区块的「重新分析 / 重新抓取」手动触发。
- 量化预测首次需要回填多年历史因子，要等抓取完成才会从「不可用」变成有数字；之后是增量更新。
- 页面每 10 秒轮询行情接口；默认限流 60 次/分（LLM 接口 6 次/分），正常浏览不会触发。

**服务地址：**
- 前端: http://localhost:5173
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

### 可选：MySQL / Docker（未随本仓库实测）

本 README 的快速开始、闸门命令与 CI **只走 SQLite** —— 这是唯一被仓库实测覆盖的复现路径。
仓库里仍保留两处可选的 MySQL / 容器化资产，供确实需要的人参考，但**不保证在当前版本下
开箱可用**：

- `docker-compose.yml` + `backend/schema.sql`：三容器（mysql / backend / frontend）编排。
  MySQL 首次启动会用 `schema.sql` 建表；容器内后端的 `DATABASE_URL` 由 compose 注入。
- 改用本机 MySQL：在 `backend/.env` 里写
  `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/gold_analysis`，
  然后 `python init_db.py`（MySQL 路径会先建库、再执行 `schema.sql`）。

> ⚠️ 这两条路径与本轮的 SQLite 默认路径**没有跑过同一套闸门**，行为差异（ENUM 存储、
> 字符串比较大小写、事务语义）已知存在。用之前请先跑一遍
> `GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" python -m pytest`，
> 确认基线再上线。
---

## 🧪 常用命令

**闸门命令的唯一真源。** 改完代码必须全部跑绿（规矩见 [`AGENTS.md`](AGENTS.md)）。

### 后端

```bash
cd backend

# 安装依赖（首次）
pip install -r requirements.txt -r requirements-dev.txt

# 配置级自检（只读：不连库、不出网；失败项会给出修复命令，退出码 0/1）
python scripts/verify_setup.py

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

# 机构观点：加 as_of_date / source 并把真实预测复制到规范行（幂等；**不删除任何行**）
python scripts/migrate_institution_views.py --dry-run
python scripts/migrate_institution_views.py --apply
# 回滚（删除两列；已有的数据行不动）
python scripts/migrate_institution_views.py --drop-columns --yes

# 量化因子引擎：老库升级到带 factor_observations / model_evaluations 的结构（幂等，只加不删）
python scripts/migrate_quant.py --dry-run    # 先看会做什么
python scripts/migrate_quant.py
# 回滚（删除两张新表与 predictions 的量化列，既有数据不动）
python scripts/migrate_quant.py --drop --yes

# 手动跑一轮因子抓取（首次回填 10 年；之后是增量）
python -c "from app.database import SessionLocal; from app.services.quant.sync import run_sync; db=SessionLocal(); print(run_sync(db, force=True).to_dict()); db.close()"

# 量化研究台：预注册候选 × 尺度的全档评估（默认读缓存；--refresh 全量重算）
python scripts/quant_lab.py
python scripts/quant_lab.py --refresh
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
```

### 浏览器端到端测试

`npm run test:e2e` 会真的把三个服务拉起来，再由真实浏览器访问：

1. 假 LLM 服务（`backend/scripts/dev_mock_llm.py`，OpenAI 协议兼容，不消耗额度）
2. 真后端（uvicorn + SQLite，数据由 `backend/scripts/dev_seed_sqlite.py` 准备）
3. 构建产物（`vite preview`，经代理把 `/api` 转发给后端）

它复用本机已安装的 Chrome，**不下载** Playwright 自带浏览器。若你的 Python
不在 `PATH` 上，用 `E2E_PYTHON` 指定解释器：

```powershell
$env:E2E_PYTHON = "path\to\python.exe"
cd app
npm run build
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
仍复用已安装的 Chrome。

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

---

## 🗂️ 目录结构

```
GoldMind/
├── app/                          # 前端（React 19 + TypeScript + Tailwind）
│   ├── src/
│   │   ├── sections/            # 六个页面区块 + 各自的测试
│   │   ├── research/            # 「研究」页：预注册评估的全档结果
│   │   ├── components/          # 可复用组件（含机构观点的预测日期列）
│   │   ├── layout/              # 报头 / 页脚
│   │   ├── services/            # API 客户端与类型定义（api.ts）
│   │   └── test/                # 测试夹具
│   └── package.json
├── backend/                      # 后端（FastAPI + SQLAlchemy；默认 SQLite 单文件）
│   ├── app/
│   │   ├── services/            # 业务逻辑
│   │   │   ├── llm_provider.py                     # **LLM 调用的唯一入口**
│   │   │   ├── institution_prediction_service.py   # 机构观点（含机构注册表）
│   │   │   └── quant/                              # 量化引擎：sources / derive / storage /
│   │   │                                           #   sync / engine / decompose / scenarios /
│   │   │                                           #   backtest / monitor / service /
│   │   │                                           #   stats / preregistered
│   │   ├── routers/             # API 路由
│   │   ├── models/ schemas/     # 数据模型与响应契约
│   │   ├── tasks/ scheduler.py  # 定时任务（含唯一时区口径）
│   │   └── utils/timeutil.py    # **「现在」与「今天」的唯一来源**
│   ├── scripts/                 # 迁移脚本、文档生成器、冒烟与开发工具
│   ├── tests/                   # unit / integration / e2e
│   ├── schema.sql               # MySQL（可选路径）建表脚本；SQLite 走模型 create_all
│   ├── goldmind.db              # 默认 SQLite 库（运行时生成，已被 .gitignore 忽略）
│   └── requirements*.txt
├── docs/                         # 中文文档
│   ├── en/                      # 英文镜像（与中文版一一对应）
│   ├── specs/                   # 各轮改动的 spec 与 plan（过程记录）
│   ├── 00-产品方向.md · 10-密钥与隐私.md · 20-前端设计规范.md
│   ├── ARCHITECTURE.md · API.md
│   └── images/screenshots/
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
| [`docs/specs/`](docs/specs/) | —（保持中文） | 各轮改动的 spec 与 plan（过程记录，不是第二权威）；本轮量化见 `2026-10-02-量化策略提升路线图.md` + `2026-10-02-研究台报告.md` | 追溯某轮决定时 |

> 📌 `docs/API.md` 与 `docs/en/api.md` **不是手写的** —— 它们由
> `backend/scripts/gen_api_doc.py` 从 FastAPI 路由表生成，`backend/tests/integration/test_api_doc.py`
> 校验两份都与实现一致。改接口后运行 `cd backend && python scripts/gen_api_doc.py` 重新生成即可。

---

## 🔄 工作流程

1. **数据采集**：腾讯财经实时金价、新浪财经 ICE 美元指数；历史数据回填支持新浪 / 东方财富 / Yahoo 三源；新闻经 RSS 抓取
2. **持久化**：金价、美元指数、新闻写入 SQLite（默认单文件；`DATABASE_URL` 可切 MySQL）
3. **分析**：5 个分析服务各自拼装 prompt → 调用一次 LLM（端点由 `LLM_*` 决定）→ 解析 JSON
4. **量化**：公开数据源 → 因子库 → 滚动 z → 分尺度权重 → 一份校准分布 → 走查式回测
5. **缓存**：结果写入内存 + JSON 文件两级缓存（TTL 2 小时），供重启与多进程共享
6. **展示**：前端每 10 秒轮询行情接口，分析结果按需拉取

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
| 多 Agent 协作 | 4 个**独立的单轮 LLM 调用**，不是 Agent 协作：拼 prompt → `llm.invoke(prompt)` → 解析 JSON。没有工具调用循环、没有 Agent 间通信 |
| RAG / 向量检索 | 没有向量库、没有 embedding、没有检索步骤。历史价格与新闻是直接拼进 prompt 的上下文 |
| ReAct 推理循环 | 未实现，没有 Thought / Action / Observation 循环 |
| 实时联网搜索 | 默认关闭（`LLM_SEARCH_ENABLED=false`）。它用的是 MiMo 插件式 `web_search`，不是通用 OpenAI 能力；端点未开通时返回 `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`，此时回退到 RSS 新闻窗口 |
| 情感分析 | `sentiment` 字段恒为 `NEUTRAL`，只为接口形状稳定，页面不展示情感结论 |
| Redis / 消息总线 / WebSocket / K8s / WAF / 认证中间件 | 都没有。缓存是内存 + JSON 文件两级 |
| 交易执行 | 不接券商、不下单、不托管资金 |

**「某一节显示暂不可用」是设计行为，不是 bug**：推理模型的思考与正文共用
`LLM_MAX_TOKENS`（默认 8192）。这份额度太小，投资策略那种三档完整 JSON 会被截断、
解析失败，于是按红线返回空内容 —— 页面如实显示「投资策略暂不可用」，而不是摆一份
编造的策略（旧版本写死 4096，所以这一节长期为空）。此外端点自带内容风控，
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
- 美国财政部、纽约联储、CFTC、Yahoo Finance、新浪财经 - 提供免密钥的公开数据源

---

## 📧 联系作者

如果您有任何问题、建议或合作意向，欢迎通过以下方式联系我们：

- 🐛 **问题与建议**：请在 [GitHub Issues](https://github.com/JasonBuildAI/GoldMind/issues) 提出

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/JasonBuildAI">JasonBuildAI</a></sub>
</p>
