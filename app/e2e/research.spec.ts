import { expect, test } from '@playwright/test'

/**
 * 研究页端到端：浏览器 → vite preview 代理 → uvicorn → SQLite。
 *
 * E2E 种子库没有量化因子面板，因此这里断言的是「诚实降级」链路：
 * 接口如实返回 unavailable + 原因，页面把这些话原样显示，不补任何数字。
 * 有数据时的完整渲染由集成测试 backend/tests/integration/test_quant_research_api.py
 * 与组件测试 src/research/ResearchPage.test.tsx 覆盖。
 */
test.describe('GoldMind 研究页端到端', () => {
  test('研究接口经代理可达，页面与接口说的一致且无前端异常', async ({ page, request }) => {
    const resp = await request.get('/api/gold/quant/research')
    expect(resp.ok()).toBeTruthy()
    const body = await resp.json()
    expect(body.holdout_start).toBe('2023-10-02')
    expect(body.model_version).toBe('quant-v4')
    expect(['ok', 'unavailable']).toContain(body.status)

    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))

    await page.goto('/research.html')

    await expect(page.getByRole('heading', { level: 1, name: 'GoldMind' })).toBeVisible()
    await expect(page.getByRole('link', { name: '看板' })).toBeVisible()
    await expect(page.getByTestId('research-verdict')).toContainText(body.verdict.label)

    if (body.status === 'ok') {
      await expect(page.getByTestId('research-overview')).toBeVisible()
    } else {
      await expect(page.getByText(body.reason)).toBeVisible()
    }

    expect(errors).toEqual([])
  })
})
