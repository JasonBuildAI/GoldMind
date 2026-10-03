import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { buttonByText, byTestId, createBlockHarness, hasText } from '@/test/harness'
import { analysisApi, type BearishFactorsResponse, type BullishFactorsResponse } from '@/services/api'

import FactorColumns from '../FactorColumns.vue'

/**
 * 多空对照：两侧独立取数与刷新、三态、占位标注。
 *
 * 最要紧的一条：接口失败或返回空列表时**不许**摆内置因子。原实现会在失败时
 * 回退到一组写死的因子与总结，那违反「不编造数据」的红线。
 */
vi.mock('@/services/api', () => ({
  analysisApi: { getBullishFactors: vi.fn(), getBearishFactors: vi.fn() },
}))

const mocked = vi.mocked(analysisApi, true)

const BULLISH: BullishFactorsResponse = {
  bullish_factors: [
    {
      id: 'fed-policy',
      title: '接口返回的看涨因素',
      subtitle: '来自接口',
      description: '描述',
      details: ['要点1', '要点2'],
      impact: 'high',
    },
  ],
  analysis_summary: '看涨总结',
  last_updated: '2026-02-03 10:00:00',
}

const BEARISH: BearishFactorsResponse = {
  bearish_factors: [
    {
      id: 'dollar-strength',
      title: '接口返回的看跌因素',
      subtitle: '来自接口',
      description: '描述',
      details: ['要点1', '要点2'],
      impact: 'medium',
    },
  ],
  analysis_summary: '看跌总结',
  last_updated: '2026-02-03 10:00:00',
}

const harness = createBlockHarness()

/** 挂载并等两侧的取数都落定。 */
async function renderFactors() {
  const mounted = harness.mount(FactorColumns)
  await vi.waitFor(() => {
    expect(mocked.getBullishFactors).toHaveBeenCalled()
    expect(mocked.getBearishFactors).toHaveBeenCalled()
  })
  // 等状态真正写进 DOM：三态块或内容块总有一个出现
  await vi.waitFor(() => {
    expect(mounted.root.querySelectorAll('[data-testid^="bullish-"]').length).toBeGreaterThan(0)
  })
  return mounted
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  harness.cleanup()
})

describe('Factors', () => {
  it('两侧各自渲染接口返回的因子与总结', async () => {
    mocked.getBullishFactors.mockResolvedValue(BULLISH)
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    const { root } = await renderFactors()

    expect(hasText(root, '接口返回的看涨因素')).toBe(true)
    expect(hasText(root, '接口返回的看跌因素')).toBe(true)
    expect(byTestId(root, 'field-bullish.analysis_summary')?.textContent).toContain('看涨总结')
    expect(byTestId(root, 'field-bearish.analysis_summary')?.textContent).toContain('看跌总结')
    // 不应再显示内置默认因子
    expect(hasText(root, '美联储降息周期')).toBe(false)
  })

  it('接口失败时如实说「暂不可用」，而不是摆内置文案', async () => {
    mocked.getBullishFactors.mockRejectedValue(new Error('boom'))
    mocked.getBearishFactors.mockRejectedValue(new Error('boom'))

    const { root } = await renderFactors()

    expect(hasText(root, '看涨因素暂不可用')).toBe(true)
    expect(hasText(root, '看跌因素暂不可用')).toBe(true)
    // 不能出现任何内置的因子或总结文案
    expect(hasText(root, '美联储降息周期')).toBe(false)
    expect(byTestId(root, 'field-bullish.analysis_summary')).toBeNull()
    expect(byTestId(root, 'field-bearish.analysis_summary')).toBeNull()
    // 同时要说明失败原因
    expect(hasText(root, /无法连接后端/)).toBe(true)
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getBullishFactors.mockRejectedValue(timeoutError)
    mocked.getBearishFactors.mockRejectedValue(timeoutError)

    const { root } = await renderFactors()

    const matches = [...root.querySelectorAll('*')].filter((node) =>
      /分析耗时较长/.test(node.textContent ?? ''),
    )
    expect(matches.length).toBeGreaterThan(0)
    expect(hasText(root, '看涨因素暂不可用')).toBe(true)
    expect(hasText(root, '看跌因素暂不可用')).toBe(true)
  })

  it('接口返回空列表时也走「暂不可用」，不摆内置因子', async () => {
    mocked.getBullishFactors.mockResolvedValue({
      bullish_factors: [],
      analysis_summary: '',
      last_updated: '',
    })
    mocked.getBearishFactors.mockResolvedValue({
      bearish_factors: [],
      analysis_summary: '',
      last_updated: '',
    })

    const { root } = await renderFactors()

    expect(hasText(root, '看涨因素暂不可用')).toBe(true)
    expect(hasText(root, '美联储降息周期')).toBe(false)
  })

  it('一侧失败不影响另一侧', async () => {
    mocked.getBullishFactors.mockRejectedValue(new Error('boom'))
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    const { root } = await renderFactors()

    expect(hasText(root, '看涨因素暂不可用')).toBe(true)
    expect(hasText(root, '接口返回的看跌因素')).toBe(true)
    expect(byTestId(root, 'field-bullish.analysis_summary')).toBeNull()
    expect(byTestId(root, 'field-bearish.analysis_summary')?.textContent).toContain('看跌总结')
  })

  // ------------------------------------------------------------------ //
  // 占位内容
  // ------------------------------------------------------------------ //
  it('有内容但后端标了占位时，标注提示条而不是当成分析结论', async () => {
    // 缓存未命中时后端会立刻返回一份内置内容（metadata.status = 'analyzing'），
    // 结构与真实分析完全一样。不看 metadata 就会把内置常量当结论展示。
    mocked.getBullishFactors.mockResolvedValue({
      ...BULLISH,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })
    mocked.getBearishFactors.mockResolvedValue({
      ...BEARISH,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })

    const { root } = await renderFactors()

    expect(byTestId(root, 'bullish-placeholder')).not.toBeNull()
    expect(byTestId(root, 'bearish-placeholder')).not.toBeNull()
    // 内容仍然展示（占位内容是后端给的，不是前端编的），但必须带提示
    expect(hasText(root, '接口返回的看涨因素')).toBe(true)
    expect(byTestId(root, 'bullish-placeholder')?.textContent).toContain('占位内容')
  })

  it('空内容 + 正在分析时走「正在分析中」，而不是「暂不可用」', async () => {
    mocked.getBullishFactors.mockResolvedValue({
      bullish_factors: [],
      analysis_summary: '',
      last_updated: '',
      metadata: { cached: false, status: 'analyzing' },
    })
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    const { root } = await renderFactors()

    expect(byTestId(root, 'bullish-analyzing')).not.toBeNull()
    expect(byTestId(root, 'bullish-unavailable')).toBeNull()
    expect(hasText(root, '看涨因素正在分析中')).toBe(true)
  })

  it('真实分析结果不显示占位提示', async () => {
    mocked.getBullishFactors.mockResolvedValue({
      ...BULLISH,
      metadata: { cached: true, cache_source: 'file' },
    })
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    const { root } = await renderFactors()

    expect(hasText(root, '接口返回的看涨因素')).toBe(true)
    expect(byTestId(root, 'bullish-placeholder')).toBeNull()
  })

  it('空内容 + 正在分析时说明正在分析，并可以手动触发重算', async () => {
    mocked.getBullishFactors
      .mockResolvedValueOnce({
        bullish_factors: [],
        analysis_summary: '',
        last_updated: '',
        metadata: { cached: false, status: 'analyzing' },
      })
      .mockResolvedValueOnce(BULLISH)
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    const { root } = await renderFactors()

    expect(hasText(root, '看涨因素正在分析中')).toBe(true)

    const column = byTestId(root, 'bullish-factors')
    expect(column).not.toBeNull()
    buttonByText(column!, '重新分析')?.click()

    await vi.waitFor(() => {
      expect(hasText(root, '接口返回的看涨因素')).toBe(true)
    })
    expect(mocked.getBullishFactors).toHaveBeenLastCalledWith(true)
  })

  it('逐条因子本身是折叠，且不再套第二层折叠', async () => {
    mocked.getBullishFactors.mockResolvedValue(BULLISH)
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    const { root } = await renderFactors()

    const column = byTestId(root, 'bullish-factors')!
    const factor = column.querySelector('.factor')
    expect(factor).not.toBeNull()

    const details = factor!.querySelector('details')
    expect(details).not.toBeNull()
    expect(details?.querySelector('summary')?.textContent).toContain('接口返回的看涨因素')
    // 可读性规范：折叠最多一层 —— 因子折叠里不许再有折叠
    expect(details?.querySelectorAll('details').length).toBe(0)
    // 因子列表也不许被包在另一层折叠里
    expect(column.querySelectorAll('details').length).toBe(column.querySelectorAll('.factor').length + 1)
  })
})
