import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { byTestId, createBlockHarness, hasText } from '@/test/harness'
import { investmentAdviceApi, type InvestmentAdviceResponse } from '@/services/api'

import StrategySection from '../StrategySection.vue'

/**
 * 投资策略：市场评估、三档对照、执行原则与风险提示、三态与降级分支。
 *
 * 降级分支（`analysis_status: 'insufficient_data'`）值得单独说：那时后端
 * **没有调用模型**，只回一份确定性行情统计。页面必须明说「数据不足」，
 * 而不是把统计当成策略展示。
 */
vi.mock('@/services/api', () => ({
  investmentAdviceApi: { getInvestmentAdvice: vi.fn() },
}))

const mocked = vi.mocked(investmentAdviceApi, true)

const ADVICE: InvestmentAdviceResponse = {
  market_assessment: {
    current_position: '接口返回的当前位置',
    risk_level: 'medium',
    recommended_approach: '接口返回的建议策略',
    key_considerations: ['考量甲', '考量乙'],
  },
  strategies: [
    {
      type: 'conservative',
      title: '接口返回的保守策略',
      description: '描述',
      allocation: '5%',
      timeframe: '长期',
      risk_level: 'low',
      entry_strategy: {
        current_price_assessment: '偏高',
        recommended_entry_range: '$2500-2600',
        entry_timing: '等待回调',
        position_building: '分三批',
      },
      exit_strategy: {
        profit_target: '$2900',
        stop_loss: '-10%',
        rebalancing_trigger: '年末',
      },
      pros: ['优点甲'],
      cons: ['缺点甲'],
      suitable_for: ['新手'],
      execution_steps: ['步骤1', '步骤2'],
    },
  ],
  core_principles: [{ title: '接口返回的原则', description: '原则描述' }],
  risk_warning: '接口返回的风险提示',
  disclaimer: '接口返回的免责声明',
}

const harness = createBlockHarness()

/** 挂载并等到终态：三档对照、数据不足、正在分析、不可用四者之一。 */
async function renderStrategy() {
  const mounted = harness.mount(StrategySection)
  await vi.waitFor(() => {
    expect(
      mounted.root.querySelector(
        '[data-testid="strategy-columns"], [data-testid="strategy-insufficient"], [data-testid="strategy-analyzing"], [data-testid="strategy-unavailable"]',
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

describe('Strategy', () => {
  it('渲染市场评估与三档策略的对照字段', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue(ADVICE)

    const { root } = await renderStrategy()

    expect(byTestId(root, 'field-advice.assessment.current_position')?.textContent).toContain(
      '接口返回的当前位置',
    )
    expect(byTestId(root, 'field-advice.assessment.recommended_approach')?.textContent).toContain(
      '接口返回的建议策略',
    )
    expect(byTestId(root, 'field-advice.assessment.key_considerations')?.textContent).toContain(
      '考量甲；考量乙',
    )

    const columns = byTestId(root, 'strategy-columns')!
    expect(columns.textContent).toContain('接口返回的保守策略')
    // 仓位 / 时间框架 / 风险
    expect(columns.textContent).toContain('5%')
    expect(columns.textContent).toContain('长期')
    expect(byTestId(root, 'field-advice.strategy.risk_level')?.textContent).toContain('低风险')
    // 入场与离场
    expect(columns.textContent).toContain('$2500-2600')
    expect(columns.textContent).toContain('$2900')
    expect(columns.textContent).toContain('-10%')
    // 优缺点与执行步骤
    expect(columns.textContent).toContain('优点甲')
    expect(columns.textContent).toContain('缺点甲')
    expect(columns.textContent).toContain('步骤1')
  })

  it('渲染接口返回的执行原则与风险提示，而不是写死的文案', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue(ADVICE)

    const { root } = await renderStrategy()

    expect(hasText(root, '接口返回的原则')).toBe(true)
    expect(hasText(root, '接口返回的风险提示')).toBe(true)
    expect(hasText(root, '接口返回的免责声明')).toBe(true)
  })

  it('后端已开始分析时说明正在分析，而不是报「不可用」', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue({
      // 后端的占位响应就是这个形状：空数组 + 空对象（空对象是真值，
      // 只判 !assessment 会把空壳当成有内容，页面就显示一个空面板）。
      market_assessment: {},
      strategies: [],
      core_principles: [],
      risk_warning: '',
      disclaimer: '',
      metadata: { cached: false, status: 'analyzing' },
    } as unknown as InvestmentAdviceResponse)

    const { root } = await renderStrategy()

    expect(hasText(root, '投资策略正在分析中')).toBe(true)
  })

  it('数据不足时如实说明，只展示行情统计', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue({
      // 降级响应：不调模型、不给策略，只给行情统计与说明。
      market_assessment: {},
      strategies: [],
      core_principles: [],
      risk_warning: '当前没有可分析的数据输入（多空因子 / 可核实机构预测 / 近期新闻均为空）。',
      disclaimer: '',
      analysis_status: 'insufficient_data',
      price_snapshot: {
        label: '近12个月',
        window_start: '2025-10-01',
        window_end: '2026-10-01',
        latest_price: 4245.14,
        change_pct: 11.71,
        high: 4400,
        low: 3100,
        amplitude_pct: 41.94,
        full_window: true,
        as_of: '2026-10-01',
        basis: 'close',
        basis_label: '日收盘',
        source: 'gold_prices 日线',
      },
      metadata: { cached: false, status: 'insufficient_data' },
    } as unknown as InvestmentAdviceResponse)

    const { root } = await renderStrategy()

    expect(hasText(root, '数据不足，暂不生成策略')).toBe(true)
    expect(byTestId(root, 'field-advice.snapshot.latest_price')?.textContent).toContain('$4,245.14')
    expect(byTestId(root, 'field-advice.snapshot.change_pct')?.textContent).toContain('+11.71%')
    expect(byTestId(root, 'field-advice.snapshot.amplitude_pct')?.textContent).toContain('41.94%')
    // 快照价是金价：它自己的交易日 / 口径 / 来源必须一起给
    expect(byTestId(root, 'field-advice.snapshot.as_of')?.textContent).toContain('2026-10-01')
    expect(byTestId(root, 'field-advice.snapshot.basis_label')?.textContent).toContain('日收盘')
    expect(byTestId(root, 'field-advice.snapshot.source')?.textContent).toContain('gold_prices 日线')
    expect(byTestId(root, 'strategy-columns')).toBeNull()
  })

  it('接口失败时如实说「暂不可用」，不摆内置策略', async () => {
    mocked.getInvestmentAdvice.mockRejectedValue(new Error('boom'))

    const { root } = await renderStrategy()

    expect(hasText(root, '投资策略暂不可用')).toBe(true)
    expect(byTestId(root, 'strategy-columns')).toBeNull()
    expect(hasText(root, '保守策略')).toBe(false)
    expect(hasText(root, /无法连接后端/)).toBe(true)
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getInvestmentAdvice.mockRejectedValue(timeoutError)

    const { root } = await renderStrategy()

    expect(hasText(root, /分析耗时较长/)).toBe(true)
  })

  it('接口返回占位内容时明确标注，而不是当成分析结论', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue({
      ...ADVICE,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })

    const { root } = await renderStrategy()

    expect(byTestId(root, 'strategy-placeholder')).not.toBeNull()
  })

  it('三档策略字段同名同序：换一档后同样的字段仍然有槽位', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue({
      ...ADVICE,
      strategies: [
        ...ADVICE.strategies,
        { ...ADVICE.strategies[0], type: 'balanced', title: '均衡档' },
        { ...ADVICE.strategies[0], type: 'opportunistic', title: '机会档' },
      ],
    })

    const { root } = await renderStrategy()

    const columns = byTestId(root, 'strategy-columns')!
    for (const type of ['conservative', 'balanced', 'opportunistic']) {
      expect(byTestId(columns, `strategy-${type}`), `缺少 ${type} 档`).not.toBeNull()
    }
    // 三档各自都带同一批字段槽位
    expect(columns.querySelectorAll('[data-testid="field-advice.strategy.allocation"]').length).toBe(3)
    expect(columns.querySelectorAll('[data-testid="field-advice.entry.entry_timing"]').length).toBe(3)
    expect(columns.querySelectorAll('[data-testid="field-advice.exit.profit_target"]').length).toBe(3)
  })
})
