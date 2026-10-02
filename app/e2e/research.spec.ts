import { expect, test } from '@playwright/test'

import { TESTIDS } from '../src/testids'

/**
 * 研究页端到端：浏览器 → vite preview 代理 → uvicorn → SQLite。
 *
 * E2E 种子库没有量化因子面板，因此这里断言的是「诚实降级」链路：
 * 接口如实返回 unavailable + 原因，页面把这些话原样显示，不补任何数字。
 * 有数据时的完整渲染由集成测试 backend/tests/integration/test_quant_research_api.py
 * 与组件测试 src/research/ResearchPage.test.tsx 覆盖。
 */
const RESEARCH_NAV = [
  '裁决',
  '前向留出期',
  '覆盖度',
  '诊断',
  '分段',
  '因子',
  '基准',
  '同步报告',
]

test.describe('GoldMind 研究页端到端', () => {
  test('研究接口经代理可达，页面与接口说的一致且无前端异常', async ({ page, request }) => {
    const resp = await request.get('/api/gold/quant/research')
    expect(resp.ok()).toBeTruthy()
    const body = await resp.json()
    expect(body.holdout_start).toBe('2023-10-02')
    // 裁决窗口自成一列：封板日之后才是干净的样本外，页面必须把这段摊开
    expect(body.active_holdout_start).toBe('2026-10-03')
    expect(body.model_version).toBe('quant-v7')
    expect(['ok', 'unavailable']).toContain(body.status)

    if (body.status === 'ok') {
      for (const horizon of body.horizons) {
        expect(horizon.periods.forward).toBeTruthy()
        expect(horizon.forward_readiness.window_start).toBe('2026-10-03')
        expect(horizon.forward_readiness.required_bets).toBeGreaterThan(0)
      }
    }

    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))

    await page.goto('/research.html')

    await expect(page.getByRole('heading', { level: 1, name: 'GoldMind' })).toBeVisible()
    await expect(page.getByRole('link', { name: '看板' })).toBeVisible()
    for (const label of RESEARCH_NAV) {
      await expect(page.getByRole('link', { name: label, exact: true })).toBeVisible()
    }

    // 裁决块只展示接口给的结论；没有结论时，降级原因必须原样出现
    await expect(page.getByTestId(TESTIDS.researchVerdict)).toContainText(body.verdict.label)

    if (body.status === 'ok') {
      for (const id of [
        TESTIDS.researchDataWindow,
        TESTIDS.researchForwardWindow,
        TESTIDS.researchOverview,
        TESTIDS.researchCoverage,
        TESTIDS.researchDiagnostics,
        TESTIDS.researchRegimes,
        TESTIDS.researchFactors,
        TESTIDS.researchBenchmarks,
        TESTIDS.researchSync,
      ]) {
        await expect(page.getByTestId(id)).toBeVisible()
      }
    } else {
      await expect(page.getByText(body.reason)).toBeVisible()
    }

    expect(errors).toEqual([])
  })
})