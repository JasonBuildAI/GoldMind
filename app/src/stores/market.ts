import { describeApiError } from '@/lib/apiError'
import {
  goldApi,
  type CorrelationData,
  type DailyPrice,
  type DollarRealtime,
  type GoldStats,
} from '@/services/api'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/**
 * 行情数据：金价统计、日线、金价 / 美元相关性、实时美元指数。
 *
 * 行为与原来的 `GoldDataContext` 逐条一致，只是换成 Pinia store：
 *   - 30 秒轮询，页面隐藏时跳过本轮，切回来立即补一次；
 *   - 5 秒缓存窗口：短时间内重复调用不重复请求；
 *   - 「上次取值时间」存在普通变量里，不参与响应式 —— 它是缓存判据，
 *     不是渲染数据。放响应式里会让每次取数都触发一轮额外的渲染。
 */
const CACHE_DURATION = 5000

// 轮询间隔（毫秒）。从 10 秒放宽到 30 秒：一个打开的看板原先每 10 秒
// 拉 stats / daily / correlation / dollar 各一次（外加首屏约 15 个区块请求），
// 首分钟就逼近后端 60 次/分钟的限流上限；一旦 429，整片报错。
// 30 秒档位下空闲请求 ≤ 8 次/分钟。
export const POLL_INTERVAL = 30000

/** 标签页被切到后台时跳过本轮 —— 没人看的数据不值得占用限流额度。 */
export function isPageHidden(): boolean {
  return typeof document !== 'undefined' && document.hidden
}

export const useMarketStore = defineStore('market', () => {
  // ---- 金价统计 -------------------------------------------------------- //
  const stats = ref<GoldStats | null>(null)
  const statsLoading = ref(false)
  const statsError = ref<string | null>(null)
  let statsLastFetch = 0

  // ---- 日线 ------------------------------------------------------------ //
  const dailyPrices = ref<DailyPrice[]>([])
  const dailyLoading = ref(false)
  const dailyError = ref<string | null>(null)
  let dailyLastFetch = 0

  // ---- 金价 / 美元相关性 ----------------------------------------------- //
  const correlationData = ref<CorrelationData[]>([])
  const correlationLoading = ref(false)
  const correlationError = ref<string | null>(null)
  let correlationLastFetch = 0

  // ---- 实时美元指数 ---------------------------------------------------- //
  const dollarRealtime = ref<DollarRealtime | null>(null)

  const lastUpdated = ref<Date | null>(null)

  /** 取金价统计。`force` 绕过 5 秒缓存窗口。 */
  async function refreshStats(force = false): Promise<void> {
    const now = Date.now()
    if (!force && now - statsLastFetch < CACHE_DURATION) return

    statsLoading.value = true
    statsError.value = null
    try {
      stats.value = await goldApi.getStats()
      statsLastFetch = now
      lastUpdated.value = new Date()
    } catch (err) {
      // 统一翻译：固定写「获取统计数据失败」会把 429 限流、后端 503、
      // 断网都显示成同一句，用户既不知道发生了什么，也不知道该做什么。
      statsError.value = describeApiError(err, { fallback: '获取统计数据失败。' })
      console.error('Failed to fetch stats:', err)
    } finally {
      statsLoading.value = false
    }
  }

  /**
   * 用实时价替换相关性序列的最后一个点 —— **仅当行情自带的交易日
   * 与最后一点是同一天**。
   *
   * 用 `dollarRealtime.date`（数据源给出的交易日）比较，不要用
   * `new Date().toISOString()`：那是 UTC 日期，东八区 00:00-08:00 之间
   * 算出来的是昨天，实时美元指数就静默地不更新了。
   *
   * 日期不匹配时**不追加**数据点：那会造出「旧金价 + 新美元指数」的假点，
   * 误导对金价/美元负相关关系的判断。实时值已由 `dollarRealtime` 单独暴露。
   */
  function patchLastCorrelationPoint(quote: DollarRealtime): void {
    const rows = correlationData.value
    if (!rows.length || !quote.date) return
    const lastIndex = rows.length - 1
    if (rows[lastIndex].date !== quote.date) return
    correlationData.value = rows.map((row, index) =>
      index === lastIndex ? { ...row, dollar_index: quote.price } : row,
    )
  }

  /** 取图表数据（日线 + 相关性，各自按缓存窗口判定）。 */
  async function refreshCharts(force = false): Promise<void> {
    const now = Date.now()
    const shouldFetchDaily = force || now - dailyLastFetch >= CACHE_DURATION
    const shouldFetchCorrelation = force || now - correlationLastFetch >= CACHE_DURATION
    if (!shouldFetchDaily && !shouldFetchCorrelation) return

    dailyLoading.value = shouldFetchDaily
    correlationLoading.value = shouldFetchCorrelation
    dailyError.value = null
    correlationError.value = null

    try {
      const [daily, correlation] = await Promise.all([
        shouldFetchDaily ? goldApi.getDailyPrices() : Promise.resolve(null),
        shouldFetchCorrelation ? goldApi.getCorrelation() : Promise.resolve(null),
      ])

      if (daily) {
        dailyPrices.value = daily
        dailyLastFetch = now
      }

      if (correlation) {
        correlationData.value = correlation
        correlationLastFetch = now
        // 实时美元指数取不到不影响历史序列：失败只记一条警告。
        try {
          const quote = await goldApi.getDollarRealtime()
          dollarRealtime.value = quote
          patchLastCorrelationPoint(quote)
        } catch (dollarErr) {
          console.warn('获取实时美元指数失败，使用历史数据:', dollarErr)
        }
      }

      lastUpdated.value = new Date()
    } catch (err) {
      const message = describeApiError(err, { fallback: '获取图表数据失败。' })
      dailyError.value = message
      correlationError.value = message
      console.error('Failed to fetch chart data:', err)
    } finally {
      dailyLoading.value = false
      correlationLoading.value = false
    }
  }

  /** 强制刷新全部行情数据（手动「刷新」按钮）。 */
  async function refreshAll(): Promise<void> {
    await Promise.all([refreshStats(true), refreshCharts(true)])
  }

  /** 单独刷新实时美元指数，并同步相关性序列的末点。 */
  async function refreshDollarRealtime(): Promise<void> {
    try {
      const quote = await goldApi.getDollarRealtime()
      dollarRealtime.value = quote
      patchLastCorrelationPoint(quote)
      lastUpdated.value = new Date()
    } catch (err) {
      console.warn('[market store] 获取实时美元指数失败:', err)
    }
  }

  /**
   * 启动轮询。返回停止函数，调用方（页面根组件）在卸载时调用。
   *
   * 初始加载与轮询分开：初始加载只跑一次，轮询走同一个 tick，
   * 页面隐藏时跳过、切回来补一次。
   */
  function startPolling(): () => void {
    void refreshStats()
    void refreshCharts()
    void refreshDollarRealtime()

    const tick = () => {
      if (isPageHidden()) return
      void refreshStats(true)
      void refreshCharts(true)
      void refreshDollarRealtime()
    }

    const interval = setInterval(tick, POLL_INTERVAL)
    // 切回来的那一刻补一次：不必干等下一个 30 秒，用户看到的是新数据
    const onVisibilityChange = () => {
      if (!isPageHidden()) tick()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }

  const hasAnyError = computed(() => Boolean(statsError.value || dailyError.value || correlationError.value))

  return {
    stats,
    statsLoading,
    statsError,
    dailyPrices,
    dailyLoading,
    dailyError,
    correlationData,
    correlationLoading,
    correlationError,
    dollarRealtime,
    lastUpdated,
    hasAnyError,
    refreshStats,
    refreshCharts,
    refreshAll,
    refreshDollarRealtime,
    startPolling,
  }
})
