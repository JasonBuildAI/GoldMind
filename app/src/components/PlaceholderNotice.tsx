import { PLACEHOLDER_NOTICE } from '@/lib/placeholder'

/**
 * 占位内容提示条。
 *
 * 只在接口明确表示「还在分析、这是占位内容」时渲染 —— 后端缓存未命中时会先返回
 * 一份结构与真实分析完全一样的内置内容，不看 metadata 就分辨不出来。
 */
export default function PlaceholderNotice({
  show,
  testId,
}: {
  show: boolean
  testId?: string
}) {
  if (!show) return null

  return (
    <span data-testid={testId} role="status" className="note">
      {PLACEHOLDER_NOTICE}
    </span>
  )
}
