import type { InstitutionPrediction } from '@/services/api'
import { formatUsd } from '@/lib/format'

/**
 * 评级同时给符号与文字，颜色只是加强 —— 不让颜色单独承载语义。
 * 红涨绿跌，与价格方向一致。
 */
const RATING: Record<string, { label: string; symbol: string; tone: string }> = {
  bullish: { label: '看涨', symbol: '▲', tone: 'is-up' },
  bearish: { label: '看跌', symbol: '▼', tone: 'is-down' },
  neutral: { label: '中性', symbol: '—', tone: '' },
}

/**
 * 机构观点表：机构 / 评级 / 目标价 / 时间框架 / 理由。
 *
 * 目标价右对齐并统一为 `$5,400.00`；理由单元格里的补充要点收在 `<details>` 里，
 * 让表格保持可扫读。窄屏由外层的 .table-scroll 横向滚动。
 */
export default function InstitutionTable({
  institutions,
  testId,
}: {
  institutions: InstitutionPrediction[]
  testId?: string
}) {
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid={testId}>
        <thead>
          <tr>
            <th scope="col">机构</th>
            <th scope="col">评级</th>
            <th scope="col" className="num">
              目标价
            </th>
            <th scope="col">时间框架</th>
            <th scope="col">理由</th>
          </tr>
        </thead>
        <tbody>
          {institutions.map((institution) => {
            const rating = RATING[institution.rating] ?? RATING.neutral
            return (
              <tr key={institution.name}>
                <th scope="row">{institution.name}</th>
                <td className={rating.tone}>
                  <span aria-hidden="true">{rating.symbol}</span> {rating.label}
                </td>
                <td className="num">{formatUsd(institution.target_price)}</td>
                <td>{institution.timeframe}</td>
                <td>
                  {institution.reasoning}
                  {institution.key_points.length > 0 ? (
                    <details className="row-details">
                      <summary>要点（{institution.key_points.length}）</summary>
                      <ul>
                        {institution.key_points.map((point, index) => (
                          <li key={`${index}-${point}`}>{point}</li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
