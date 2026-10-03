import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createBlockHarness, type Mounted } from '@/test/harness'
import * as fixtures from '@/test/fixtures'
import { TESTIDS } from '@/testids'

/**
 * 结构守卫：整页挂载后，页面骨架必须满足可访问性与「一个事实一个来源」的要求。
 *
 * 为什么是测试而不是靠人看：这些约束（每页一个 h1、skip link 指向真实存在的
 * 目标、锚点导航的每一项都能落到真实的节、tab 有 aria-selected、id 不重复、
 * 折叠不嵌套）一旦破了，页面在**浏览器里仍然能跑** —— 只有读屏用户与键盘用户
 * 会受影响，而他们不会来提 issue。
 */
const apiMocks = vi.hoisted(() => ({
  goldApi: {
    getStats: vi.fn(),
    getDailyPrices: vi.fn(),
    getCorrelation: vi.fn(),
    getDollarRealtime: vi.fn(),
  },
  analysisApi: { getBullishFactors: vi.fn(), getBearishFactors: vi.fn() },
  institutionApi: { getInstitutionPredictions: vi.fn() },
  investmentAdviceApi: { getInvestmentAdvice: vi.fn() },
  marketSummaryApi: { getMarketSummary: vi.fn() },
  quantApi: {
    getFactors: vi.fn(),
    getPredictions: vi.fn(),
    getAccuracy: vi.fn(),
    getMonitor: vi.fn(),
    getResearch: vi.fn(),
    refresh: vi.fn(),
  },
  newsDigestApi: { getDigest: vi.fn(), refresh: vi.fn() },
  sourcesApi: { getStatus: vi.fn() },
  healthApi: { getHealth: vi.fn() },
}))

vi.mock('@/services/api', () => apiMocks)

const harness = createBlockHarness()
let dashboard: Mounted | null = null

/** 整页挂载并等最后一个区块（量化预测）渲染出来。 */
async function renderDashboard(): Promise<Mounted> {
  if (dashboard) return dashboard

  const { createPinia } = await import('pinia')
  const pinia = createPinia()

  apiMocks.goldApi.getStats.mockResolvedValue(fixtures.GOLD_STATS)
  apiMocks.goldApi.getDailyPrices.mockResolvedValue(fixtures.DAILY)
  apiMocks.goldApi.getCorrelation.mockResolvedValue(fixtures.CORRELATION)
  apiMocks.goldApi.getDollarRealtime.mockResolvedValue(fixtures.DOLLAR)
  apiMocks.marketSummaryApi.getMarketSummary.mockResolvedValue(fixtures.SUMMARY)
  apiMocks.analysisApi.getBullishFactors.mockResolvedValue(fixtures.BULLISH)
  apiMocks.analysisApi.getBearishFactors.mockResolvedValue(fixtures.BEARISH)
  apiMocks.institutionApi.getInstitutionPredictions.mockResolvedValue(fixtures.INSTITUTIONS)
  apiMocks.investmentAdviceApi.getInvestmentAdvice.mockResolvedValue(fixtures.ADVICE)
  apiMocks.newsDigestApi.getDigest.mockResolvedValue(fixtures.DIGEST)
  apiMocks.quantApi.getFactors.mockResolvedValue(fixtures.FACTORS_RESPONSE)
  apiMocks.quantApi.getPredictions.mockResolvedValue(fixtures.PREDICTIONS_RESPONSE)
  apiMocks.quantApi.getAccuracy.mockResolvedValue(fixtures.ACCURACY_RESPONSE)
  apiMocks.quantApi.getMonitor.mockResolvedValue(fixtures.MONITOR_RESPONSE)
  apiMocks.quantApi.getResearch.mockResolvedValue(fixtures.RESEARCH)
  apiMocks.sourcesApi.getStatus.mockResolvedValue(fixtures.SOURCES)
  apiMocks.healthApi.getHealth.mockResolvedValue(fixtures.HEALTH)
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ services: { ai_config: fixtures.HEALTH.services.ai_config } }),
    })),
  )

  const [{ default: DashboardPage }, { useMarketStore }] = await Promise.all([
    import('@/views/dashboard/DashboardPage.vue'),
    import('@/stores/market'),
  ])

  // 行情区块读 store，不直接调 API —— 先喂满，否则 stats.* 全无槽位。
  const marketStore = useMarketStore(pinia)
  marketStore.stats = fixtures.GOLD_STATS
  marketStore.dailyPrices = fixtures.DAILY
  marketStore.correlationData = fixtures.CORRELATION
  marketStore.dollarRealtime = fixtures.DOLLAR
  marketStore.statsLoading = false
  marketStore.dailyLoading = false
  marketStore.correlationLoading = false

  dashboard = harness.mount(DashboardPage, {
    pinia,
    // 整页测试关掉轮询：留着定时器会让后面的用例被一次「取数失败」改掉 DOM。
    props: { autoPoll: false },
  })
  await vi.waitFor(() => {
    expect(dashboard!.root.querySelector('[data-testid="field-quant.model_version"]')).not.toBeNull()
  })
  return dashboard
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  harness.cleanup()
  dashboard = null
  vi.unstubAllGlobals()
})

describe('结构守卫：页面骨架', () => {
  it('每页恰好一个 h1，且它是字标', async () => {
    const { root } = await renderDashboard()

    const h1s = [...root.querySelectorAll('h1')]
    expect(h1s).toHaveLength(1)
    expect(h1s[0].textContent).toContain('GoldMind')
  })

  it('skip link 指向真实存在的目标', async () => {
    const { root } = await renderDashboard()

    const skip = root.querySelector<HTMLAnchorElement>('a.skip-link')
    expect(skip, '缺少跳到主要内容的 skip link').not.toBeNull()
    const target = skip!.getAttribute('href')!.replace('#', '')
    expect(root.querySelector(`#${target}`), `skip link 指向不存在的 #${target}`).not.toBeNull()
  })

  it('语义标签齐全：header / nav / main / footer 各一个', async () => {
    const { root } = await renderDashboard()

    expect(root.querySelectorAll('header')).toHaveLength(1)
    expect(root.querySelectorAll('nav')).toHaveLength(1)
    expect(root.querySelectorAll('main')).toHaveLength(1)
    expect(root.querySelectorAll('footer')).toHaveLength(1)
  })

  it('锚点导航的每一项都能落到真实的节', async () => {
    const { root } = await renderDashboard()

    const nav = root.querySelector('nav')!
    const anchors = [...nav.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')]
    expect(anchors.length).toBeGreaterThanOrEqual(5)

    const missing = anchors
      .map((anchor) => anchor.getAttribute('href')!.replace('#', ''))
      .filter((id) => root.querySelector(`#${id}`) === null)
    expect(missing, `导航指向不存在的锚点：${missing.join('、')}`).toEqual([])
  })

  it('阅读顺序固定：今日结论 → 行情 → 驱动 → 消息 → 量化预测 → 投资策略 → 数据与方法', async () => {
    const { root } = await renderDashboard()

    const order = [
      TESTIDS.sectionConclusion,
      TESTIDS.sectionMarket,
      TESTIDS.sectionDrivers,
      // 消息 2026-10-03 起是一等板块：夹在「驱动」与「量化预测」之间
      TESTIDS.sectionMessages,
      TESTIDS.sectionQuant,
      TESTIDS.sectionStrategy,
      TESTIDS.sectionData,
    ]
    const all = [...root.querySelectorAll('*')]
    const positions = order.map((id) => {
      const node = root.querySelector(`#${id}`)
      expect(node, `缺少 #${id}`).not.toBeNull()
      return all.indexOf(node!)
    })

    expect(positions, '各节的阅读顺序被改动了').toEqual([...positions].sort((a, b) => a - b))
  })

  it('消息是独立的一节，不再挂在「驱动」里面', async () => {
    const { root } = await renderDashboard()

    const drivers = root.querySelector(`#${TESTIDS.sectionDrivers}`)!
    const messages = root.querySelector(`#${TESTIDS.sectionMessages}`)!
    expect(messages).not.toBeNull()
    // 搬出来之后不能再留在「驱动」的子树里 —— 否则导航有了入口，
    // 内容却还是「驱动」的一部分，两处锚点指向同一块内容。
    expect(drivers.contains(messages)).toBe(false)
    // 导航里必须有「消息」这一项，且指向真实存在的那一节
    const nav = root.querySelector('nav')!
    const link = [...nav.querySelectorAll<HTMLAnchorElement>('a[href="#messages"]')]
    expect(link, '侧边栏没有「消息」入口').toHaveLength(1)
    expect(link[0].textContent).toBe('消息')
  })

  it('id 不重复（重复 id 会让锚点跳到错误的元素）', async () => {
    const { root } = await renderDashboard()

    const ids = [...root.querySelectorAll('[id]')].map((node) => node.id)
    const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index)
    expect([...new Set(duplicates)], '存在重复 id').toEqual([])
  })

  it('每个 tablist 里的 tab 都有 aria-selected，且恰有一个选中', async () => {
    const { root } = await renderDashboard()

    const tablists = [...root.querySelectorAll('[role="tablist"]')]
    expect(tablists.length, '页面上一个 tablist 都没有，守卫形同虚设').toBeGreaterThan(0)

    for (const tablist of tablists) {
      const tabs = [...tablist.querySelectorAll('[role="tab"]')]
      expect(tabs.length).toBeGreaterThan(0)
      for (const tab of tabs) {
        expect(tab.getAttribute('aria-selected'), 'tab 缺少 aria-selected').toMatch(/true|false/)
      }
      const selected = tabs.filter((tab) => tab.getAttribute('aria-selected') === 'true')
      expect(selected, '一个 tablist 里选中的 tab 不是恰好一个').toHaveLength(1)
    }
  })

  it('所有按钮都有可访问名，且不出现裸的 <div onclick>', async () => {
    const { root } = await renderDashboard()

    const nameless = [...root.querySelectorAll('button')].filter(
      (button) => !(button.textContent ?? '').trim() && !button.getAttribute('aria-label'),
    )
    expect(nameless, '有按钮没有可访问名').toEqual([])

    // 可点击的东西必须是原生按钮 / 链接：div + onclick 键盘按不到
    expect(root.querySelectorAll('div[onclick]')).toHaveLength(0)
  })

  it('折叠最多一层：任何 details 里都不许再有 details', async () => {
    const { root } = await renderDashboard()

    const nested = [...root.querySelectorAll('details')].filter(
      (details) => details.querySelectorAll('details').length > 0,
    )
    expect(nested.length, '存在嵌套两层的折叠').toBe(0)
  })
})
