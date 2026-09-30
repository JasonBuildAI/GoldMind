import { expect, test, type Page } from '@playwright/test'

/**
 * 浏览器级端到端测试。
 *
 * 覆盖的是真实链路：浏览器 → vite preview 的 /api 代理 → uvicorn → SQLite，
 * 以及 → 假 LLM 服务（模拟 OpenAI 协议）。
 *
 * 因此这里断言的都是「只有整条链路都通才可能成立」的事实，
 * 而不是可以用 mock 轻易伪造的界面文案。
 */

/**
 * 精确定位「看涨因子」区块。
 *
 * 不能用 `locator('section', { hasText: ... })`：hasText 会命中所有祖先，
 * 而「投资建议」「市场总结」区块里也有同名刷新按钮，会造成 strict mode 冲突；
 * 靠 heading 做 DOM 遍历又依赖组件内部分层。组件上挂了稳定的 testid，
 * 直接用它最可靠。
 */
function bullishSection(page: Page) {
  return page.getByTestId('bullish-factors')
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

  test('健康检查经代理可达，且上报 MiMo', async ({ request }) => {
    const resp = await request.get('/health')
    expect(resp.ok()).toBeTruthy()

    const body = await resp.json()
    expect(body.services.database.status).toBe('connected')
    expect(body.services.ai_config.provider).toBe('mimo')
  })

  test('首屏渲染，且没有未捕获的前端异常', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (err) => errors.push(err.message))

    await page.goto('/')

    await expect(page.getByRole('heading', { level: 1, name: /GoldMind/ })).toBeVisible()
    // 报头的五个锚点全部可达 —— 少一个都会让某一节失去入口
    for (const label of ['行情', '多空', '机构', '策略', '总结']) {
      await expect(page.getByRole('link', { name: label })).toBeVisible()
    }
    // 两条报价都在首屏：纽约黄金与美元指数
    await expect(page.getByText('纽约黄金', { exact: true })).toBeVisible()
    await expect(page.getByText('美元指数', { exact: true })).toBeVisible()

    expect(errors).toEqual([])
  })

  test('点击刷新后，页面渲染出来自 LLM 的分析结果', async ({ page }) => {
    await page.goto('/')

    const section = bullishSection(page)

    // 初始没有缓存时，后端返回**空内容 + status=analyzing**，页面显示「正在分析中」。
    // 它不会先摆一份内置因子：编造的结论与真实分析长得一样，用户分不出来。
    await expect(section.getByText('看涨因素正在分析中')).toBeVisible()

    // 触发一次真实分析：前端 → 后端 → 假 LLM → 解析 → 缓存 → 渲染
    await section.getByRole('button', { name: '重新分析' }).click()

    await expect(section.getByText('端到端看涨因子').first()).toBeVisible({ timeout: 30_000 })
    // 「正在分析中」应当已被真实结果替换
    await expect(section.getByText('看涨因素正在分析中')).toHaveCount(0)
  })

  test('刷新后重新加载页面，命中缓存而不是回退默认值', async ({ page }) => {
    await page.goto('/')

    await bullishSection(page).getByRole('button', { name: '重新分析' }).click()
    await expect(bullishSection(page).getByText('端到端看涨因子').first()).toBeVisible({
      timeout: 30_000,
    })

    // 重新加载：这次走缓存路径，仍应显示同一份分析
    await page.reload()
    await expect(bullishSection(page).getByText('端到端看涨因子').first()).toBeVisible({
      timeout: 30_000,
    })
  })

  test('全页可见文本不出现未实现的能力宣称', async ({ page }) => {
    // 界面曾把「多 Agent 协作 / ReAct / RAG / 智能驱动」写成既有能力，
    // 而实现是单轮 LLM 调用（见 docs/00-产品方向.md 第三节）。
    // 这不是文案偏好：那些词等于替系统编造能力，违反项目红线。
    await page.goto('/')

    // 先把五个区块都填上内容再扫描 —— 空白页扫不出什么，
    // 真正会漏的是「有数据之后」才渲染出来的那些行。
    await page.getByTestId('bullish-factors').getByRole('button', { name: '重新分析' }).click()
    await page.getByTestId('bearish-factors').getByRole('button', { name: '重新分析' }).click()
    await page.getByRole('button', { name: '重新抓取' }).click()
    await page.locator('#strategy').getByRole('button', { name: '重新分析' }).click()
    await page.locator('#conclusion').getByRole('button', { name: '重新分析' }).click()

    await expect(page.getByText('端到端看涨因子').first()).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText('端到端市场共识').first()).toBeVisible({ timeout: 30_000 })

    const text = await page.locator('body').innerText()
    expect(text).not.toMatch(/Agent|ReAct|RAG|多智能体|智能驱动/i)
  })
})
