import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Hero from './Hero'
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
    ytd_return: 3.85,
    max_price: 2750,
    min_price: 2580,
    max_date: '2025-06-01',
    min_date: '2025-01-02',
    volatility: 6.59,
    market_status: '上涨',
    market_status_desc: '趋势向好',
    updated_at: '2026-02-03T10:00:00',
    data_source: '腾讯财经-纽约黄金',
    is_realtime: true,
    ...overrides,
  }
}

function renderHero(value: GoldStats | null, loading = false, error: string | null = null) {
  mockedUseGoldData.mockReturnValue({
    stats: value,
    statsLoading: loading,
    statsError: error,
  } as unknown as ReturnType<typeof useGoldData>)
  return render(<Hero />)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Hero 的数据新鲜度标识', () => {
  it('取到实时价时显示「实时」', () => {
    renderHero(stats({ is_realtime: true }))

    expect(screen.getAllByText('实时').length).toBeGreaterThan(0)
    expect(screen.queryByText('历史数据')).not.toBeInTheDocument()
  })

  it('价格来自数据库时显示「历史数据」而不是「实时」', () => {
    // 回归：原先这个绿色徽标是无条件渲染的 —— 即使价格来自数据库里的
    // 历史记录，页面照样闪着绿点说「实时」。
    renderHero(stats({ is_realtime: false, data_source: '数据库历史数据' }))

    expect(screen.queryByText('实时')).not.toBeInTheDocument()
    expect(screen.getAllByText('历史数据').length).toBeGreaterThan(0)
  })

  it('没有数据时如实说「暂不可用」，不摆一个编造的价格', () => {
    // 回归：原实现在这里用一份 fallbackStats 顶着，其中 current_price 是
    // 写死的 2823.0 —— 页面会显示一个根本不存在的金价。
    // 项目红线：「不为了好看而展示编造的数据，宁可显示「数据不可用」」。
    renderHero(null, false)

    expect(screen.getByTestId('hero-unavailable')).toBeInTheDocument()
    expect(screen.getByText('金价数据暂不可用')).toBeInTheDocument()
    // 不能出现任何价格数字或「纽约黄金期货」那张卡
    expect(screen.queryByText('纽约黄金期货', { exact: true })).not.toBeInTheDocument()
    expect(screen.queryByText('$2,823.00')).not.toBeInTheDocument()
    expect(screen.queryByText('实时')).not.toBeInTheDocument()
  })

  it('把数据来源放在 title 里，便于悬停确认', () => {
    renderHero(stats({ data_source: '新浪财经-伦敦金' }))

    expect(screen.getAllByTitle('新浪财经-伦敦金').length).toBeGreaterThan(0)
  })
})
