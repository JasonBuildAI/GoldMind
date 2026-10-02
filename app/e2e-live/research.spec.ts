import { expect, test, type Locator } from '@playwright/test'

import { fieldTestId, TESTIDS } from '../src/testids'

/**
 * 真栈研究页验证（真实数据库 / 真实量化数据）：
 *
 *     E2E_LLM=real npx playwright test e2e-live
 *
 * 不设 E2E_LLM=real 时整组跳过。真栈下研究页必须给出完整技能面板，
 * 而不是「研究数据不可用」的降级块。
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

test.describe('GoldMind 真栈研究页（E2E_LLM=real）', () => {
  test.skip(!LIVE, '只在真实栈下运行：E2E_LLM=real npx playwright test e2e-live')

  test('覆盖度 / 诊断 / 分段 / 因子 / 基准 / 同步报告都有真实内容', async ({
    page,
    request,
  }) => {
    // 接口层先确认状态：真栈下研究接口必须是 ok，否则页面只能降级
    const resp = await request.get('/api/gold/quant/research')
    expect(resp.ok()).toBeTruthy()
    const body = await resp.json()
    expect(body.status).toBe('ok')
    expect(body.horizons.length).toBeGreaterThan(0)

    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))

    await page.goto('/research.html', { waitUntil: 'domcontentloaded' })

    await expect(page.getByRole('heading', { level: 1, name: 'GoldMind' })).toBeVisible()
    await expect(page.getByRole('link', { name: '看板' })).toBeVisible()

    // 裁决块：标签、状态、详情与数据窗口
    await expectRealContent(page.getByTestId(TESTIDS.researchVerdict), 60, '版本与裁决')
    await expectRealContent(page.getByTestId(TESTIDS.researchDataWindow), 10, '数据窗口')

    // 前向留出期（裁决窗口）与 Beta 后验
    await expectRealContent(page.getByTestId(TESTIDS.researchForwardWindow), 80, '前向留出期')

    // 覆盖度：技能总览表 + 四个样本期明细
    await expectRealContent(page.getByTestId(TESTIDS.researchOverview), 80, '技能总览')
    await expectRealContent(page.getByTestId(TESTIDS.researchCoverage), 40, '覆盖度明细')

    // 诊断 / 分段 / 因子 / 基准 / 同步报告
    await expectRealContent(page.getByTestId(TESTIDS.researchDiagnostics), 40, '诊断')
    await expectRealContent(page.getByTestId(TESTIDS.researchRegimes), 40, '分段')
    await expectRealContent(page.getByTestId(TESTIDS.researchFactors), 40, '因子拆解')
    await expectRealContent(page.getByTestId(TESTIDS.researchBenchmarks), 40, '基准候选')
    await expectRealContent(page.getByTestId(TESTIDS.researchSync), 30, '同步报告')

    // 来源 / 数据截至列：裁决窗口必须写出 active_holdout_start
    await expect(page.getByTestId(fieldTestId('research.active_holdout_start'))).toContainText(
      String(body.active_holdout_start),
    )
    await expect(page.getByTestId(fieldTestId('research.holdout_start'))).toContainText(
      String(body.holdout_start),
    )

    // 无错误态、无未捕获异常
    expect(await page.locator('.panel__error').count()).toBe(0)
    await expect(page.getByText('研究数据不可用')).toHaveCount(0)
    expect(errors).toEqual([])
  })
})