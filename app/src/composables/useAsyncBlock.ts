import { describeApiError } from '@/lib/apiError'
import { ref, shallowRef, type Ref } from 'vue'

/**
 * 区块取数的统一形态：首次加载与「重新分析」分开计状态，
 * 失败一律翻译成人话（`describeApiError`），不把 axios 的错误对象摆到页面上。
 *
 * 为什么统一：原来每个区块各写一遍 `loading / refreshing / error` 三件套，
 * 12 个区块就是 12 份几乎一样的代码，改一处文案要改 12 遍。
 */
export interface AsyncBlock<T> {
  data: Ref<T | null>
  loading: Ref<boolean>
  refreshing: Ref<boolean>
  error: Ref<string | null>
  /** 首次加载（`refresh=false`）与显式刷新（`refresh=true`）走同一个入口 */
  load: (refresh?: boolean) => Promise<void>
}

export function useAsyncBlock<T>(
  fetcher: (refresh: boolean) => Promise<T>,
  options: { fallback: string; timeout?: string } = { fallback: '获取最新分析失败。' },
): AsyncBlock<T> {
  const data = shallowRef<T | null>(null)
  const loading = ref(true)
  const refreshing = ref(false)
  const error = ref<string | null>(null)

  async function load(refresh = false): Promise<void> {
    if (refresh) {
      refreshing.value = true
    } else {
      loading.value = true
    }
    error.value = null

    try {
      data.value = await fetcher(refresh)
    } catch (err) {
      error.value = describeApiError(err, options)
      data.value = null
    } finally {
      loading.value = false
      refreshing.value = false
    }
  }

  return { data, loading, refreshing, error, load }
}
