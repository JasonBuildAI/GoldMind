import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { byTestId, createBlockHarness, hasText } from '@/test/harness'
import { useMarketStore } from '@/stores/market'
import type { CorrelationData, DailyPrice, DollarRealtime, GoldStats } from '@/services/api'

import MarketSection from '../MarketSection.vue'

/**
 * 行情区块：数据新鲜度标识、不编造数据、涨跌表达与窗口口径。
 *
 * 区块读的是 Pinia store（由 30 秒轮询填充），所以测试直接写 store 状态，
 * 而不是替身 API —— 这样测的是「store 里有什么就显示什么」。
 */
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

const DAILY: DailyPrice[] = [{ date: '2026-02-03', price: 2700, volume: 1000 }]
const CORRELATION: CorrelationData[] = [
  { date: '2026-02-03', gold_price: 2700, dollar_index: 98.5 },
]
const DOLLAR: DollarRealtime = {
  price: 98.5,
  previous_close: 98.4,
  change: 0.1,
  change_percent: 0.1,
  open: 98.4,
  high: 98.6,
  low: 98.3,
  updated_at: '2026-02-03T10:00:00',
  date: '2026-02-03',
  source: '新浪财经-美元指数',
}

interface MarketFixture {
  stats?: GoldStats | null
  statsLoading?: boolean
  statsError?: string | null
  dailyPrices?: DailyPrice[]
  dailyError?: string | null
  dollarRealtime?: DollarRealtime | null
}

const harness = createBlockHarness()

function renderMarket(overrides: MarketFixture = {}) {
  const pinia = createPinia()
  const store = useMarketStore(pinia)
  store.stats = overrides.stats === undefined ? null : overrides.stats
  store.statsLoading = overrides.statsLoading ?? false
  store.statsError = overrides.statsError ?? null
  store.dailyPrices = overrides.dailyPrices ?? []
  store.dailyError = overrides.dailyError ?? null
  store.correlationData = []
  store.dollarRealtime = overrides.dollarRealtime ?? null
  return harness.mount(MarketSection, { pinia })
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  harness.cleanup()
})

describe('Market 的数据新鲜度标识', () => {
  it('取到实时价时显示「实时报价」，并把来源放进 title', () => {
    const { root } = renderMarket({ stats: stats({ is_realtime: true }) })

    expect(hasText(root, '实时报价')).toBe(true)
    expect(root.querySelectorAll('[title="腾讯财经-纽约黄金"]').length).toBeGreaterThan(0)
    expect(hasText(root, '历史数据')).toBe(false)
  })

  it('价格来自数据库时显示「历史数据」而不是「实时报价」', () => {
    const { root } = renderMarket({
      stats: stats({ is_realtime: false, data_source: '数据库历史数据' }),
    })

    expect(hasText(root, '实时报价')).toBe(false)
    expect(hasText(root, '历史数据')).toBe(true)
  })
})

describe('Market 不编造数据', () => {
  it('没有行情时显示「金价数据暂不可用」，且一个报价块都不渲染', () => {
    const { root } = renderMarket()

    expect(byTestId(root, 'market-unavailable')).not.toBeNull()
    expect(hasText(root, '金价数据暂不可用')).toBe(true)
    // 报价块出现就意味着有数字被顶上来当真实行情了
    expect(root.querySelectorAll('.quote')).toHaveLength(0)
  })

  it('接口报错时把原因如实显示出来', () => {
    const { root } = renderMarket({ statsError: '无法连接后端，请检查网络后重试。' })

    expect(hasText(root, '无法连接后端，请检查网络后重试。')).toBe(true)
  })

  it('没有历史序列时说明「价格数据暂不可用」，不画内置曲线', () => {
    const { root } = renderMarket({ stats: stats(), dailyError: '获取图表数据失败。' })

    expect(hasText(root, '价格数据暂不可用')).toBe(true)
    expect(hasText(root, /最近 \d+ 个交易日/)).toBe(false)
  })
})

describe('Market 的涨跌表达', () => {
  it('涨跌同时给出符号与文字，不只靠颜色', () => {
    const { root } = renderMarket({ stats: stats({ window_return: 3.85 }) })

    const change = root.querySelector('.quote__change')
    expect(change).not.toBeNull()
    expect(change?.textContent).toContain('▲')
    expect(change?.textContent).toContain('涨')
    expect(change?.textContent).toContain('+3.85%')
  })
})

describe('Market 的窗口口径', () => {
  it('标注窗口长度，不把高低振幅叫成波动率', () => {
    const { root } = renderMarket({ stats: stats() })

    expect(hasText(root, '近 12 个月')).toBe(true)
    expect(byTestId(root, 'market-snapshot-table')).not.toBeNull()
    expect(hasText(root, '高低振幅')).toBe(true)
    // 口径注解跟着数字走：不把它叫成「波动率」，也不改名
    expect(hasText(root, 'stats.amplitude')).toBe(true)
    expect(hasText(root, '波动率')).toBe(false)
    expect(hasText(root, '波动区间')).toBe(false)
    expect(hasText(root, '年初至今')).toBe(false)
  })

  it('走势图与逐日数据收在一层折叠里，默认不占版面', () => {
    const { root } = renderMarket({ stats: stats(), dailyPrices: DAILY })

    const details = root.querySelector('details[data-testid="market-chart"]')
    expect(details).not.toBeNull()
    expect(details?.hasAttribute('open')).toBe(false)
    expect(details?.querySelector('summary')?.textContent).toContain('展开走势图与逐日数据')
  })

  it('美元指数报价与快照字段逐行展示，含交易日与来源', () => {
    const { root } = renderMarket({ stats: stats(), dollarRealtime: DOLLAR })

    expect(hasText(root, '新浪财经-美元指数')).toBe(true)
    expect(byTestId(root, 'field-dollar.date')?.textContent?.trim()).toBe('2026-02-03')
    expect(byTestId(root, 'field-dollar.price')?.textContent?.trim()).toBe('98.50')
    expect(byTestId(root, 'dollar-quote')?.textContent).toContain('交易日 2026-02-03')
  })

  it('相关性表的金价与美元各带自己的口径与来源列', () => {
    const pinia = createPinia()
    const store = useMarketStore(pinia)
    store.stats = stats()
    store.correlationData = CORRELATION
    store.statsLoading = false
    store.correlationLoading = false
    const { root } = harness.mount(MarketSection, { pinia })

    const table = byTestId(root, 'correlation-table')
    expect(table).not.toBeNull()
    expect(table?.textContent).toContain('金价口径')
    expect(table?.textContent).toContain('美元口径')
    expect(byTestId(root, 'field-correlation.gold_price')?.textContent).toContain('$2,700.00')
  })
})
