import { expect, test, type Locator, type Page } from '@playwright/test'

import { fieldTestId, TESTIDS } from '../src/testids'

/**
 * 浏览器级端到端测试。默认档（不设 E2E_LLM）全程离线：
 * 浏览器 → vite preview 的 /api 代理 → uvicorn（SQLite 种子库）→ 假 LLM 服务。
 *
 * 因此这里断言的都是「只有整条链路都通才可能成立」的事实，
 * 而不是可以用 mock 轻易伪造的界面文案。选择器一律从 src/testids.ts 取，
 * 与组件、截图脚本共用同一份契约。
 *
 * 用例顺序有硬约束：E2E 关掉了后端启动预热（SCHEDULER_ENABLED=false），
 * 「无缓存 → 正在分析中」只可能出现在**整个会话的第一次页面加载**。
 * 那条断言必须排在所有 page.goto 之前 —— 它曾经排在第 5 位，
 * 前面的用例先加载页面把分析跑完、缓存变热，CI 上这条断言随机失败。
 *
 * 真栈验证（真实 LLM 与真实数据）见 e2e-live/，用 E2E_LLM=real 触发。
 */

const NAV_LABELS = ['今日结论', '行情', '驱动', '消息', '量化预测', '投资策略', '数据与方法', '研究']

/** 精确定位「看涨因素」区块：区块内自己也有刷新按钮，必须限定范围（strict mode）。 */
function bullishSection(page: Page) {
  return page.getByTestId(TESTIDS.bullishFactors)
}

/**
 * 逐条因子在 Vue 版里**每条自己就是一个折叠**（可读性规范：细节最多一层折叠；
 * 原来「展开逐条因子」的外层折叠会把因子折叠套成两层）。因此这里不再需要
 * 先展开外层 —— 直接断言折叠里的内容即可，同时顺带证明这一层打得开。
 */
async function expandFactors(section: Locator) {
  const first = section.locator('.factor details').first()
  await first.locator('summary').click()
  await expect(first).toHaveAttribute('open', '')
}

test.describe('GoldMind 看板端到端', () => {
  test('浏览器经代理访问后端，拿到种子数据', async ({ request }) => {
    const resp = await request.get('/api/gold/prices/daily')
    expect(resp.ok()).toBeTruthy()

    const daily = await resp.json()
    // 种子数据：2025-01-02 起，2600 起步、每步 +10
    expect(daily.length).toBeGreaterThanOrEqual(10)
    expect(daily[0].date).toBe('2025-01-02')
    expect(daily[0].price).toBe(2600)
    // 第 10 个交易日（索引 9）收盘 2690
    expect(daily[9].price).toBe(2690)
  })

  test('新闻接口返回种子新闻', async ({ request }) => {
    const resp = await request.get('/api/gold/news')
    expect(resp.ok()).toBeTruthy()

    const news = await resp.json()
    expect(news).toHaveLength(3)
    expect(news[0].title).toContain('端到端新闻')
  })

  test('健康检查经代理可达，且上报 LLM、初始化进度与配置热加载', async ({ request }) => {
    const resp = await request.get('/health')
    expect(resp.ok()).toBeTruthy()

    const body = await resp.json()
    expect(body.services.database.status).toBe('connected')
    // 与 playwright.config.ts 注入的 LLM_PROVIDER 保持一致
    expect(body.services.ai_config.provider).toBe('e2e')
    expect(body.services.ai_config.model).toBe('e2e-mock-model')

    // 2.0.2：bootstrap 与 config_watch 是「数据与方法」节的直接数据源，
    // 字段缺失会让页面只能显示降级说明，这里先把契约钉住。
    expect(body.bootstrap).toBeTruthy()
    expect(['pending', 'running', 'done', 'failed', 'disabled', 'skipped']).toContain(
      body.bootstrap.status,
    )
    expect(typeof body.bootstrap.ready).toBe('boolean')
    expect(typeof body.bootstrap.step.index).toBe('number')
    expect(typeof body.bootstrap.step.total).toBe('number')
    expect(Array.isArray(body.bootstrap.phases)).toBeTruthy()
    expect(body.bootstrap.gaps).toBeTruthy()

    expect(body.config_watch).toBeTruthy()
    expect(body.config_watch.env_file).toBeTruthy()
    expect(Array.isArray(body.config_watch.reloaded_keys)).toBeTruthy()
  })

  test('无缓存首屏显示「正在分析中」，点击刷新后渲染 LLM 结果', async ({ page }) => {
    // 必须第一个加载页面：此前没有任何请求触发过因子分析，缓存必定为空。
    await page.goto('/')

    const section = bullishSection(page)

    // 初始没有缓存时，后端返回**空内容 + status=analyzing**，页面显示「正在分析中」。
    // 它不会先摆一份内置因子：编造的结论与真实分析长得一样，用户分不出来。
    await expect(section.getByText('看涨因素正在分析中')).toBeVisible()

    // 触发一次真实分析：前端 → 后端 → 假 LLM → 解析 → 缓存 → 渲染
    await section.getByRole('button', { name: '重新分析' }).click()

    // 折叠层外的一行结论先出现，证明链路通了
    await expect(section.getByTestId(fieldTestId('bullish.analysis_summary'))).toContainText(
      '看涨总结',
      { timeout: 30_000 },
    )
    // 再展开逐条因子，核对假 LLM 产出的因子标题真的渲染出来了
    await expandFactors(section)
    await expect(section.getByText('端到端看涨因子').first()).toBeVisible()
    // 「正在分析中」应当已被真实结果替换
    await expect(section.getByText('看涨因素正在分析中')).toHaveCount(0)
  })

  test('首屏按阅读顺序渲染：报头 → 今日速览 → 新鲜度条 → 各节 → 页脚', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (err) => errors.push(err.message))

    await page.goto('/')

    await expect(page.getByRole('heading', { level: 1, name: 'GoldMind' })).toBeVisible()

    // 报头的每个锚点全部可达 —— 少一个都会让某一节失去入口
    for (const label of NAV_LABELS) {
      await expect(page.getByRole('link', { name: label, exact: true })).toBeVisible()
    }

    // 今日速览 + 数据新鲜度条：状态与逐块时间都必须有落点
    await expect(page.getByTestId(TESTIDS.todaySummary)).toContainText('今日速览')
    await expect(page.getByTestId(TESTIDS.freshnessBar)).toContainText('数据新鲜度')
    await expect(page.getByTestId(TESTIDS.freshnessState)).not.toBeEmpty()
    await expect(page.getByTestId(`${TESTIDS.freshnessItemPrefix}market`)).toBeVisible()

    // 两条报价都在首屏：纽约黄金与美元指数。
    // 「美元指数」在报头、新鲜度条、口径表与页脚都会出现，必须限定在行情区块内（strict mode）。
    const market = page.locator(`#${TESTIDS.sectionMarket}`)
    await expect(market.getByRole('heading', { name: '纽约黄金', exact: true })).toBeVisible()
    await expect(market.getByRole('heading', { name: '美元指数', exact: true })).toBeVisible()

    // 自上而下的阅读顺序：今日结论 → 行情 → 驱动 → 消息 → 量化预测 → 投资策略 → 数据与方法
    for (const id of [
      TESTIDS.sectionConclusion,
      TESTIDS.sectionMarket,
      TESTIDS.sectionDrivers,
      TESTIDS.sectionMessages,
      TESTIDS.sectionQuant,
      TESTIDS.sectionStrategy,
      TESTIDS.sectionData,
    ]) {
      await expect(page.locator(`#${id}`)).toBeVisible()
    }

    // 页脚统一免责声明
    await expect(page.getByRole('contentinfo')).toContainText('不构成投资建议')

    expect(errors).toEqual([])
  })

  test('刷新后重新加载页面，命中缓存而不是回退默认值', async ({ page }) => {
    await page.goto('/')

    await bullishSection(page).getByRole('button', { name: '重新分析' }).click()
    await expect(
      bullishSection(page).getByTestId(fieldTestId('bullish.analysis_summary')),
    ).toContainText('看涨总结', { timeout: 30_000 })

    // 重新加载：这次走缓存路径，仍应显示同一份分析
    await page.reload()
    const section = bullishSection(page)
    await expect(section.getByTestId(fieldTestId('bullish.analysis_summary'))).toContainText(
      '看涨总结',
      { timeout: 30_000 },
    )
    await expandFactors(section)
    await expect(section.getByText('端到端看涨因子').first()).toBeVisible({ timeout: 30_000 })
  })

  test('消息板块展示种子消息，展开可见评分依据与同题报道', async ({ page }) => {
    await page.goto('/')

    const section = page.getByTestId(TESTIDS.driversMessages)

    // 同题报道的代表条取簇内重要性最高者：1.2 小时前的美联社那条。
    // `.first()`：英文原题现在出现两次（折叠态那行小字 + 展开区的「英文原题」），
    // 这里要的是**不展开就能看到**的那一处。
    await expect(
      section.getByText('Gold hits record high on central bank demand').first(),
    ).toBeVisible()

    // 原文链接新窗口打开，且指向真实种子 URL
    const original = section.getByRole('link', {
      name: /原文：Gold hits record high on central bank demand/,
    })
    await expect(original).toHaveAttribute('target', '_blank')
    await expect(original).toHaveAttribute('href', 'https://example.invalid/e2e/digest/1')

    // 展开详情：摘要 + 评分依据 + 同题报道（另一家来源的链接）
    await section.getByText('展开详情').first().click()
    await expect(section.getByText(/端到端消息摘要/).first()).toBeVisible()
    await expect(section.getByText(/家来源/).first()).toBeVisible()
    await expect(
      section.getByRole('link', { name: 'Gold hits record high on central bank buying' }),
    ).toBeVisible()

    // 26 小时前的消息不在 24 小时窗口，切到 7 天窗口才出现
    await expect(section.getByText('Gold steadies ahead of US payrolls data')).toHaveCount(0)
    await section.getByRole('tab', { name: '7 天内' }).click()
    await expect(section.getByText('Gold steadies ahead of US payrolls data')).toBeVisible()
  })

  test('中文化：折叠态就能读到中文标题与导语，未翻译的那条如实说明原因', async ({ page }) => {
    await page.goto('/')

    const section = page.getByTestId(TESTIDS.driversMessages)

    // 折叠态（没有点任何「展开详情」）就该看到中文：读者不必逐条展开
    await expect(section.getByTestId(fieldTestId('digest.items.title_zh')).first()).toHaveText(
      '端到端中文标题 1',
    )
    await expect(section.getByTestId(fieldTestId('digest.items.brief_zh')).first()).toBeVisible()
    await expect(section.getByText('端到端中文导语 1')).toBeVisible()
    // AI 产出必须带标注
    await expect(section.getByTestId(fieldTestId('digest.items.translated')).first()).toBeVisible()

    // 中文是叠加：英文原题仍在同一条卡片上
    await expect(
      section.getByTestId(fieldTestId('digest.items.title')).first(),
    ).toContainText('Gold hits record high on central bank demand')

    // 翻译状态一行说清开关、模型与待翻译条数
    await expect(section.getByTestId(fieldTestId('digest.translation.model'))).toBeVisible()
    await expect(section.getByTestId(fieldTestId('digest.translation.pending'))).toContainText(
      '待翻译 1 条',
    )

    // 未翻译的那条（26 小时前，只在 7 天窗口）：英文标题 + 为什么没有中文，绝不留空
    await section.getByRole('tab', { name: '7 天内' }).click()
    // 按标题定位而不是按 id：种子库的 id 由自增分配，钉死数字等于把测试耦合到插入顺序
    const untranslated = section
      .locator('li[data-testid^="message-"]')
      .filter({ hasText: 'Gold steadies ahead of US payrolls data' })
    await expect(untranslated).toContainText('Gold steadies ahead of US payrolls data')
    await expect(untranslated).toContainText('中文翻译暂不可用')
  })

  test('数据与方法节按 /health 原样展示初始化进度与配置热加载', async ({ page, request }) => {
    const health = await (await request.get('/health')).json()

    await page.goto('/')

    const section = page.locator(`#${TESTIDS.sectionData}`)
    await expect(section).toBeVisible()

    // 数据源可用性表（GET /api/gold/sources/status）
    await expect(section.getByTestId(TESTIDS.dataSourcesStatus)).toBeVisible()
    // 同步报告（来自因子接口的 sync 字段）
    await expect(section.getByTestId(TESTIDS.dataSync)).toBeVisible()
    // 初始化进度：状态词与 /health 完全一致，不美化
    const bootstrap = section.getByTestId(TESTIDS.dataBootstrap)
    await expect(bootstrap).toBeVisible()
    await expect(bootstrap).toContainText(String(health.bootstrap.status))
    // 口径说明/图例
    await expect(section.getByTestId(TESTIDS.dataLegend)).toBeVisible()

    // 配置热加载：文件名来自 /health，不展示任何密钥值
    const watch = section.getByTestId(TESTIDS.dataConfigWatch)
    await expect(watch).toBeVisible()
    await expect(watch.getByTestId(fieldTestId('health.config_watch.env_file'))).toContainText(
      health.config_watch.env_file,
    )
  })

  test('全页可见文本不出现未实现的能力宣称', async ({ page }) => {
    // 界面曾把「多 Agent 协作 / ReAct / RAG / 智能驱动」写成既有能力，
    // 而实现是单轮 LLM 调用（见 docs/00-产品方向.md 第三节）。
    // 这不是文案偏好：那些词等于替系统编造能力，违反项目红线。
    await page.goto('/')

    // 先把各区块都填上内容再扫描 —— 空白页扫不出什么，
    // 真正会漏的是「有数据之后」才渲染出来的那些行。
    // 「重新抓取」在机构观点与量化预测各有一个，选择器必须限定区块（strict mode）。
    await page.getByTestId(TESTIDS.bullishFactors).getByRole('button', { name: '重新分析' }).click()
    await page.getByTestId(TESTIDS.bearishFactors).getByRole('button', { name: '重新分析' }).click()
    await page
      .getByTestId(TESTIDS.driversInstitutions)
      .getByRole('button', { name: '重新抓取' })
      .click()
    await page.locator(`#${TESTIDS.sectionStrategy}`).getByRole('button', { name: '重新分析' }).click()
    await page
      .locator(`#${TESTIDS.sectionConclusion}`)
      .getByRole('button', { name: '重新分析' })
      .click()

    // 今日结论的一行核心观点在折叠层外，先等它出现
    await expect(page.getByTestId(fieldTestId('summary.core_view'))).toContainText(
      '端到端核心观点',
      { timeout: 30_000 },
    )
    // 展开今日结论与看涨因子的折叠层，让 LLM 产出的要点也进入可见文本再扫描
    await page.getByTestId(TESTIDS.conclusionDetails).locator('summary').click()
    await expect(page.getByText('端到端市场共识').first()).toBeVisible({ timeout: 30_000 })
    await expect(
      page.getByTestId(TESTIDS.bullishFactors).getByTestId(fieldTestId('bullish.analysis_summary')),
    ).toContainText('看涨总结', { timeout: 30_000 })
    await expandFactors(page.getByTestId(TESTIDS.bullishFactors))
    await expect(page.getByText('端到端看涨因子').first()).toBeVisible({ timeout: 30_000 })

    const text = await page.locator('body').innerText()
    // 用词边界匹配：coverage / storage / average 里都含 "rag"，
    // 不设边界会把「覆盖度」的代号 coverage 误判成能力宣称（第一次跑就撞上了）。
    expect(text).not.toMatch(/\bAgent\b|\bReAct\b|\bRAG\b|多智能体|智能驱动/i)
  })
})