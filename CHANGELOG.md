# 更新日志

本文件记录每个版本改了什么，**一行一条**。版本号与 git tag 一一对应：
`vX.Y.Z` 对应下面的 `## [X.Y.Z] - YYYY-MM-DD`。

版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)，格式参考
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

> 🌐 [中文](./CHANGELOG.md) | [English](./CHANGELOG_EN.md)

---

## [Unreleased]

（下一轮的未发布内容记在这里；2.0.3 的全部改动见下方。）

---

## [2.0.3] - 2026-10-03

### 变更

- **研究页加了显式的返回按钮**。研究页是独立入口（`research.html`）、没有客户端路由，
  回看板原本只能靠导航里的一个「看板」文字项（混在一堆锚点中间，用户反馈「进去以后
  无法返回主页」）。现在左栏最上面是「‹ 返回看板」按钮，两个入口的**字标本身也是
  回主页的链接**；`ResearchPage.test.ts` 守着这两条。
- **版式改成「左侧栏 + 内容区」两栏，整页铺满**。字标、锚点导航、今日速览与数据新鲜度
  从顶部横条搬进左侧栏（`AppSidebar`，整列吸顶、半透明底、右侧发丝线），内容区把剩余
  宽度全部吃掉 —— 不再把正文居中收窄到 1180px，宽屏上表格与图表能一次看全；可读性改由
  各区块自己的 68ch 行宽上限保证。窄于 960px 落成单栏，左栏回到页面顶部横条。
- **前端整体重写：React 19 → Vue 3 + Pinia**。`app/src` 按功能分组
  （`views/dashboard` / `views/research` / `components` / `stores` / `composables` / `styles`），
  一个文件只讲一件事；两个 HTML 入口（看板 / 研究页）与 `./research.html` 相对链接不变。
  测试从 Testing Library 迁到 `@vue/test-utils`，类型检查改走 `vue-tsc`。
- **视觉语言改为 Apple macOS / HIG**：分层表面、发丝线、圆角 6/8/10、两级极轻阴影、
  半透明左栏与卡片浮层、系统字体栈（去掉衬线栈）与 Apple 语义色板；
  所有前景/背景对按 4.5:1 实测。规范见 `docs/20-前端设计规范.md`（第二、四节整节改写）。
- 顺带删掉**实际没用上**的依赖：Tailwind（639 处 `className` 里只有 6 处是工具类）、
  recharts（只用在 2 处图表，改为自绘 SVG）、Radix Tabs（改为自研 ARIA tablist）、
  lucide-react / clsx / tailwind-merge。前端产物 JS 从 863 kB 降到 312 kB。
- **「消息」从「驱动」里独立成一等板块**：左栏在「驱动」与「量化预测」之间多出 `#messages`
  入口，原始事实与模型解读分成两个区块、各自可达。
- **消息卡片中文化**：英文来源每条在折叠态给出**中文标题与 2–3 句导语**（只压缩来源标题与
  摘要已有的事实，英文原题与摘要原样保留、可逐条核对；翻不了时如实显示原因）。译文落库
  四个可空列（`title_zh` / `brief_zh` / `translated_at` / `translation_model`，换模型会
  触发重译）；每次抓取后批量翻译一轮（上限 `NEWS_TRANSLATE_BATCH`，默认 30，已译的不重复付费）。
- **每个金价都带自己的刷新时间**：六个展示国际金价的位置（侧栏速览、行情结论行与报价块、
  今日结论的当前价格、降级策略快照、量化基准价与公允价值市场价）逐处显示「这个价是什么时候的」，
  连同口径（`basis`）与来源；取不到价时字段保持空、页面说「时间未知」，不编一个时间。
- **README 的截图一节改成表格化卡片**：15 张全部用当前前端 + 真实栈重拍，分组顺序＝页面阅读顺序
  （首屏 · 今日结论 / 行情 / 走势 / 多空对照 / 机构观点 / 消息 / 量化预测 / 投资策略 / 研究页），
  每张配一句「这张图看什么」。旧 `price-chart`（5434px 高的长图）拆成「行情」+「走势」两屏，
  `market-summary` 并入首屏，新增「消息」一屏（14 → 15 张）；
  `docs/20-前端设计规范.md` 与英文版同步到 15 张。
- **截图脚本可以只重拍其中几张（`SCREENSHOT_ONLY=<名字片段>`），裁剪边界改成等它渲染**。
  `padToText` 此前只找一次，而边界块可能是懒渲染的 —— 找不到就静默回落到写死的像素数，
  同一块两次拍摄会裁出两个高度（研究页「前向留出期」的 `1 年` 行就被切掉过一半）；
  现在找不到会按秒重试，超时才回落并打印警告。

### 新增

- 版式自检脚本 `app/scripts/verify_layout.mjs`（需要真实栈在跑）：在真实浏览器里实测
  1440×900 与 390×844 两档无横向溢出（越界元素点名）、两栏铺满与窄屏单栏、左栏吸顶与
  发丝线、设计令牌生效、无装饰性渐变与发光、锚点可达、正文与次要文字对比度 ≥ 4.5:1。
  单元测试跑在 happy-dom 里、**没有排版引擎**，「整页横向滚动」这类问题它看不见。
- 三条闸门守卫：`src/__tests__/guards/forbiddenCopy.test.ts`（全部区块渲染后扫能力宣称禁用词）、
  `pageStructure.test.ts`（一个 h1 / skip link 目标存在 / 导航锚点可达 / 阅读顺序 / id 唯一 /
  tab 有 `aria-selected` / 按钮有可访问名 / 折叠不嵌套）、
  `designTokens.test.ts`（组件里不出现写死的十六进制色）。三条都做过变异验证（见本轮 spec 附录）。
- README 截图守卫 `backend/tests/unit/test_readme_screenshots.py`：两语言引用的每张图都真实存在、
  都写在**表格行**里，且「README 引用集合 == `capture_screenshots.mjs` 的 `SHOTS` == 目录里的文件」
  三方一致，导语里的张数一起守（做过变异验证：删一行 / 把图移出表格 / 改张数都会红）。

### 修复

- 启动引导的 `schema_migrations` 注册表改由 Core Table 生成 SQL：`key` 是 MySQL 保留字，
  手写裸 SQL 在 MySQL 上直接报 1064、自动迁移无法落地；SQLite 行为不变（真实 MySQL 实测通过）。
- 前端两处标签组的 tabpanel `id` 撞车（五个决策尺度与回测尺度共用 `tabpanel-${horizon}`），
  会让 `aria-controls` 指向错误的元素；`TabsNav` 现在要求调用方给 `panelId` 前缀。
- 窄屏整页横向滚动（实测 390px 视口下文档宽 1025px），三个原因逐个修掉：
  栅格 / 弹性容器的子项缺 `min-width: 0`（长段落与表格把轨道顶宽）、
  `.table-scroll` 自身缺 `min-width: 0`（「表内滚动」变成「整页滚动」）、
  图表没清掉浏览器给 `figure` 的默认外边距（`1em 40px`，单边就顶出 40px）。
- 截图脚本默认地址从 `127.0.0.1:5173` 改成 `localhost:5173`：Vite 开发服务器默认只监听
  `::1`（README 里的服务地址也是 localhost），写死 IPv4 会连不上、卡在「读不到 /health」。
- 机构观点表的机构标记不再被当成图片地址：接口的 `logo` 字段本来就是机构缩写
  （`GS` / `UBS` / `MS` / `C`），此前每格都挂一个碎图图标（README 的截图里肉眼可见）；
  现在按字标渲染，`InstitutionsPanel.test.ts` 加了守卫。
- 消息刷新接口的接口文档与 README 服务清单不再声称「不调用 LLM」：该刷新会触发一批中文翻译
  （一次 chat 调用、计入每日预算），文档改为如实描述 —— 抓取与评分是确定性的，翻译是唯一付费调用。

---

## [2.0.2] - 2026-10-03

### 新增

- **全自动运行：`backend/.env` 是唯一人工输入**。启动引导（`app/bootstrap.py`，挂在 FastAPI lifespan）自动建表、自动迁移、按覆盖度回填（价格 / 美元指数 / 新闻与消息板块 / 量化因子全历史，`QUANT_BACKFILL_YEARS` 默认 20 年、可断点续跑、修订流水一并回填）并在数据就绪后触发首轮分析；全程幂等、失败自动下轮重试，`/health.bootstrap` 暴露「第 N 步 / 共 M 步」与缺口（`AUTO_BOOTSTRAP` 默认 true）
- 自动迁移注册表 + `schema_migrations` 表：`migrate_quant` / `migrate_institution_views` / `migrate_news_digest_url` / `fix_enum_columns` 全部转为幂等自动迁移；SQLite 在 DDL 前自动备份到 `backend/backups/`，MySQL 只做加列 / 建表、不删数据
- LLM 配置热生效（`CONFIG_WATCH` 默认 true）：监听 `backend/.env`，LLM 相关键出现或变化时热重载设置、重置客户端缓存并**立即触发一轮分析**，无需重启；`DATABASE_URL` 等需重启的键在 `/health.config_watch` 明确提示
- 调度自愈与日常维护：启动即补跑错过的日期任务（不等 cron），所有任务开启 `coalesce` + `misfire_grace_time`；新增长期任务 —— 每日自动备份（SQLite 保留 7 份；MySQL 如实标注不代跑 mysqldump）与每日数据体检（只对安全项自动修复，先备份）（`AUTO_BACKUP` 默认 true）
- LLM 调用门控 `services/llm_gate.py`：输入指纹不变则跳过重算、复用缓存（显式强制刷新不受限）；新增 `LLM_DAILY_CALL_BUDGET`（默认 200/日，≤0 不设限），用尽后各块返回「暂不可用 + 原因」，绝不编内容
- `GET /api/gold/sources/status` 汇总各抓取通道的尝试流水与可用性；`/health` 增加 `bootstrap` 与 `config_watch` 字段
- 金价口径逐处标注（第 1 条）：每个价格附 `basis`（实时报价 / 日收盘 / 量化基准）、来源与 as-of；同一交易日的实时报价与收盘价偏差 > 3% 进体检点名
- 消息条目新增 `via_aggregator`（经聚合入口）与 `event_tags`（FOMC / CPI / NFP / 央行决议 / 央行购金确定性标注，注入分析 prompt、页面照实展示）
- 量化 `quant-v7`：因子新增 `publication_lag_days` 按**可观测时点**对齐（第 12 条）；250 日尺度停止发布方向（`direction_status: not_published` + 原因，只保留公允价值偏离与校准区间）；新增「相对永远看多的增量（含置信区间）」与「敢喊跌质量」一级指标、前向裁决 Beta 后验（先验写死 `Beta(1,1)`，与 CRPS 并排）、研究台 regime 与展期基准对照候选（只进研究台）、「高权威消息强度」派生序列（预注册候选 + 监测表第 22 行）
- 权重敏感性报告 `backend/scripts/weight_sensitivity.py`（第 6 条）：扰动权重后报告排序稳定性 / 符号翻转 / 逐因子杠杆，只报告不改线上权重，附归一化守卫；逐因子覆盖画像（首末观测、年计数、缺口年、「积累期」）(第 11 条)
- 上海黄金交易所 Au99.99 日线接入为 `sge_gold` 序列（第 3 条），「上海金溢价」从「不可用」转为实算；接入当日的源核验结论见本轮 spec（金十 / MINING / Kitco / FX168 不可达，如实记未落地）
- 可选 `REFRESH_TOKEN`（第 20 条）：设置后 POST refresh 必须带 `X-Refresh-Token` 请求头
- 数据体检入口 `scripts/check_data_sanity.py`：未来日期 / NaN 与 ±inf / 宽松数值域 / 跨库一致性一起报告；首跑点出长库 1 行未来日期（etf_shares 2026-10-05，已备份后清理）与 seasonality 两库 778 行分歧
- 消息板块的 13 个高权威源接入四类 LLM 分析：多空因子 / 机构观点 / 投资策略 / 市场总结共用一份「分析输入包」，新闻从「仅标题」升级为「标题 + 摘要（截断、去 HTML）」，来源、时间与链接一并进 prompt
- LLM 输出的确定性结构校验（`services/factor_validation.py`）：id 与标题去重、空项过滤、最多 5 条、正文数字 best-effort 引用核对；不合格时降级为空结构而不是原样透传
- 预测落库改为**追加式每日快照**：`(模型版本, 尺度, 截止日)` 一行，同天重算就地更新、跨天保留，可回看「当时说过什么」
- 回测新增 **CRPS**（分布级连续评分）及对「零漂移」基准的技能分，与 Brier 技能分并排展示在接口与研究页
- 研究页显著标注数据窗口（起止、交易日数、年数）：所有数字由当前库这个窗口现算，与 README / 历史报告引用的快照样本数不一致时以研究页为准
- 备份入口 `scripts/backup_db.py`：SQLite 用 backup API 全量复制并逐表校验行数；MySQL 只打印 `mysqldump` 指引，不代跑
- 研究台新增 M 族候选：多因子 walk-forward Ridge 直接建模（只吃已实现样本对，标准化在同一窗口内估计），与「先合成再一元回归」对照；候选定义仍只在 `scripts/quant_lab.py` 一处，**不进线上 service**
- LLM 端点合规守卫：`tp-` key + token-plan 端点组合在构造时警告一次（不含密钥内容）并给出切换指引，`/health` 透传 `token_plan_backend` 字段

### 变更

- 双库对齐进启动引导（第 14 条）：服务库为准覆盖长库、长库独有日期只补不删；存量 10902 行分歧（GPR 整条序列错位一天 + 冷启动测试落进长库的 5 行假数据）清零，`check_data_sanity --strict` 由失败转为通过
- 运维脚本降级为可选：`init_db.py` / `backfill_quant.py` / `migrate_*.py` / `backup_db.py` / `check_data_sanity.py` 保留原样，但「不使用也不会缺任何功能」；Docker 入口改为「等库 → 直接起 uvicorn」，裸机路径就是 `uvicorn app.main:app`
- 快速开始改为「填 `backend/.env` → 启动 → 完成」，README 中英同步
- 研究页与看板把方向增量 KPI、Beta 后验、监测行分组（参与信号 / 只看不评）摆到一级位置
- 四个 LLM 分析服务改为消费同一份「分析输入包」：同窗口、同价格上下文、同技能声明，消除各服务各拉数据的口径漂移
- 量化页把未校准的「因子偏向」与同步报告的「未到期」噪音从主表折进详情：偏向收进折叠说明，逐源状态收进折叠的「数据源状态」区，主版面只留结论与可行动信息
- 看板轮询从 10 秒放宽到 30 秒，标签页隐藏时暂停、恢复可见立即补一次（空闲请求量约 30 次/分 → 约 8 次/分）

### 变更（破坏性）

- `/news` 响应移除死字段 `sentiment`，删除情感汇总端点 `/api/gold/news/sentiment/summary`（DB 列留存历史数据、过滤参数保留；页面不再展示情感结论）
- 量化模型版本 `quant-v6 → quant-v7`：发布滞后修正 + 250 日方向策略落地，前向窗口按新封板日 2026-10-03 重启（旧 `quant-v6` 记录保留在库中、按版本号可查；v6 的前向注单不再计入裁决）

### 修复

- LLM 输出撞上单点输出上限（`finish_reason=length`）时不再直接整块降级：`invoke_with_retries` 用「压缩提示」重试一次（数组条目变少、字段变短），仍截断才如实返回「暂不可用」，绝不拼接残缺 JSON。首次真实冷启动实测：投资策略的四档策略 schema 撞上 8192 输出上限、整块降级为空，重试后产出完整三档策略
- 启动引导的市场总结不再每次启动强制重算（`force` 透传，输入指纹不变就不重复计费）；新增第 7 步「回填后再次对齐本地研究长库」，一次启动就收敛两库，且首次对齐导入长库历史避免重复联网回填
- 长库 GPR 序列缺少发布滞后右移、整条错位一天（第 12 条的存量后果），以及冷启动测试曾写进长库的假数据 —— 由启动引导的双库对齐修复，实测跨库不一致 10902 行 → 0 行
- 引导回填期间页面显示「初始化中（第 N 步 / 共 M 步）」并给出缺口，而不是「不可用」；LLM 未配置时数据层照常运行，配置出现后自动补齐，不需要点任何「重新分析」
- 投资建议的统计窗口随日历滚动（去掉写死的 `datetime(2025,1,1)`）；「波动区间」正名为「高低振幅」并写明定义，prompt 同步
- `etf_shares` 拒绝写入晚于今天的观测日（存储层守卫 + 源层修复），页面上不再出现未来日期
- 机构观点的 news_scan 总结改为由结构化行**确定性拼装**，LLM 总结不再与结构化数据互相矛盾
- 市场总结在机构数据缺失时不再输出机构判断（确定性清洗 + prompt 加固）
- 投资建议在无因子 / 无机构 / 无新闻时不调 LLM：只给行情统计与「数据不足」说明，前端如实标注 `insufficient_data`
- 测试库护栏：`GOLDMIND_TEST_DATABASE_URL` 指向的库名必须含 `test`，否则测试在导入期拒跑（2026-10-02 事故：误连开发库，`drop_all` 删光 9 张业务表）
- 缺库/缺表时接口返回 **503 + `python init_db.py` 修复指引**（原先裸 500），启动时做 schema 自检并在缺表时打 ERROR；其余 SQL 错误仍是 500
- 外部行情源（Yahoo 限流/不可用）时，量化引擎改用本地已同步的 `gold_prices` / `dollar_index` 兜底基准价与美元因子，来源如实标注；不再整片「缺少黄金价格序列」
- 前端对 **429 / 5xx / 网络错误**做指数退避重试（429 尊重 `Retry-After`，最多 3 次尝试）；同一 URL 的在飞 GET 合并为一个请求；`POST` 与 `?refresh=true` 永不重试
- 真实栈验收实测投资建议接口 500：模型截断重试后的输出漏吐 `disclaimer`，缓存命中时一直缺该契约键、响应模型校验失败。分析解析出口、实时出口与缓存读出口现在都把缺失的契约键补齐成空值（`core_principles=[]`、`disclaimer=""` 等），只做形状归一、不编内容；只有解析出真内容的轮次才记输入指纹，空结构仍按下轮重试

### 文档

- README 中英：2.0.2 发布横幅 / 徽章 / 新截图、快速开始改为「填 `.env` → 启动」、新增「全自动运行」节、金价三口径与监测表第 22 行的说明
- `docs/ARCHITECTURE.md` 新增「自动化运行」一节（引导阶段、迁移注册、热生效、调度自愈与备份）；`docs/API.md` 与 `docs/en/api.md` 由路由表重新生成
- 新增本轮 spec / plan（`docs/specs/2026-10-03-2.0.2-整改与自动化.md` 及其 `-plan`）、权重敏感性报告（`docs/specs/2026-10-03-权重敏感性报告.md`）与零人工冷启动验收报告（`docs/specs/2026-10-03-零人工冷启动验收.md`）
- `docs/10-密钥与隐私.md` 补齐 `AUTO_BOOTSTRAP` / `QUANT_BACKFILL_YEARS` / `AUTO_BACKUP` / `CONFIG_WATCH` / `REFRESH_TOKEN` / `LLM_DAILY_CALL_BUDGET` 六个新配置键

---

## [2.0.1] - 2026-10-02

### 新增

- 因子闸门与筛选工具 `backend/scripts/screen_factors.py`：去均值协方差 + Newey–West HAC + Bonferroni + |t| ≥ 3、跨尺度同号、前向窗口确认；26 年面板 255 格无一过线，17 个候选在修好引擎后彼此不可区分 —— 这条阴性结果是本轮把预算指向新信息源的依据
- 监测仪表盘扩到 **21 行**：新增 GVZ / 金银比 / 铜金比 / CFTC 净多头占未平仓比 / GPR 五条信息行，一律不给多空方向；库里 0 行时显示「不可用 + 原因」而不是从表上消失
- 因子观测改为「当前值 + 追加式修订流水」双表，支持 `--as-of` 按时点重建面板；老库升级自动回填 10 年流水
- 评测新口径：按 stride=h 抽取的独立下注数（250 日留出期 506 个重叠样本实际只有 2 次下注）、逐因子 HAC t 与 iid 对照、按已实现波动率分档的覆盖率审计、「反向显著」只登记不采纳的出口
- 第三道前向窗口闸门落地为代码：窗口起点写死 2026-10-02，判不了时报 pending 并列出还差多少个交易日
- 通用 LLM 接入：任何 OpenAI 兼容端点都行，配置面是 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`（三项齐备才算已配置），`LLM_PROVIDER` 仅作界面展示标签
- 新增 `LLM_MAX_TOKENS`（默认 `8192`）、`LLM_SEARCH_ENABLED`（默认 `false`）、`LLM_SEARCH_MODEL` / `LLM_SEARCH_BASE_URL` / `LLM_SEARCH_API_KEY` 与 `LLM_SEARCH_MAX_KEYWORD`
- 量化研究台与预注册：候选清单、选择规则与通过线的唯一实现 `backend/app/services/quant/preregistered.py`，全档评估工具 `backend/scripts/quant_lab.py`，接口 `GET /api/gold/quant/research`，独立「研究」页 `app/research.html`
- 量化统计工具箱 `backend/app/services/quant/stats.py`：Newey–West HAC 标准误、圆周分块自助区间、HAC t / Diebold–Mariano、Brier 技能分与可靠性分桶（重叠样本不再按独立样本处理）
- 20 年因子历史回填（新增 36,150 行 / 修订 26,445 行，见 `docs/specs/2026-10-02-回填报告.md`），为留出期评估补齐数据

### 变更

- 模型版本 `quant-v5`：方向、上行概率、80% 区间与三情景统一到同一张校准分布 F̂（区间宽度取 F̂ 的经验分位，不再被 uncertainty 二次放大）；方向判定退回校准后 μ 的符号（实测优于分布中位数）
- 四层公允价分解不再外推：目标价超出 6 个 σ 或 12 个 log 溢价时单列 `unsupported_by` 并拒绝给数
- 陈旧因子在合成阶段即变 NaN，不再向前填充成假水位；样本不足的尺度如实标「不可判定」而非「未通过」，每条落库预测自带该尺度实测技能状态
- 监测仪表盘逐行判新鲜度：超龄行只给数值与观测日，不再给多空标签
- 预注册候选 C2（每注校准 + 窗口）以 60 日 0.7679 未跨 0.78 通过线被淘汰，阈值不动；控制候选 C0 与 B0 逐值相同
- **默认数据库改为 SQLite 单文件**（`backend/goldmind.db`，零安装、零配置）：`init_db.py` 在 SQLite 下用模型 `create_all` 建表，`seed_data.py` 去掉 pymysql 直连；MySQL 降级为可选路径（未随本轮闸门实测）
- 量化评估改为**预注册**口径：候选清单与通过线先写死，再看留出期（2023-10-02 起）；修好引擎口径后重裁，17 个候选 × 5 个尺度彼此不可区分，26 年面板 255 格无一过闸门，研究页如实标注「无统计优势」

### 变更（破坏性）

- **LLM 配置改名：`MIMO_*` → `LLM_*`，不留兼容回退。** 升级时必须把 `backend/.env` 与部署环境里的 `MIMO_API_KEY` / `MIMO_BASE_URL` / `MIMO_MODEL` / `MIMO_SEARCH_MODEL` / `MIMO_SEARCH_MAX_KEYWORD` / `MIMO_TRUST_ENV` 换成 `LLM_*` 对应项

### 修复

- **ACI 区间覆盖错位**：α 更新曾拿「当前行的区间」判「h 天前发出的那一注」，修后开发期 20 日覆盖率 76.7%→79.3%、60 日 72.6%→73.6%
- 拒收任何观测日期晚于「今天」的记录；前端监测表不再把 <0.01 的比值四舍五入成 0.00
- **投资策略长期显示「暂不可用」**：5 个分析服务硬编码 `max_tokens=4096`，三档策略的完整 JSON 被截断；改为取 `LLM_MAX_TOKENS`（默认 8192），解析失败时日志记录 `finish_reason` 与 token 用量
- 端点返回 `finish_reason=content_filter` 时自动重试一次；新闻提示词默认上限收到 10 条
- 冒烟脚本更名 `backend/scripts/smoke_llm.py`（原 `smoke_mimo.py`），联网搜索只在 `LLM_SEARCH_ENABLED=true` 时探测

### 文档

- `README.md` / `README_EN.md` 全量重写：十节量化策略（含 21 行监测表、预注册裁决与已知限制）、逐项实测的快速开始与命令、14 张 2026-10-02 从真实栈截取的截图（脚本拒绝写空图）
- 新增漂移守卫：架构文档声明、README 监测表 vs `monitor.ROW_SPECS`、README 命令 vs 各脚本真实 `--help`（均做过变异验证）
- README 修复复现缺口：Node 下限改为 ≥22.22.2（或 24.15+/26+）、补 Google Chrome 前置、删除并不存在的 `.\start_all.ps1`、补冷启动预期
- 报头 / 走势 / 多空 / 机构 / 策略 / 总结截图全部重截；机构观点如实保留「暂无最新预测」空态，文档写明精确报错文案
- README 中英双版同步到 SQLite 零配置快速开始；量化第六节换成留出期实测覆盖率与方向命中率，新增「研究台与预注册」一节，已知限制改为留出期口径
- `docs/ARCHITECTURE.md`（含英文镜像）改为默认 SQLite 的部署与配置口径，第十一节补统计、预注册与研究台；`docs/00-产品方向.md`（含英文镜像）的存储口径改为 SQLite 默认

## [2.0.0] - 2026-10-01

2.0 的主线是**可核实**：预测收敛到一份可回测的分布，机构观点不再因为「当天没有新研报」
就抹掉真实数据，文档中英双版且接口文档由代码生成。

### 新增

- 量化预测引擎：14 个因子覆盖四类影响因素（货币政策与利率 / 避险与信用 / 供需结构 / 市场与技术面），数据源全部免费且免密钥
- 因子按源节流增量同步（6h～24h）并落库，`factor_observations` 对 `(factor_key, obs_date)` 建唯一约束，重复抓取幂等
- 五个预测尺度各有独立权重：短尺度由资金流与技术面主导，中尺度由政策预期与美元主导，长尺度由央行购金与需求结构主导
- 单一校准分布（模型版本 `quant-v4`）：方向 = sign(μ)、上行概率 = Φ(μ/σ)、目标价 = 基准价×(1+μ)、80% 区间 = μ±1.2816σ、三情景 = N(μ, σ²) 的分位数
- 区间宽度按走查预测误差的**经验分位**校准（正态分位在长尺度系统性偏窄）；已实现误差不足 60 组时退回扩展标准差
- 公允价四层分解：宏观锚 ＋ 需求溢价 ＋ 风险溢价 ＋ 情绪残差，偏离度 = 市场价 / 公允价 − 1
- 三情景各自带**触发条件**与**失效条件**（由该尺度最重因子与 200 日均线生成，可逐条核对）
- 走查式回测：命中率与「永远看多 / 动量 / 抛硬币」三个基准并排，另报 80% 名义区间的实际覆盖率、2022-01-01 前后分段、逐因子命中率与 IC
- 监测仪表盘：16 行水位表，每行给频率、来源、当前值、信号（看涨 / 看跌 / 中性 / 信息）与数据截至日
- 前端新增量化预测区块：五尺度 tab、公允价值分解、监测仪表盘、回测命中率、四类因子表
- 新增接口 `GET /api/gold/quant/factors|predictions|accuracy|monitor` 与 `POST /api/gold/quant/refresh`
- 新增迁移脚本 `backend/scripts/migrate_quant.py`（幂等，只加不删，带回滚）
- 新增迁移脚本 `backend/scripts/migrate_institution_views.py`（默认 dry-run，`--apply` 执行，`--drop-columns` 回滚，**不删除任何行**）

### 变更

- 机构观点改为「每家机构**最近一次可核实**的预测」：扫描窗口 `INSTITUTION_NEWS_LOOKBACK_DAYS`（默认 30 天），不再要求新闻在过去 24 小时内发布
- 机构观点表新增「预测日期」与「来源」两列，预测日期超过 30 天标注「已滞后 N 天」
- 机构名称规范化到四家规范行（高盛 / 瑞银 / 摩根士丹利 / 花旗），写入、读取、提示词与测试全部由同一份机构注册表派生
- 机构观点读取不再设「2 小时内才读库」门槛，直接按规范行组装；窗口内没有新预测时由服务端给出确定性说明
- 前端表现层重构为浅色研究简报：设计令牌化、数字表格化、红涨绿跌且方向同时给符号与文字，六节一律左对齐、无渐变无阴影
- 文档全面双版：README、用户文档、API 文档都有英文镜像；`docs/API.md` 与 `docs/en/api.md` 改由 `backend/scripts/gen_api_doc.py` 从路由表生成

### 修复

- **不再用空目标价覆盖已有真实预测** —— 2026-10-01 06:01 被「暂无」覆盖掉的四条机构目标价（5400 / 5000 / 6300 / 6000）已从旧别名行恢复到规范行
- 四条 `target_price` 全为 null 的占位缓存不再遮蔽数据库里的真实数据（旧判据只检查「列表非空」）
- 分析服务不再返回编造的兜底因子 / 策略：数据源或联网搜索不可用时如实返回「不可用 + 原因」
- 前端删除了各区块内置的写死兜底数据，并由测试钉住「失败时不得出现内置文案」
- 设置对象自身也做密钥掩码，避免密钥经日志或错误信息外泄

### 文档

- 重写 `README.md` 并新增 `README_EN.md`，含 2.0 发布横幅与专章《量化策略》
- 新增 `docs/en/`：`product-direction.md`、`secrets-and-privacy.md`、`frontend-design.md`、`architecture.md`、`api.md`
- 新增 `CONTRIBUTING_EN.md` 与本文件、`CHANGELOG_EN.md`

---

## [1.0.0] - 2026-02-03

首个公开版本。

### 新增

- 金价与美元指数采集（腾讯财经实时金价、新浪财经 ICE 美元指数），历史数据回填支持新浪 / 东方财富 / Yahoo 三源
- MySQL 8 持久化（`gold_prices` / `dollar_index` / `news` / `institution_views` / `predictions`）
- 四个 LLM 分析服务：看涨因子、看跌因子、机构观点、投资建议，外加市场总结
- React 单页看板：行情 / 多空对照 / 机构观点 / 投资策略 / 总结
- 内存 + JSON 文件两级缓存，支持多进程与重启后共享
- APScheduler 定时刷新，Docker Compose 一键部署

[2.0.3]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.3
[2.0.2]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.2
[2.0.1]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.1
[2.0.0]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.0
[1.0.0]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v1.0.0
