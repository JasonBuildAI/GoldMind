import { useFreshnessStore, type FreshnessState } from '@/stores/freshness'
import { toValue, watch, type MaybeRefOrGetter } from 'vue'

/**
 * 区块登记自己的新鲜度；key 固定，见 `FRESHNESS_BLOCKS`。
 *
 * 区块本身不渲染新鲜度条（条在报头），所以没有 Pinia 实例时静默跳过登记 ——
 * 单测里可以单独挂载一个区块，不必为它再装一层 store。
 */
export function useFreshnessBlock(
  key: string,
  label: MaybeRefOrGetter<string>,
  state: MaybeRefOrGetter<FreshnessState>,
  asOf: MaybeRefOrGetter<string | null>,
): void {
  let store: ReturnType<typeof useFreshnessStore> | null = null
  try {
    store = useFreshnessStore()
  } catch {
    store = null
  }
  if (!store) return

  watch(
    [() => toValue(label), () => toValue(state), () => toValue(asOf)],
    ([labelValue, stateValue, asOfValue]) => {
      store!.publish({ key, label: labelValue, state: stateValue, asOf: asOfValue })
    },
    { immediate: true },
  )
}
