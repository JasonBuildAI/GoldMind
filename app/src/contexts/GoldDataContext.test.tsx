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

// 用**本地**日期，别用 toISOString() —— 那是 UTC 日期。
// 原来这里和被测代码用了同一个 UTC 公式，两边「错得一样」，
// 于是永远相等、测试永远绿，掩盖了东八区 00:00-08:00 之间不更新的 bug。
const TODAY = new Date().toLocaleDateString('en-CA')

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
  data_source: '腾讯财经-纽约黄金',
  is_realtime: true,
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
  // 行情自带的交易日：前端用它判断「最后一个点是不是今天」
  date: TODAY,
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
    // 夹具抛的是没有 `response` 的错误 —— 语义上就是「没拿到响应」，
    // 也就是连不上后端。文案应当说明这一点，而不是笼统的「获取失败」。
    mocked.getStats.mockRejectedValue(new Error('boom'))
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('stats-error')).toHaveTextContent('无法连接后端')
    })
    expect(screen.getByTestId('price')).toHaveTextContent('none')
  })

  it('图表接口失败时给出错误', async () => {
    mocked.getDailyPrices.mockRejectedValue(new Error('boom'))
    mocked.getCorrelation.mockRejectedValue(new Error('boom'))
    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('daily-error')).toHaveTextContent('无法连接后端')
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

  it('按行情自带的交易日判断，而不是浏览器算出来的「今天」', async () => {
    // 回归：原实现用 `new Date().toISOString().split('T')[0]` 取「今天」，
    // 那是 **UTC** 日期 —— 东八区 00:00-08:00 之间它给出的是昨天，
    // 于是「最后一个点是不是今天」永远判 false，实时美元指数静默不更新，
    // 相关性图上今天那个点一直显示旧值。
    //
    // 这条测试不依赖跑测试时的钟点：故意用一个**不可能是今天**的日期，
    // 只要两边一致就必须合并。旧实现拿它跟「今天」比，必然不合并。
    const quoteDay = '2025-06-01'
    mocked.getCorrelation.mockResolvedValue([
      { date: '2025-01-02', gold_price: 2600, dollar_index: 108 },
      { date: quoteDay, gold_price: 2610, dollar_index: 107.9 },
    ])
    mocked.getDollarRealtime.mockResolvedValue({
      ...DOLLAR_REALTIME,
      date: quoteDay,
      price: 106.5,
    })

    renderProvider()

    await waitFor(() => {
      expect(screen.getByTestId('corr-last-dollar')).toHaveTextContent('106.5')
    })
    expect(screen.getByTestId('corr-count')).toHaveTextContent('2')
  })

  it('行情日期与最后一点不一致时不动它', async () => {
    // 反向：日期对不上就不该合并，否则又是拿实时值去覆盖一个别的交易日。
    mocked.getCorrelation.mockResolvedValue([
      { date: '2025-01-02', gold_price: 2600, dollar_index: 108 },
      { date: '2025-01-03', gold_price: 2610, dollar_index: 107.9 },
    ])
    mocked.getDollarRealtime.mockResolvedValue({
      ...DOLLAR_REALTIME,
      date: '2025-01-04',
      price: 106.5,
    })

    renderProvider()

    await waitFor(() => {
      expect(mocked.getDollarRealtime).toHaveBeenCalled()
    })
    expect(screen.getByTestId('corr-last-dollar')).toHaveTextContent('107.9')
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
