import { expect, test, type Locator, type Page } from '@playwright/test'

import { fieldTestId, TESTIDS } from '../src/testids'

/**
 * 真栈看板验证（真实 LLM / 真实行情 / 真实数据库）：
 *
 *     E2E_LLM=real npx playwright test e2e-live
 *
 * 不设 E2E_LLM=real 时整组跳过，默认 `npm run test:e2e` 仍是全离线档。
 * 真栈下这里只做三件事：主要区块必须有非空真实内容、刷新要闭环（POST 之后
 * 内容更新且没有错误态）、不允许任何「暂不可用 / 拒绝出数」的降级块。
 *
 * 「数据源不可用：GPR（…）」这类如实披露不是错误态：仓库红线要求拿不到就
 * 明说，所以断言只看「暂不可用」降级块与「刷新失败」报告，不按 CSS 类名一刀切。
 */

const LIVE = process.env.E2E_LLM === 'real'
const READY_TIMEOUT = 180_000
// 真栈一次完整抓取（9 个真实源里通常 8 个可用）实测约 60–90 秒；
// 受源站限速与重试影响可能更慢，客户端与用例都按更宽的上限等待。
const REFRESH_TIMEOUT = 540_000

async function expectRealContent(target: Locator, minChars: number, label: string) {
  await expect(target, `${label} 应当可见`).toBeVisible({ timeout: READY_TIMEOUT })
  await expect
    .poll(
      async () => (await target.innerText()).replace(/\s+/g, '').length,
      { message: `${label} 内容为空`, timeout: READY_TIMEOUT },
    )
    .toBeGreaterThan(minChars)
}

/** 没有缓存时后端会先返回「分析中」；点一次刷新并等真实结果，不伪造内容。 */
async function ensureAnalyzed(section: Locator, button: string) {
  const analyzing = section.getByText(/正在分析中|暂不可用/)
  if ((await analyzing.count()) > 0) {
    await section.getByRole('button', { name: button }).click()
  }
}

/** 不允许任何降级块与失败报告：出现即说明真栈该出的数没出。 */
async function expectNoDegradedState(page: Page) {
  await expect(page.getByText('暂不可用')).toHaveCount(0)
  await expect(page.getByText(/刷新失败/)).toHaveCount(0)
}

test.describe('GoldMind 真栈看板（E2E_LLM=real）', () => {
  test.skip(!LIVE, '只在真实栈下运行：E2E_LLM=real npx playwright test e2e-live')

  test('所有主要区块都有非空内容，且没有不可用 / 错误状态', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))

    await page.goto('/', { waitUntil: 'domcontentloaded' })

    // 报头：字标、锚点导航、今日速览、数据新鲜度条
    await expect(page.getByRole('heading', { level: 1, name: 'GoldMind' })).toBeVisible()
    await expectRealContent(page.getByTestId(TESTIDS.todaySummary), 10, '今日速览')
    await expectRealContent(page.getByTestId(TESTIDS.freshnessBar), 10, '数据新鲜度条')

    // 今日结论：等模型分析落地（无缓存时先点刷新）
    const conclusion = page.locator(`#${TESTIDS.sectionConclusion}`)
    await ensureAnalyzed(conclusion, '重新分析')
    await expectRealContent(conclusion.getByTestId(TESTIDS.conclusionSummary), 40, '今日结论')

    // 行情：报价、指标表、日线表、相关性表
    const market = page.locator(`#${TESTIDS.sectionMarket}`)
    await expectRealContent(market.getByTestId(TESTIDS.marketStats), 60, '行情指标')
    // 逐日数据在「行情」的一层折叠里（设计规范：每节一层折叠），先展开再断言。
    await market.getByTestId(TESTIDS.marketChart).locator('summary').click()
    await expectRealContent(market.getByTestId(TESTIDS.dailyTable), 40, '日线表')
    // gold-quote / dollar-quote 是卡片底部的口径行；卡片标题在 h3 上。
    // exact 必须加：默认子串匹配会连「金价与美元指数对照（N 行）」一起命中。
    await expect(market.getByRole('heading', { name: '纽约黄金', exact: true })).toBeVisible()
    await expect(market.getByTestId(TESTIDS.goldQuote)).toContainText('口径')
    await expect(market.getByRole('heading', { name: '美元指数', exact: true })).toBeVisible()
    await expect(market.getByTestId(TESTIDS.dollarQuote)).toContainText('交易日')

    // 驱动：看涨 / 看跌 / 消息 / 机构
    const bullish = page.getByTestId(TESTIDS.bullishFactors)
    const bearish = page.getByTestId(TESTIDS.bearishFactors)
    await ensureAnalyzed(bullish, '重新分析')
    await ensureAnalyzed(bearish, '重新分析')
    await expectRealContent(bullish, 60, '看涨因素')
    await expectRealContent(bearish, 60, '看跌因素')
    await expectRealContent(page.getByTestId(TESTIDS.driversMessages), 80, '消息')
    const institutions = page.getByTestId(TESTIDS.driversInstitutions)
    await ensureAnalyzed(institutions, '重新抓取')
    await expectRealContent(institutions, 60, '机构观点')

    // 量化预测：公允价值、监测信号、回测评估、四类因子
    const quant = page.locator(`#${TESTIDS.sectionQuant}`)
    await expectRealContent(quant.getByTestId(TESTIDS.quantFairValue), 60, '公允价值分解')
    await expectRealContent(quant.getByTestId(TESTIDS.quantMonitorTable), 60, '监测信号')
    // 回测与预测挂在尺度 tab 上：切到「1 季 / 1 年」再取内容
    await quant.getByRole('tab', { name: '1 季', exact: true }).first().click()
    await expectRealContent(quant.getByTestId('quant-accuracy-60'), 60, '回测评估（1 季）')
    await quant.getByRole('tab', { name: '1 年', exact: true }).first().click()
    await expectRealContent(quant.getByTestId('quant-prediction-250'), 60, '量化预测（1 年）')
    await expectRealContent(quant.getByTestId(TESTIDS.quantFactorTable).first(), 60, '四类影响因素')

    // 投资策略
    const strategy = page.locator(`#${TESTIDS.sectionStrategy}`)
    await ensureAnalyzed(strategy, '重新分析')
    await expectRealContent(strategy.getByTestId(TESTIDS.strategyColumns), 80, '投资策略')

    // 数据与方法
    const data = page.locator(`#${TESTIDS.sectionData}`)
    await expectRealContent(data.getByTestId(TESTIDS.dataSourcesStatus), 40, '数据源可用性')
    await expectRealContent(data.getByTestId(TESTIDS.dataBootstrap), 40, '初始化进度')
    await expectRealContent(data.getByTestId(TESTIDS.dataConfigWatch), 30, '配置与热加载')
    await expectRealContent(data.getByTestId(TESTIDS.dataLegend), 30, '口径说明')

    // 页脚免责声明
    await expect(page.getByRole('contentinfo')).toContainText('不构成投资建议')

    // 不允许任何「暂不可用」的降级块与未捕获异常
    await expectNoDegradedState(page)
    expect(errors).toEqual([])
  })

  test('刷新闭环：POST /api/gold/quant/refresh 后内容更新且没有错误', async ({ page }) => {
    // 真栈刷新要抓 9 个真实源再重算回测，单次实测约 60–90 秒；
    // 默认 90 秒用例预算只够抓一半，这里整体放宽到 10 分钟。
    test.setTimeout(600_000)

    await page.goto('/', { waitUntil: 'domcontentloaded' })

    const quant = page.locator(`#${TESTIDS.sectionQuant}`)
    await expectRealContent(quant.getByTestId(TESTIDS.quantFactorTable).first(), 40, '四类影响因素')

    // 记录刷新前的同步时间戳（落在「数据与方法 → 同步报告」）。
    const syncStamp = page.getByTestId(fieldTestId('quant.sync.finished_at'))
    await expect(syncStamp).toBeVisible({ timeout: READY_TIMEOUT })
    const before = (await syncStamp.innerText()).trim()

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) =>
          res.url().includes('/api/gold/quant/refresh') && res.request().method() === 'POST',
        { timeout: REFRESH_TIMEOUT },
      ),
      quant.getByRole('button', { name: '重新抓取' }).click(),
    ])
    expect(response.ok()).toBeTruthy()
    // 后端原话：本轮抓了几个源、生成了几个周期的预测，都要是真的
    const body = (await response.json()) as {
      success: boolean
      sources: unknown[]
      predictions: unknown[]
    }
    expect(body.success).toBe(true)
    expect(body.sources.length).toBeGreaterThan(0)
    expect(body.predictions.length).toBeGreaterThan(0)

    // 刷新报告必须显示成功与后端原话
    const success = page.getByTestId(fieldTestId('quant.refresh.success'))
    await expect(success).toContainText('成功')
    const message = page.getByTestId(fieldTestId('quant.refresh.message'))
    await expect(message).not.toBeEmpty()

    // 刷新后量化区块仍非空
    await expectRealContent(quant.getByTestId(TESTIDS.quantFactorTable).first(), 40, '四类影响因素')

    // 重载页面读刷新后的同步时间戳：格式是「YYYY-MM-DD HH:MM」，可直接
    // 字符串比较；同一分钟内完成时两者相等，所以断言「不早于」而不是「晚于」。
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expectRealContent(page.getByTestId(TESTIDS.quantFactorTable).first(), 40, '四类影响因素')
    const after = (await page.getByTestId(fieldTestId('quant.sync.finished_at')).innerText()).trim()
    expect(before).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
    expect(after).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
    expect(after >= before).toBe(true)

    await expectNoDegradedState(page)
  })
})
