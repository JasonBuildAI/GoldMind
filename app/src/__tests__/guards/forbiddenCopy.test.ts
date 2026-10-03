import { describe, expect, it, vi } from 'vitest'

import { createBlockHarness } from '@/test/harness'
import * as fixtures from '@/test/fixtures'

/**
 * 界面文案守卫：页面上不得出现与实现不符的能力宣称。
 *
 * 为什么这是一条测试而不是文案偏好：当前实现是**单轮 LLM 调用**
 * （见 `docs/00-产品方向.md` 第三节），没有多 Agent 协作、没有 ReAct、
 * 没有 RAG。把这些词写在界面上等于替系统编造能力，违反本项目
 * 「不许编造」的红线 —— 而这条线以前只在浏览器 e2e 里守，跑得慢、
 * 定位差，改坏了要等一整套 Playwright 才知道。
 *
 * 扫描方式：把**全部区块**用全非空夹具渲染出来，再扫一遍可见文本。
 * 空白页扫不出什么 —— 真正会漏的是「有数据之后」才渲染出来的那些行。
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

/**
 * 禁用词。用词边界匹配：`coverage` / `storage` / `average` 里都含 "rag"，
 * 不设边界会把「覆盖度」的代号 coverage 误判成能力宣称。
 */
const FORBIDDEN = /\bAgent\b|\bReAct\b|\bRAG\b|多智能体|智能驱动/i

const harness = createBlockHarness()

describe('界面文案守卫', () => {
  it('全部区块渲染后，页面文本不出现未实现的能力宣称', async () => {
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

    const [
      { default: ConclusionSection },
      { default: MarketSection },
      { default: DriversSection },
      { default: MessagesSection },
      { default: QuantSection },
      { default: StrategySection },
      { default: DataMethodsSection },
      { default: ResearchPage },
      { useMarketStore },
    ] = await Promise.all([
      import('@/views/dashboard/ConclusionSection.vue'),
      import('@/views/dashboard/MarketSection.vue'),
      import('@/views/dashboard/DriversSection.vue'),
      // 消息独立成节之后，光挂「驱动」已经扫不到消息的文案了 —— 必须一起挂上，
      // 否则这块内容里的能力宣称（最容易在这里出现）就没人守了。
      import('@/views/dashboard/MessagesSection.vue'),
      import('@/views/dashboard/QuantSection.vue'),
      import('@/views/dashboard/StrategySection.vue'),
      import('@/views/dashboard/DataMethodsSection.vue'),
      import('@/views/research/ResearchPage.vue'),
      import('@/stores/market'),
    ])

    const marketStore = useMarketStore(pinia)
    marketStore.stats = fixtures.GOLD_STATS
    marketStore.dailyPrices = fixtures.DAILY
    marketStore.correlationData = fixtures.CORRELATION
    marketStore.dollarRealtime = fixtures.DOLLAR
    marketStore.statsLoading = false
    marketStore.dailyLoading = false
    marketStore.correlationLoading = false

    const mounted = [
      ConclusionSection,
      MarketSection,
      DriversSection,
      MessagesSection,
      QuantSection,
      StrategySection,
      DataMethodsSection,
      ResearchPage,
    ].map((component) => harness.mount(component, { pinia }))

    // 等最后一个区块（研究页）把夹具渲染出来，再整体扫描
    await vi.waitFor(() => {
      expect(document.querySelector('[data-testid="field-research.model_version"]')).not.toBeNull()
    })

    const text = mounted.map((instance) => instance.root.textContent ?? '').join('\n')

    // 守卫自身：确认真的扫到了内容，否则「没匹配到禁用词」是空转
    expect(text.length).toBeGreaterThan(2000)

    expect(text).not.toMatch(FORBIDDEN)

    harness.cleanup()
    vi.unstubAllGlobals()
  })
})
