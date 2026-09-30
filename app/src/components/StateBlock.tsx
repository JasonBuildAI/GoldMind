import type { ReactNode } from 'react'

export type StateKind = 'loading' | 'analyzing' | 'unavailable'

/**
 * 加载 / 正在分析 / 不可用三种状态的统一呈现。
 *
 * 「不可用」必须说清原因与下一步；「正在分析」必须说明当前内容不是本次分析结果。
 * 这里只负责显示，判定逻辑在各区块（依据 lib/placeholder.ts 与后端 metadata）。
 */
export default function StateBlock({
  kind = 'loading',
  title,
  detail,
  actions,
  testId,
}: {
  kind?: StateKind
  title: string
  detail?: string
  actions?: ReactNode
  testId?: string
}) {
  return (
    <div
      className={kind === 'analyzing' ? 'state state--analyzing' : 'state'}
      data-testid={testId}
      role="status"
    >
      <p className="state__title">{title}</p>
      {detail ? <p className="state__detail">{detail}</p> : null}
      {actions ? <div className="state__actions">{actions}</div> : null}
    </div>
  )
}
