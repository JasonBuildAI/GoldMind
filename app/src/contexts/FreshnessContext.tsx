import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

/**
 * 数据新鲜度：每个区块在取数成功后把自己「数据截至 / 分析时间 + 状态」登记进来，
 * 报头的新鲜度条统一展示。区块不直接渲染新鲜度条 —— 同一事实只有一个来源。
 */
export type FreshnessState = 'fresh' | 'analyzing' | 'stale' | 'unavailable' | 'pending'

export interface FreshnessEntry {
  key: string
  label: string
  /** 数据截至或分析时间；没有就不显示时间，不拿浏览器时钟顶替 */
  asOf: string | null
  state: FreshnessState
}

/** 新鲜度条的固定行序：没有登记过的区块显示「待更新」。 */
export const FRESHNESS_BLOCKS: ReadonlyArray<{ key: string; label: string }> = [
  { key: 'market', label: '行情' },
  { key: 'dollar', label: '美元指数' },
  { key: 'bullish', label: '看涨因素' },
  { key: 'bearish', label: '看跌因素' },
  { key: 'messages', label: '消息' },
  { key: 'institutions', label: '机构观点' },
  { key: 'quant', label: '量化预测' },
  { key: 'strategy', label: '投资策略' },
  { key: 'conclusion', label: '今日结论' },
]

export const FRESHNESS_STATE_LABEL: Record<FreshnessState, string> = {
  fresh: '已更新',
  analyzing: '分析中',
  stale: '陈旧',
  unavailable: '不可用',
  pending: '待更新',
}

interface FreshnessContextValue {
  entries: Record<string, FreshnessEntry>
  publish: (entry: FreshnessEntry) => void
}

const FreshnessContext = createContext<FreshnessContextValue | undefined>(undefined)

export function FreshnessProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<Record<string, FreshnessEntry>>({})

  const publish = useCallback((entry: FreshnessEntry) => {
    setEntries((prev) => {
      const old = prev[entry.key]
      if (
        old &&
        old.label === entry.label &&
        old.asOf === entry.asOf &&
        old.state === entry.state
      ) {
        return prev
      }
      return { ...prev, [entry.key]: entry }
    })
  }, [])

  const value = useMemo(() => ({ entries, publish }), [entries, publish])

  return <FreshnessContext.Provider value={value}>{children}</FreshnessContext.Provider>
}

export function useFreshness(): FreshnessContextValue {
  const context = useContext(FreshnessContext)
  if (context === undefined) {
    throw new Error('useFreshness must be used within a FreshnessProvider')
  }
  return context
}

/**
 * 区块登记自己的新鲜度；key 固定，见 FRESHNESS_BLOCKS。
 *
 * 没有 Provider 时静默跳过登记：区块本身不渲染新鲜度条（条在报头），
 * 因此单测里可以单独渲染区块，不必为它再包一层 Provider。
 */
export function useFreshnessBlock(
  key: string,
  label: string,
  state: FreshnessState,
  asOf: string | null,
): void {
  const context = useContext(FreshnessContext)
  useEffect(() => {
    context?.publish({ key, label, asOf, state })
  }, [context, key, label, state, asOf])
}

/** 顶层新鲜度状态：任一区块不可用/陈旧/未完成都会拉低整个看板的状态。 */
export function freshnessSummary(entries: Record<string, FreshnessEntry>): {
  state: FreshnessState
  label: string
} {
  const known = FRESHNESS_BLOCKS.map((block) => entries[block.key]).filter(
    (entry): entry is FreshnessEntry => Boolean(entry),
  )
  if (known.some((entry) => entry.state === 'unavailable')) {
    return { state: 'unavailable', label: '部分数据不可用' }
  }
  if (known.some((entry) => entry.state === 'analyzing' || entry.state === 'pending')) {
    return { state: 'analyzing', label: '部分数据加载中' }
  }
  if (known.some((entry) => entry.state === 'stale')) {
    return { state: 'stale', label: '部分数据陈旧' }
  }
  return { state: 'fresh', label: '数据已更新' }
}