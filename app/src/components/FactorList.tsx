import type { ReactNode } from 'react'

import { fieldTestId } from '@/testids'

/** 因子条目在两个方向上的结构一致，这里只声明界面真正会用到的字段。 */
export interface Factor {
  id: string
  title: string
  subtitle: string
  description: string
  details: string[]
  impact: string
}

const IMPACT_LABEL: Record<string, string> = {
  high: '高影响',
  medium: '中影响',
  low: '低影响',
}

/**
 * 因子列表：一条因子一行，点开看要点。
 *
 * 用原生 `<details>` —— 键盘、屏幕阅读器与打印都直接可用，不必为「展开」
 * 再写一遍无障碍逻辑。影响程度只给文字（高/中/低），不靠颜色区分。
 * fieldPrefix 决定字段级 testid（bullish.items.* / bearish.items.*）。
 */
export default function FactorList({
  factors,
  fieldPrefix,
}: {
  factors: Factor[]
  fieldPrefix: 'bullish' | 'bearish'
}): ReactNode {
  return (
    <ul className="factors">
      {factors.map((factor) => (
        <li key={factor.id} className="factor" data-testid={`${fieldPrefix}-factor-${factor.id}`}>
          <details>
            <summary>
              <span className="factor__title" data-testid={fieldTestId(`${fieldPrefix}.items.title`)}>
                {factor.title}
              </span>
              <span className="tag" data-testid={fieldTestId(`${fieldPrefix}.items.impact`)}>
                {IMPACT_LABEL[factor.impact] ?? '中影响'}
              </span>
              <span
                className="factor__subtitle"
                data-testid={fieldTestId(`${fieldPrefix}.items.subtitle`)}
              >
                {factor.subtitle}
              </span>
            </summary>
            <div className="factor__body">
              <p data-testid={fieldTestId(`${fieldPrefix}.items.description`)}>
                {factor.description}
              </p>
              <p className="note">
                编号 <span data-testid={fieldTestId(`${fieldPrefix}.items.id`)}>{factor.id}</span>
              </p>
              {factor.details.length > 0 ? (
                <ul data-testid={fieldTestId(`${fieldPrefix}.items.details`)}>
                  {factor.details.map((detail, index) => (
                    <li key={`${index}-${detail}`}>{detail}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          </details>
        </li>
      ))}
    </ul>
  )
}