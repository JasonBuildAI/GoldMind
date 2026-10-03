import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { byTestId, createBlockHarness, hasText } from '@/test/harness'
import { marketSummaryApi, type MarketSummaryResponse } from '@/services/api'

import ConclusionSection from '../ConclusionSection.vue'

/**
 * 今日结论：内容渲染、目标价与当前价格的取值口径、三态与占位标记。
 *
 * 贯穿本文件的一条线：**取不到就显示「—」**。把 0 渲染成 `$0.00`、或摆一个
 * 写死的价格，都是这个项目明确不要的行为。
 */
vi.mock('@/services/api', () => ({
  marketSummaryApi: { getMarketSummary: vi.fn() },
}))

const mocked = vi.mocked(marketSummaryApi, true)

const SUMMARY: MarketSummaryResponse = {
  core_bullish_logic: ['接口返回的看涨逻辑'],
  main_risks: ['接口返回的主要风险'],
  market_consensus: ['接口返回的市场共识'],
  institution_targets: [
    { institution: '接口返回的机构', target: 5400, probability: '高', timeframe: '2026年底' },
  ],
  current_price: 2690,
  comprehensive_judgment: {
    bullish_summary: '接口返回的看多判断',
    bearish_summary: '接口返回的看空判断',
    neutral_summary: '接口返回的中性判断',
  },
  core_view: '接口返回的核心观点',
  investment_recommendation: '接口返回的投资建议',
  confidence_level: '中',
  time_horizon: '中期',
}

const harness = createBlockHarness()

/**
 * 挂载并等到**终态**出现。
 *
 * 不能等 `[data-testid^="conclusion-"]`：那个前缀也会命中初始的
 * `conclusion-loading`，于是 waitFor 立刻返回、断言在「正在读取…」上跑，
 * 每个用例都变成假绿或假红。终态只有三种：内容行、正在分析、不可用。
 */
async function renderConclusion() {
  const mounted = harness.mount(ConclusionSection)
  await vi.waitFor(() => {
    expect(
      mounted.root.querySelector(
        '[data-testid="field-summary.core_view"], [data-testid="conclusion-analyzing"], [data-testid="conclusion-unavailable"]',
      ),
    ).not.toBeNull()
  })
  return mounted
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  harness.cleanup()
})

describe('Conclusion', () => {
  it('渲染三栏要点、综合判断与核心观点', async () => {
    mocked.getMarketSummary.mockResolvedValue(SUMMARY)

    const { root } = await renderConclusion()

    expect(hasText(root, '接口返回的看涨逻辑')).toBe(true)
    expect(hasText(root, '接口返回的主要风险')).toBe(true)
    expect(hasText(root, '接口返回的市场共识')).toBe(true)
    expect(hasText(root, '接口返回的看多判断')).toBe(true)
    expect(hasText(root, '接口返回的看空判断')).toBe(true)
    expect(hasText(root, '接口返回的中性判断')).toBe(true)
    expect(hasText(root, '接口返回的核心观点')).toBe(true)
    expect(hasText(root, '接口返回的投资建议')).toBe(true)
    expect(hasText(root, '中期')).toBe(true)
  })

  it('目标价按接口返回展示，当前价格取接口字段而不是写死的数字', async () => {
    mocked.getMarketSummary.mockResolvedValue(SUMMARY)

    const { root } = await renderConclusion()

    expect(hasText(root, '$5,400.00')).toBe(true)
    expect(hasText(root, '当前价格')).toBe(true)
    expect(hasText(root, '$2,690.00')).toBe(true)
  })

  it('机构没有目标价、模型写成 0 时显示「—」，不是 $0.00', async () => {
    // 回归：模型对「暂无目标价」会写 target: 0，Intl 把它渲染成 $0.00 —— 那是
    // 一个并不存在的价格。设计规范要求算不出的字段显示「—」，不填默认值。
    mocked.getMarketSummary.mockResolvedValue({
      ...SUMMARY,
      institution_targets: [
        { institution: '接口返回的机构', target: 0, probability: '低', timeframe: '暂无' },
      ],
    })

    const { root } = await renderConclusion()

    expect(hasText(root, '接口返回的机构')).toBe(true)
    expect(hasText(root, '$0.00')).toBe(false)
  })

  it('接口没给当前价格时显示「—」，不摆写死的数字', async () => {
    // 回归：原实现把当前价格写死成 5067 —— 那是凭空的数字，
    // 会被当成「当前价格」摆在目标价表里。
    mocked.getMarketSummary.mockResolvedValue({ ...SUMMARY, current_price: 0 })

    const { root } = await renderConclusion()

    expect(byTestId(root, 'field-summary.current_price')?.textContent?.trim()).toBe('—')
    expect(hasText(root, '$5,067.00')).toBe(false)
  })

  it('接口失败时如实说「暂不可用」，不摆内置结论', async () => {
    mocked.getMarketSummary.mockRejectedValue(new Error('boom'))

    const { root } = await renderConclusion()

    expect(hasText(root, '今日结论暂不可用')).toBe(true)
    expect(hasText(root, '核心看涨逻辑')).toBe(false)
    expect(hasText(root, /无法连接后端/)).toBe(true)
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getMarketSummary.mockRejectedValue(timeoutError)

    const { root } = await renderConclusion()

    expect(hasText(root, /分析耗时较长/)).toBe(true)
  })

  it('后端已开始分析（空内容）时说明正在分析，而不是报「不可用」', async () => {
    mocked.getMarketSummary.mockResolvedValue({
      core_bullish_logic: [],
      main_risks: [],
      market_consensus: [],
      institution_targets: [],
      current_price: 0,
      comprehensive_judgment: { bullish_summary: '', bearish_summary: '', neutral_summary: '' },
      core_view: '',
      investment_recommendation: '',
      confidence_level: '',
      time_horizon: '',
      metadata: { cached: false, status: 'analyzing' },
    })

    const { root } = await renderConclusion()

    expect(hasText(root, '今日结论正在分析中')).toBe(true)
  })

  it('市场总结的占位标记（cache_source=default）也会被标注', async () => {
    // 市场总结与其余区块不同：它用 cache_source === 'default' 表示占位内容。
    mocked.getMarketSummary.mockResolvedValue({
      ...SUMMARY,
      metadata: { cached: true, cache_source: 'default' },
    })

    const { root } = await renderConclusion()

    expect(byTestId(root, 'conclusion-placeholder')).not.toBeNull()
  })
})
