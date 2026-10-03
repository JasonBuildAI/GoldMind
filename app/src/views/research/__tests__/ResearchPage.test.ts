import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { byTestId, createBlockHarness, hasText } from '@/test/harness'
import * as fixtures from '@/test/fixtures'
import { quantApi, sourcesApi, type QuantResearchResponse } from '@/services/api'
import { TESTIDS } from '@/testids'

import ResearchPage from '../ResearchPage.vue'

/**
 * 研究页：版本与裁决、前向留出期、覆盖度、诊断、分段、因子拆解、基准候选、同步报告。
 *
 * 这一页的职责是「把为什么现在还不能说模型有优势摊开写」，所以测试盯三件事：
 *   1. 裁决只认前向留出期 —— 没攒够独立下注时写「不可判定」并给出还差多少，
 *      **不许**写成「未过线」；
 *   2. 历史留出期那一列必须标成「已被看过，只作记录」，不能顶替结论；
 *   3. 取不到的值写「—」，不补默认数字。
 */
vi.mock('@/services/api', () => ({
  quantApi: { getResearch: vi.fn() },
  sourcesApi: { getStatus: vi.fn() },
}))

const mocked = vi.mocked({ quantApi, sourcesApi }, true)

const harness = createBlockHarness()

async function renderResearch() {
  const mounted = harness.mount(ResearchPage, { pinia: createPinia() })
  await vi.waitFor(() => {
    expect(byTestId(mounted.root, TESTIDS.researchOverview)).not.toBeNull()
  })
  return mounted
}

beforeEach(() => {
  vi.clearAllMocks()
  mocked.quantApi.getResearch.mockResolvedValue(fixtures.RESEARCH)
  mocked.sourcesApi.getStatus.mockResolvedValue(fixtures.SOURCES)
})

afterEach(() => {
  harness.cleanup()
})

describe('ResearchPage', () => {
  it('区块顺序固定：裁决 → 前向留出期 → 覆盖度 → 诊断 → 分段 → 因子 → 基准 → 同步报告', async () => {
    const { root } = await renderResearch()

    const ids = [
      TESTIDS.researchVerdict,
      TESTIDS.researchForwardWindow,
      TESTIDS.researchOverview,
      TESTIDS.researchCoverage,
      TESTIDS.researchDiagnostics,
      TESTIDS.researchRegimes,
      TESTIDS.researchFactors,
      TESTIDS.researchBenchmarks,
      TESTIDS.researchSync,
    ]
    const all = [...root.querySelectorAll('*')]
    const positions = ids.map((id) => {
      const node = byTestId(root, id)
      expect(node, `缺少 ${id}`).not.toBeNull()
      return all.indexOf(node!)
    })

    expect(positions).toEqual([...positions].sort((a, b) => a - b))
  })

  it('裁决块只展示接口给的结论，不自己下判断', async () => {
    const { root } = await renderResearch()

    const verdict = byTestId(root, TESTIDS.researchVerdict)!
    expect(verdict.textContent).toContain(fixtures.RESEARCH.verdict.label)
    expect(verdict.textContent).toContain(fixtures.RESEARCH.verdict.detail)
    expect(byTestId(root, 'field-research.verdict.status')?.textContent).toContain('no_edge')
  })

  it('数据窗口显著标注：起止、交易日数与年数', async () => {
    const { root } = await renderResearch()

    const window = byTestId(root, TESTIDS.researchDataWindow)!
    expect(window.textContent).toContain('2025-07-18')
    expect(window.textContent).toContain('2026-10-01')
    expect(window.textContent).toContain('311')
    expect(window.textContent).toContain('1.2')
  })

  it('前向留出期没攒够独立下注时写「尚不可判」并给出还差多少，不写「未过线」', async () => {
    const { root } = await renderResearch()

    const forward = byTestId(root, TESTIDS.researchForwardWindow)!
    // 夹具：需要 20 注、只有 2 注、还差 18 注、约 90 个交易日
    expect(forward.textContent).toContain('20')
    expect(forward.textContent).toContain('18')
    expect(forward.textContent).toContain('90')
    // 措辞：不能把「样本还没攒够」说成「模型没过线」
    expect(forward.textContent).not.toContain('未过线')
    // 术语表里的固定用词是「尚不可判」（见 docs/20-前端设计规范.md 第六节）
    expect(forward.textContent).toContain('尚不可判')
  })

  it('历史留出期那一列标明是「已被看过，只作记录」', async () => {
    const { root } = await renderResearch()

    const overview = byTestId(root, TESTIDS.researchOverview)!
    // 列头必须带「历史」字样，否则读者会把它当裁决依据
    expect(overview.querySelector('thead')?.textContent).toContain('历史')
    expect(hasText(overview, /已被/)).toBe(true)
  })

  it('技能总览把本模型与「永远看多」并排，并给出 Brier / CRPS 技能分', async () => {
    const { root } = await renderResearch()

    const overview = byTestId(root, TESTIDS.researchOverview)!
    const head = overview.querySelector('thead')?.textContent ?? ''
    expect(head).toContain('永远看多')
    expect(head).toContain('Brier')
    expect(head).toContain('CRPS')
  })

  it('每个尺度都能看到四个样本期的逐字段明细', async () => {
    const { root } = await renderResearch()

    const coverage = byTestId(root, TESTIDS.researchCoverage)!
    // 夹具是两个尺度（1 周 / 1 年）× 四个样本期
    for (const period of ['development', 'holdout', 'forward', 'full']) {
      expect(
        coverage.querySelectorAll(`[data-testid="field-research.periods.${period}.accuracy"]`).length,
        `缺少 ${period} 的命中率槽位`,
      ).toBeGreaterThan(0)
    }
  })

  it('基准候选原样展示「含展期」这类口径提示与不可用原因', async () => {
    const { root } = await renderResearch()

    const benchmarks = byTestId(root, TESTIDS.researchBenchmarks)!
    expect(byTestId(benchmarks, 'field-research.benchmark.note')?.textContent).toContain('展期')
    const alternative = byTestId(benchmarks, 'field-research.benchmark.alternatives.reason')
    expect(alternative?.textContent).toContain('暂无连续合约序列')
    // 可用性也要如实给
    expect(byTestId(benchmarks, 'field-research.benchmark.alternatives.available')).not.toBeNull()
  })

  it('Beta 后验与 CRPS 并排给出（前向裁决的独立证据）', async () => {
    const { root } = await renderResearch()

    // 后验表挂在「前向留出期」这一节里（#forward），与窗口够不够判并排。
    const forward = root.querySelector<HTMLElement>('#forward')!
    expect(hasText(forward, /Beta 后验/)).toBe(true)
    expect(forward.textContent).toContain('CRPS')
    // 后验的字段级槽位逐个有落点
    for (const name of ['prior', 'alpha', 'beta', 'successes', 'independent_bets', 'mean', 'ci95']) {
      expect(
        byTestId(root, `field-research.horizons.forward_posterior.${name}`),
        `缺少 forward_posterior.${name}`,
      ).not.toBeNull()
    }
  })

  it('接口失败时如实说不可用，不摆任何内置技能数字', async () => {
    mocked.quantApi.getResearch.mockRejectedValue(new Error('boom'))

    const { root } = await renderResearch().catch(() => harness.mount(ResearchPage))
    await vi.waitFor(() => {
      expect(hasText(root, '研究数据不可用')).toBe(true)
    })
    expect(byTestId(root, TESTIDS.researchOverview)).toBeNull()
    expect(byTestId(root, TESTIDS.researchForwardWindow)).toBeNull()
  })

  it('接口返回 unavailable 时原样展示原因，不补数字', async () => {
    mocked.quantApi.getResearch.mockResolvedValue({
      ...fixtures.RESEARCH,
      status: 'unavailable',
      reason: '因子面板为空：还没有可用的历史序列',
      data_window: null,
      horizons: [],
    } as unknown as QuantResearchResponse)

    const mounted = harness.mount(ResearchPage, { pinia: createPinia() })
    await vi.waitFor(() => {
      expect(hasText(mounted.root, '还没有可用的历史序列')).toBe(true)
    })
    expect(byTestId(mounted.root, TESTIDS.researchOverview)).toBeNull()
  })

  it('报头有回看板的链接与锚点导航，且每页一个 h1', async () => {
    const { root } = await renderResearch()

    expect(root.querySelectorAll('h1')).toHaveLength(1)
    const nav = root.querySelector('nav')!
    const back = [...nav.querySelectorAll('a')].find((a) => a.textContent?.includes('看板'))
    expect(back, '研究页没有回看板的链接').toBeTruthy()
    // 锚点全部可达
    const anchors = [...nav.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')]
    const missing = anchors
      .map((a) => a.getAttribute('href')!.replace('#', ''))
      .filter((id) => root.querySelector(`#${id}`) === null)
    expect(missing, `导航指向不存在的锚点：${missing.join('、')}`).toEqual([])
  })
})
