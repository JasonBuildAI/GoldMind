import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import { createBlockHarness } from '@/test/harness'
import * as fixtures from '@/test/fixtures'
import { fieldTestId, QUANT_FACTOR_COVERAGE_FIELDS, TESTIDS } from '@/testids'

/**
 * 字段覆盖守卫：每个响应字段都必须在页面上有展示位。
 *
 * 这是本项目的硬验收之一 —— 「内容一项不丢」这句话靠它变成可执行的检查。
 * 夹具让字段尽量非空，然后把 `TESTIDS.field` 里声明的字段级选择器逐个断言。
 * 新增响应字段却忘了给槽位、或槽位只挂在走不到的分支上，missing 列表会报出来。
 *
 * 互斥分支（投资策略的降级快照、量化预测的停发方向、消息的第二个窗口）
 * 用二次挂载覆盖 —— 字段只要在任一状态有槽位就算通过。
 *
 * 挂载方式：所有区块共用**一个** Pinia 与一批 attach 到 `document.body` 的容器，
 * 这样守卫可以像浏览器里那样对整个文档做一次查询，而不必逐组件穿透。
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

/** TESTIDS.field 的叶子选择器：路径 → data-testid 字符串（嵌套组递归展开）。 */
function allFieldSelectors(): Array<[string, string]> {
  const out: Array<[string, string]> = []
  const walk = (path: string, node: unknown) => {
    if (typeof node === 'string') {
      out.push([path, node])
      return
    }
    if (node && typeof node === 'object') {
      for (const [key, value] of Object.entries(node)) {
        walk(path ? `${path}.${key}` : key, value)
      }
    }
  }
  walk('', TESTIDS.field)
  return out
}

/** 当前 DOM 里所有已出现的字段级选择器（按叶子路径计）。 */
function foundFieldPaths(): Set<string> {
  const found = new Set<string>()
  for (const [path, id] of allFieldSelectors()) {
    if (document.querySelector(`[data-testid="${id}"]`)) found.add(path)
  }
  return found
}

function mergeFound(target: Set<string>, source: Set<string>) {
  for (const key of source) target.add(key)
}

/** 等到某个字段级选择器出现在 DOM 里（异步取数完成后才有）。 */
async function waitForField(id: string): Promise<void> {
  await vi.waitFor(() => {
    expect(document.querySelectorAll(`[data-testid="${id}"]`).length).toBeGreaterThan(0)
  })
}

/** 让已 resolve 的 promise 链跑完（组件里是 onMounted → await → 赋值）。 */
async function flush(): Promise<void> {
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

/** 按可见文案找按钮（在给定范围内）。 */
function buttonByText(scope: ParentNode, label: string): HTMLButtonElement | undefined {
  return [...scope.querySelectorAll('button')].find((button) =>
    (button.textContent ?? '').includes(label),
  )
}

const harness = createBlockHarness()
let pinia = createPinia()

/** 挂进一个 attach 到 document 的容器；所有区块共用同一个 Pinia。 */
function mountInto(component: unknown) {
  return harness.mount(component as never, { pinia })
}

beforeEach(() => {
  vi.clearAllMocks()
  harness.cleanup()
  pinia = createPinia()

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
  apiMocks.newsDigestApi.refresh.mockResolvedValue(fixtures.DIGEST_REFRESH)
  apiMocks.quantApi.getFactors.mockResolvedValue(fixtures.FACTORS_RESPONSE)
  apiMocks.quantApi.getPredictions.mockResolvedValue(fixtures.PREDICTIONS_RESPONSE)
  apiMocks.quantApi.getAccuracy.mockResolvedValue(fixtures.ACCURACY_RESPONSE)
  apiMocks.quantApi.getMonitor.mockResolvedValue(fixtures.MONITOR_RESPONSE)
  apiMocks.quantApi.getResearch.mockResolvedValue(fixtures.RESEARCH)
  apiMocks.quantApi.refresh.mockResolvedValue({
    success: true,
    message: '已抓取 7 个数据源',
    sources: fixtures.FACTORS_RESPONSE.sources,
    factor_status: {},
    predictions: fixtures.PREDICTIONS_RESPONSE.predictions,
    evaluations: fixtures.ACCURACY_RESPONSE.latest,
  })
  apiMocks.sourcesApi.getStatus.mockResolvedValue(fixtures.SOURCES)
  apiMocks.healthApi.getHealth.mockResolvedValue(fixtures.HEALTH)

  // AI 配置走的是裸 fetch('/health')，不是 axios —— 单独替身。
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ services: { ai_config: fixtures.HEALTH.services.ai_config } }),
    })),
  )
})

afterEach(() => {
  harness.cleanup()
  vi.unstubAllGlobals()
})

describe('字段覆盖：每个响应字段都有展示位', () => {
  // 这一个用例要挂载 7 个区块并等它们全部取数落定，默认 5 秒在并行跑全档时
  // 会被挤爆（表现为「Test timed out」，而不是真的少了展示位）。
  it('TESTIDS.field 的每个字段都能在页面上找到槽位', { timeout: 30_000 }, async () => {
    const [
      { default: ConclusionSection },
      { default: MarketSection },
      { default: DriversSection },
      { default: QuantSection },
      { default: StrategySection },
      { default: DataMethodsSection },
      { default: ResearchPage },
      { useMarketStore },
    ] = await Promise.all([
      import('@/views/dashboard/ConclusionSection.vue'),
      import('@/views/dashboard/MarketSection.vue'),
      import('@/views/dashboard/DriversSection.vue'),
      import('@/views/dashboard/QuantSection.vue'),
      import('@/views/dashboard/StrategySection.vue'),
      import('@/views/dashboard/DataMethodsSection.vue'),
      import('@/views/research/ResearchPage.vue'),
      import('@/stores/market'),
    ])

    // 行情区块读的是 store，不直接调 API —— 先把 store 喂满，
    // 否则 stats.* / daily.* / correlation.* / dollar.* 全都没有槽位。
    const marketStore = useMarketStore(pinia)
    marketStore.stats = fixtures.GOLD_STATS
    marketStore.dailyPrices = fixtures.DAILY
    marketStore.correlationData = fixtures.CORRELATION
    marketStore.dollarRealtime = fixtures.DOLLAR
    marketStore.statsLoading = false
    marketStore.dailyLoading = false
    marketStore.correlationLoading = false

    mountInto(ConclusionSection)
    mountInto(MarketSection)
    mountInto(DriversSection)
    mountInto(QuantSection)
    mountInto(StrategySection)
    mountInto(DataMethodsSection)
    mountInto(ResearchPage)

    // 等每个区块把夹具渲染出来，再开始盘点
    await waitForField('field-summary.core_view')
    await waitForField('field-stats.current_price')
    await waitForField('field-bullish.analysis_summary')
    await waitForField('field-digest.items.title')
    await waitForField('field-institutions.name')
    await waitForField('field-advice.strategy.title')
    await waitForField('field-quant.model_version')
    await waitForField('field-health.status')
    await waitForField('field-research.model_version')
    await flush()

    const found = foundFieldPaths()

    // 覆盖画像的 7 个字段逐个断言；夹具里两个因子分别覆盖
    // 「有缺口年」与「积累期」两种状态。
    for (const key of QUANT_FACTOR_COVERAGE_FIELDS) {
      expect(
        document.querySelectorAll(`[data-testid="${fieldTestId(`quant.factors.coverage.${key}`)}"]`)
          .length,
        `覆盖画像字段 ${key} 没有展示位`,
      ).toBeGreaterThan(0)
    }
    const sparseYears = [
      ...document.querySelectorAll(
        `[data-testid="${fieldTestId('quant.factors.coverage.sparse_years')}"]`,
      ),
    ]
    expect(
      sparseYears.some((node) => node.textContent?.includes('2017')),
      '缺口年没有展示 2017',
    ).toBe(true)
    const accumulating = [
      ...document.querySelectorAll(
        `[data-testid="${fieldTestId('quant.factors.coverage.accumulating')}"]`,
      ),
    ]
    expect(
      accumulating.some((node) => node.textContent?.includes('积累期')),
      '积累期徽标没有展示',
    ).toBe(true)

    // 降级分支：投资策略数据不足时随附的行情快照（advice.snapshot.*）
    apiMocks.investmentAdviceApi.getInvestmentAdvice.mockResolvedValue(fixtures.ADVICE_DEGRADED)
    mountInto(StrategySection)
    await waitForField('field-advice.snapshot.label')
    mergeFound(found, foundFieldPaths())

    // 刷新报告：量化（quant.refresh.*）与消息（digest.refresh.success）。
    // 用 DOM 里真实的按钮点击，而不是直接调 API —— 顺带证明按钮真的接上了。
    const quantSection = document.getElementById('quant')
    expect(quantSection, '量化预测节的锚点不见了').not.toBeNull()
    buttonByText(quantSection!, '重新抓取')?.click()
    await waitForField('field-quant.refresh.message')
    mergeFound(found, foundFieldPaths())

    buttonByText(document.body, '抓取最新消息')?.click()
    await waitForField('field-digest.refresh.success')
    mergeFound(found, foundFieldPaths())

    // 停发方向：切到 1 年尺度，direction_status=not_published 的分支才挂载
    const oneYearTab = [...quantSection!.querySelectorAll('[role="tab"]')].find((tab) =>
      tab.textContent?.includes('1 年'),
    )
    expect(oneYearTab, '量化预测节没有「1 年」尺度标签').toBeTruthy()
    ;(oneYearTab as HTMLElement).click()
    await waitForField('field-predictions.direction_reason')
    expect(
      document.querySelector(`[data-testid="${fieldTestId('predictions.direction_status')}"]`)
        ?.textContent,
    ).toContain('未发布')
    mergeFound(found, foundFieldPaths())

    const missing = allFieldSelectors()
      .map(([path]) => path)
      .filter((path) => !found.has(path))
    expect(missing, `以下字段没有展示位：\n  ${missing.join('\n  ')}`).toEqual([])
  })
})
