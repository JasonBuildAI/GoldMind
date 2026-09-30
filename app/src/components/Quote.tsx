import { formatPercent, trendOf } from '@/lib/format'

/**
 * 一条报价：名称、数值、涨跌与来源。
 * 涨跌同时给符号（▲▼）与文字（涨/跌），颜色只是加强 —— 不让颜色单独承载语义。
 */
export default function Quote({
  label,
  value,
  change,
  changeNote,
  meta,
  title,
}: {
  label: string
  value: string
  change?: number
  changeNote?: string
  meta?: string
  title?: string
}) {
  const trend = change === undefined ? null : trendOf(change)

  return (
    <div className="quote" title={title}>
      <div className="quote__label">{label}</div>
      <div className="quote__value">{value}</div>
      {trend && change !== undefined ? (
        <div
          className={
            change > 0 ? 'quote__change is-up' : change < 0 ? 'quote__change is-down' : 'quote__change'
          }
        >
          <span aria-hidden="true">{trend.symbol}</span> {formatPercent(change)}
          <span>（{trend.label}{changeNote ? `，${changeNote}` : ''}）</span>
        </div>
      ) : null}
      {meta ? <div className="quote__meta">{meta}</div> : null}
    </div>
  )
}
