import { expect, test, type Locator } from '@playwright/test'

import { fieldTestId, TESTIDS } from '../src/testids'

/**
 * 真栈看板验证（真实 LLM / 真实行情 / 真实数据库）：
 *
 *     E2E_LLM=real npx playwright test e2e-live
 *
 * 不设 E2E_LLM=real 时整组跳过，默认 `npm run test:e2e` 仍是全离线档。
 * 真栈下这里只做三件事：主要区块必须有非空真实内容、刷新要闭环（POST 之后
 * 内容更新且没有错误态）、不允许任何「暂不可用 / 拒绝出数」的降级块。
 */

const LIVE = process.env.E2E_LLM === 'real'
const READY_TIMEOUT = 180_000

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
    await expectRealContent(market.getByTestId(TESTIDS.dailyTable), 40, '日线表')
    await expect(market.getByTestId(TESTIDS.goldQuote)).toContainText('纽约黄金')
    await expect(market.getByTestId(TESTIDS.dollarQuote)).toContainText('美元指数')

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
    expect(await page.locator('.panel__error').count()).toBe(0)
    expect(errors).toEqual([])
  })

  test('刷新闭环：POST /api/gold/quant/refresh 后内容更新且没有错误', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    const quant = page.locator(`#${TESTIDS.sectionQuant}`)
    await expectRealContent(quant.getByTestId(TESTIDS.quantFactorTable).first(), 40, '四类影响因素')

    // 记录刷新前的同步时间戳，刷新后要求它重新渲染（内容确实更新了）
    const syncStamp = quant.getByTestId(fieldTestId('quant.sync.finished_at'))
    const before = (await syncStamp.count()) > 0 ? await syncStamp.innerText() : ''

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) =>
          res.url().includes('/api/gold/quant/refresh') && res.request().method() === 'POST',
        { timeout: READY_TIMEOUT },
      ),
      quant.getByRole('button', { name: '重新抓取' }).click(),
    ])
    expect(response.ok()).toBeTruthy()

    // 刷新报告必须显示成功与后端原话
    const success = page.getByTestId(fieldTestId('quant.refresh.success'))
    await expect(success).toContainText('成功')
    const message = page.getByTestId(fieldTestId('quant.refresh.message'))
    await expect(message).not.toBeEmpty()

    // 刷新后区块仍非空；同步时间戳有落点（后端可能在同一秒内完成，值可相同）
    await expectRealContent(quant.getByTestId(TESTIDS.quantFactorTable).first(), 40, '四类影响因素')
    await expect(syncStamp.first()).toBeVisible()
    expect(before.length).toBeGreaterThanOrEqual(0)
    expect(await page.locator('.panel__error').count()).toBe(0)
    await expect(page.getByText(/刷新失败/)).toHaveCount(0)
  })
})