import type { InstitutionPrediction } from '@/services/api'
import { formatUsd } from '@/lib/format'
import { fieldTestId } from '@/testids'

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
 * 机构观点表：机构 / 评级 / 目标价 / 时间框架 / 预测日期 / 线索来源 / 理由。
 *
 * 目标价右对齐并统一为 `$5,400.00`；理由单元格里的补充要点收在 `<details>` 里。
 * 「预测日期」= 该预测最近一次被核实/抓取入库的日期，超过 30 天如实标注滞后天数。
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
            <th scope="col">预测日期</th>
            <th scope="col">线索来源</th>
            <th scope="col">理由</th>
          </tr>
        </thead>
        <tbody>
          {institutions.map((institution) => {
            const rating = RATING[institution.rating] ?? RATING.neutral
            return (
              <tr key={institution.name} data-testid={`institution-${institution.name}`}>
                <th scope="row" data-testid={fieldTestId('institutions.name')}>
                  {institution.logo ? (
                    <img
                      className="institution__logo"
                      src={institution.logo}
                      alt=""
                      data-testid={fieldTestId('institutions.logo')}
                    />
                  ) : (
                    <span hidden data-testid={fieldTestId('institutions.logo')} />
                  )}
                  {institution.name}
                </th>
                <td className={rating.tone} data-testid={fieldTestId('institutions.rating')}>
                  <span aria-hidden="true">{rating.symbol}</span> {rating.label}
                </td>
                <td className="num" data-testid={fieldTestId('institutions.target_price')}>
                  {formatUsd(institution.target_price)}
                </td>
                <td data-testid={fieldTestId('institutions.timeframe')}>
                  {institution.timeframe || '—'}
                </td>
                <td data-testid={fieldTestId('institutions.as_of_date')}>
                  {institution.as_of_date ?? '—'}
                  {(institution.stale_days ?? 0) > 30 ? (
                    <span className="note" data-testid={fieldTestId('institutions.stale_days')}>
                      （已滞后 {institution.stale_days} 天）
                    </span>
                  ) : null}
                </td>
                <td className="note" data-testid={fieldTestId('institutions.source')}>
                  {institution.source ?? '—'}
                </td>
                <td data-testid={fieldTestId('institutions.reasoning')}>
                  {institution.reasoning}
                  {institution.key_points.length > 0 ? (
                    <details className="row-details" data-testid={fieldTestId('institutions.key_points')}>
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