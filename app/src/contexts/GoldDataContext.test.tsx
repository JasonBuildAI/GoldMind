import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { GoldDataProvider, useGoldData } from './GoldDataContext'
import { goldApi } from '@/services/api'

vi.mock('@/services/api', () => ({
  goldApi: {
    getStats: vi.fn(),
    getDailyPrices: vi.fn(),
    getCorrelation: vi.fn(),
    getDollarRealtime: vi.fn(),
  },
}))

const mocked = vi.mocked(goldApi, true)

const TODAY = new Date().toISOString().split('T')[0]

const STATS = {
  current_price: 2710.8,
  start_price: 2600,
  ytd_return: 4.26,
  max_price: 2750,
  min_price: 2580,
  max_date: '2025-06-01',
  min_date: '2025-01-02',
  volatility: 6.59,
  market_status: '上涨',
  market_status_desc: '趋势向好',
  updated_at: '2026-02-03T10:00:00',
}

const DAILY = [
  { date: '2025-01-02', price: 2600, volume: 100 },
  { date: '2025-01-03', price: 2610, volume: 110 },
]

/** 历史数据的最后一天是 2025-01-03，不是今天。 */
const CORRELATION_HISTORICAL = [
  { date: '2025-01-02', gold_price: 2600, dollar_index: 108 },
  { date: '2025-01-03', gold_price: 2610, dollar_index: 107.9 },
]

const DOLLAR_REALTIME = {
  price: 107.5,
  previous_close: 108,
  change_percent: -0.46,
  updated_at: '2026-02-03T10:00:00',
  source: '测试',
}

/** 只暴露被测字段的探针组件。 */
function Probe() {
  const { stats, dailyPrices, correlationData, statsError, dailyError } = useGoldData()
  const last = correlationData[correlationData.length - 1]
  return (
    <div>
      <span data-testid="price">{stats ? stats.current_price : 'none'}</span>
      <span data-testid="daily-count">{dailyPrices.length}</span>
      <span data-testid="corr-count">{correlationData.length}</span>
      <span data-testid="corr-last-date">{last ? last.date : 'none'}</span>
      <span data-testid="corr-last-dollar">{last ? last.dollar_index : 'none'}</span>
      <span data-testid="stats-error">{statsError ?? ''}</span>
      <span data-testid="daily-error">{dailyError ?? ''}</span>
    </div>
  )
}

function renderProvider() {
  return render(
    <GoldDataProvider>
      <Probe />
    </GoldDataProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocked.getStats.mockResolvedValue(STATS)
  mocked.getDailyPrices.mockResolvedValue(DAILY)
  mocked.getCorrelation.mockResolvedValue([...CORRELATION_HISTORICAL])
  mocked.getDollarRealtime.mockResolvedValue(DOLLAR_REALTIME)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('GoldDataProvider', () => {
  it('挂载时拉取统计数据并渲染出来', async () => {
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('price')).toHaveTextContent('2710.8')
    })
    expect(mocked.getStats).toHaveBeenCalled()
  })

  it('挂载时同时拉取日线与相关性数据', async () => {
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('daily-count')).toHaveTextContent('2')
      expect(screen.getByTestId('corr-count')).toHaveTextContent('2')
    })
  })

  it('统计接口失败时给出错误，而不是抛异常', async () => {
    mocked.getStats.mockRejectedValue(new Error('boom'))
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('stats-error')).toHaveTextContent('获取统计数据失败')
    })
    expect(screen.getByTestId('price')).toHaveTextContent('none')
  })

  it('图表接口失败时给出错误', async () => {
    mocked.getDailyPrices.mockRejectedValue(new Error('boom'))
    mocked.getCorrelation.mockRejectedValue(new Error('boom'))
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('daily-error')).toHaveTextContent('获取图表数据失败')
    })
  })

  // ------------------------------------------------------------------ #
  // 数据完整性
  // ------------------------------------------------------------------ #
  it('历史数据的最后一天不是今天时，不追加伪造的数据点', async () => {
    // 回归：原实现会 push 一个 date=今天、gold_price 取自上一历史交易日的点，
    // 在「金价 vs 美元指数」图上造出一个假点。
    renderProvider()

    await waitFor(() => {
      expect(mocked.getDollarRealtime).toHaveBeenCalled()
    })
    expect(screen.getByTestId('corr-count')).toHaveTextContent('2')
    expect(screen.getByTestId('corr-last-date')).toHaveTextContent('2025-01-03')
  })

  it('最后一点确实是今天时，用实时美元指数更新它（不新增点）', async () => {
    mocked.getCorrelation.mockResolvedValue([
      { date: '2025-01-02', gold_price: 2600, dollar_index: 108 },
      { date: TODAY, gold_price: 2610, dollar_index: 107.9 },
    ])
    mocked.getDollarRealtime.mockResolvedValue({ ...DOLLAR_REALTIME, price: 106.5 })

    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('corr-last-dollar')).toHaveTextContent('106.5')
    })
    expect(screen.getByTestId('corr-count')).toHaveTextContent('2')
  })

  it('每 10 秒轮询一次统计数据', async () => {
    vi.useFakeTimers()
    renderProvider()

    await vi.advanceTimersByTimeAsync(0)
    const initialCalls = mocked.getStats.mock.calls.length
    expect(initialCalls).toBeGreaterThan(0)

    await vi.advanceTimersByTimeAsync(10000)
    await vi.advanceTimersByTimeAsync(10000)

    expect(mocked.getStats.mock.calls.length).toBeGreaterThan(initialCalls + 1)
  })
})
