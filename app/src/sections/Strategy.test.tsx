import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Strategy from './Strategy'
import { investmentAdviceApi, type InvestmentAdviceResponse } from '../services/api'

vi.mock('../services/api', () => ({
  investmentAdviceApi: {
    getInvestmentAdvice: vi.fn(),
  },
}))

const mocked = vi.mocked(investmentAdviceApi, true)

const ADVICE = {
  market_assessment: {
    current_position: '接口返回的当前位置',
    risk_level: 'medium' as const,
    recommended_approach: '接口返回的建议策略',
    key_considerations: ['考量甲', '考量乙'],
  },
  strategies: [
    {
      type: 'conservative' as const,
      title: '接口返回的保守策略',
      description: '描述',
      allocation: '5%',
      timeframe: '长期',
      risk_level: 'low' as const,
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

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Strategy', () => {
  it('渲染市场评估与三档策略的对照字段', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue(ADVICE)

    render(<Strategy />)

    expect(await screen.findByText('接口返回的当前位置')).toBeInTheDocument()
    expect(screen.getByText('接口返回的建议策略')).toBeInTheDocument()
    expect(screen.getByText('考量甲；考量乙')).toBeInTheDocument()

    const columns = within(screen.getByTestId('strategy-columns'))
    expect(columns.getByText('接口返回的保守策略')).toBeInTheDocument()
    // 仓位 / 时间框架 / 风险
    expect(columns.getByText('5%')).toBeInTheDocument()
    expect(columns.getByText('长期')).toBeInTheDocument()
    expect(columns.getByText('低风险')).toBeInTheDocument()
    // 入场与离场
    expect(columns.getByText('$2500-2600')).toBeInTheDocument()
    expect(columns.getByText('$2900')).toBeInTheDocument()
    expect(columns.getByText('-10%')).toBeInTheDocument()
    // 优缺点与执行步骤
    expect(columns.getByText('优点甲')).toBeInTheDocument()
    expect(columns.getByText('缺点甲')).toBeInTheDocument()
    expect(columns.getByText('步骤1')).toBeInTheDocument()
  })

  it('渲染接口返回的执行原则与风险提示，而不是写死的文案', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue(ADVICE)

    render(<Strategy />)

    expect(await screen.findByText('接口返回的原则')).toBeInTheDocument()
    expect(screen.getByText('接口返回的风险提示')).toBeInTheDocument()
  })

  it('后端已开始分析时说明正在分析，而不是报「不可用」', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue({
      // 后端的占位响应就是这个形状：空数组 + 空对象（空对象是真值，
      // 只判 !assessment 会把空壳当成有内容，页面就显示一个空面板）。
      // 类型断言是因为 MarketAssessment 在接口契约里声明为完整对象，
      // 而真实占位响应并不满足它 —— 这正是要在界面上防住的形状。
      market_assessment: {},
      strategies: [],
      core_principles: [],
      risk_warning: '',
      disclaimer: '',
      metadata: { cached: false, status: 'analyzing' },
    } as unknown as InvestmentAdviceResponse)

    render(<Strategy />)

    expect(await screen.findByText('投资策略正在分析中')).toBeInTheDocument()
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
      },
      metadata: { cached: false, status: 'insufficient_data' },
    } as unknown as InvestmentAdviceResponse)

    render(<Strategy />)

    expect(await screen.findByText('数据不足，暂不生成策略')).toBeInTheDocument()
    expect(screen.getByText('$4245.14')).toBeInTheDocument()
    expect(screen.getByText('+11.71%')).toBeInTheDocument()
    expect(screen.getByText('41.94%')).toBeInTheDocument()
    expect(screen.queryByTestId('strategy-columns')).not.toBeInTheDocument()
  })

  it('接口失败时如实说「暂不可用」，不摆内置策略', async () => {
    mocked.getInvestmentAdvice.mockRejectedValue(new Error('boom'))

    render(<Strategy />)

    expect(await screen.findByText('投资策略暂不可用')).toBeInTheDocument()
    expect(screen.queryByTestId('strategy-columns')).not.toBeInTheDocument()
    expect(screen.queryByText('保守策略')).not.toBeInTheDocument()
    expect(screen.getByText(/无法连接后端/)).toBeInTheDocument()
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getInvestmentAdvice.mockRejectedValue(timeoutError)

    render(<Strategy />)

    expect(await screen.findByText(/分析耗时较长/)).toBeInTheDocument()
  })

  it('接口返回占位内容时明确标注，而不是当成分析结论', async () => {
    mocked.getInvestmentAdvice.mockResolvedValue({
      ...ADVICE,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })

    render(<Strategy />)

    expect(await screen.findByTestId('strategy-placeholder')).toBeInTheDocument()
  })
})
