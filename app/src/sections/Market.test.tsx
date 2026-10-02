import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Market from './Market'
import { useGoldData } from '@/contexts/GoldDataContext'
import type { GoldStats } from '@/services/api'

vi.mock('@/contexts/GoldDataContext', () => ({
  useGoldData: vi.fn(),
}))

const mockedUseGoldData = vi.mocked(useGoldData)

function stats(overrides: Partial<GoldStats> = {}): GoldStats {
  return {
    current_price: 2700,
    start_price: 2600,
    window_label: '近 12 个月',
    window_start: '2025-10-02',
    window_end: '2026-10-01',
    window_return: 3.85,
    max_price: 2750,
    min_price: 2580,
    max_date: '2025-06-01',
    min_date: '2025-01-02',
    amplitude: 6.59,
    market_status: '上涨',
    market_status_desc: '趋势向好',
    updated_at: '2026-02-03T10:00:00',
    data_source: '腾讯财经-纽约黄金',
    is_realtime: true,
    price_basis: 'close',
    price_basis_label: '日收盘',
    price_as_of: '2026-02-03T10:00:00',
    ...overrides,
  }
}

function renderMarket(overrides: Record<string, unknown> = {}) {
  mockedUseGoldData.mockReturnValue({
    stats: null,
    statsLoading: false,
    statsError: null,
    dailyPrices: [],
    dailyLoading: false,
    dailyError: null,
    correlationData: [],
    correlationLoading: false,
    correlationError: null,
    dollarRealtime: null,
    ...overrides,
  } as unknown as ReturnType<typeof useGoldData>)
  return render(<Market />)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Market 的数据新鲜度标识', () => {
  it('取到实时价时显示「实时报价」，并把来源放进 title', () => {
    renderMarket({ stats: stats({ is_realtime: true }) })

    expect(screen.getAllByText('实时报价').length).toBeGreaterThan(0)
    expect(screen.getAllByTitle('腾讯财经-纽约黄金').length).toBeGreaterThan(0)
    expect(screen.queryByText('历史数据')).not.toBeInTheDocument()
  })

  it('价格来自数据库时显示「历史数据」而不是「实时报价」', () => {
    renderMarket({ stats: stats({ is_realtime: false, data_source: '数据库历史数据' }) })

    expect(screen.queryByText('实时报价')).not.toBeInTheDocument()
    expect(screen.getAllByText('历史数据').length).toBeGreaterThan(0)
  })
})

describe('Market 不编造数据', () => {
  it('没有行情时显示「金价数据暂不可用」，且一个报价块都不渲染', () => {
    const { container } = renderMarket()

    expect(screen.getByTestId('market-unavailable')).toBeInTheDocument()
    expect(screen.getByText('金价数据暂不可用')).toBeInTheDocument()
    // 报价块出现就意味着有数字被顶上来当真实行情了
    expect(container.querySelectorAll('.quote')).toHaveLength(0)
  })

  it('接口报错时把原因如实显示出来', () => {
    renderMarket({ statsError: '无法连接后端，请检查网络后重试。' })

    expect(screen.getByText('无法连接后端，请检查网络后重试。')).toBeInTheDocument()
  })

  it('没有历史序列时说明「价格数据暂不可用」，不画内置曲线', () => {
    renderMarket({ stats: stats(), dailyError: '获取图表数据失败。' })

    expect(screen.getAllByText('价格数据暂不可用').length).toBeGreaterThan(0)
    expect(screen.queryByText(/最近 \d+ 个交易日/)).not.toBeInTheDocument()
  })
})

describe('Market 的涨跌表达', () => {
  it('涨跌同时给出符号与文字，不只靠颜色', () => {
    const { container } = renderMarket({ stats: stats({ window_return: 3.85 }) })

    const change = container.querySelector('.quote__change')
    expect(change).not.toBeNull()
    expect(change?.textContent).toContain('▲')
    expect(change?.textContent).toContain('涨')
    expect(change?.textContent).toContain('+3.85%')
  })
})

describe('Market 的窗口口径', () => {
  it('标注窗口长度，不把高低振幅叫成波动率', () => {
    renderMarket({ stats: stats() })

    expect(screen.getAllByText(/近 12 个月/).length).toBeGreaterThan(0)
    expect(screen.getByTestId('market-snapshot-table')).toBeInTheDocument()
    expect(screen.getByText('高低振幅')).toBeInTheDocument()
    // 口径注解跟着数字走：不把它叫成「波动率」，也不改名
    expect(screen.getByText('stats.amplitude')).toBeInTheDocument()
    expect(screen.queryByText(/波动率/)).not.toBeInTheDocument()
    expect(screen.queryByText('波动区间')).not.toBeInTheDocument()
    expect(screen.queryByText('年初至今')).not.toBeInTheDocument()
  })
})
