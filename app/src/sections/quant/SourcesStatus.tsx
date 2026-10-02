import { displayStamp } from '@/lib/format'
import type { QuantFactorsResponse } from '@/services/api'
import { fieldTestId } from '@/testids'
import { statusLabel, statusTag } from './shared'

const field = fieldTestId

/**
 * 量化数据源状态与同步报告：收进一层折叠，不占主版面。
 * 「未到期」表示本轮按各源的最小间隔跳过，不是失败 —— 状态词照后端显示。
 */
export default function SourcesStatus({ factors }: { factors: QuantFactorsResponse }) {
  const okSources = factors.sources.filter((source) => source.status === 'ok').length
  const failed = factors.sources.filter((source) => source.status === 'error')

  return (
    <details className="row-details" data-testid="quant-sources-details">
      <summary>
        数据源状态（{okSources}/{factors.sources.length} 正常，展开看逐个源与同步报告）
      </summary>

      {failed.length > 0 ? (
        <p className="panel__error">
          数据源不可用：
          {failed
            .map((source) => `${source.label ?? source.name}（${source.error ?? '原因未知'}）`)
            .join('；')}
        </p>
      ) : null}

      <p className="panel__meta">
        <span>同步完成 {displayStamp(factors.sync.finished_at) ?? '—'}</span>
        <span className="note">「未到期」表示本轮按各源的最小间隔跳过，不是失败；同步报告见「数据与方法」。</span>
      </p>

      {factors.sources.length > 0 ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">数据源</th>
                <th scope="col">状态</th>
                <th scope="col">说明</th>
              </tr>
            </thead>
            <tbody>
              {factors.sources.map((source) => (
                <tr key={source.name}>
                  <th scope="row">
                    <span data-testid={field('quant.source.label')}>{source.label ?? source.name}</span>
                    <span className="note" data-testid={field('quant.source.name')}>
                      {source.name}
                    </span>
                  </th>
                  <td>
                    <span data-testid={field('quant.source.status')}>{statusLabel(source.status)}</span>
                    {statusTag(source.status)}
                  </td>
                  <td className="note">
                    <span data-testid={field('quant.source.error')}>
                      {source.error ?? '—'}
                    </span>
                    <span className="note" data-testid={field('quant.source.reason')}>
                      {source.reason ?? '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="note">还没有同步记录 —— 点右上角「重新抓取」跑一轮。</p>
      )}
    </details>
  )
}