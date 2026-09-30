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

  it('兜底数据也不声称自己是实时的', () => {
    // statsLoading=false + stats=null：加载已结束但没有数据，此时页面展示的
    // 就是 fallbackStats。
    //
    // 必须让这张卡片**真的渲染出来**：若 statsLoading 仍为 true，卡片整块不渲染，
    // 「找不到实时」的断言会无条件通过 —— 那是假绿。
    // 变异测试实测确认过：把 fallbackStats.is_realtime 改成 true，旧写法照样绿。
    renderHero(null, false)

    expect(screen.getByText('纽约黄金期货', { exact: true })).toBeInTheDocument()
    expect(screen.queryByText('实时')).not.toBeInTheDocument()
    expect(screen.getAllByText('历史数据').length).toBeGreaterThan(0)
  })

  it('把数据来源放在 title 里，便于悬停确认', () => {
    renderHero(stats({ data_source: '新浪财经-伦敦金' }))

    expect(screen.getAllByTitle('新浪财经-伦敦金').length).toBeGreaterThan(0)
  })
})
