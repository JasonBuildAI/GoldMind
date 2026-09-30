import { useCallback, useEffect, useState } from 'react'

import PlaceholderNotice from '@/components/PlaceholderNotice'
import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import SignOff from '@/components/SignOff'
import StateBlock from '@/components/StateBlock'
import { describeApiError } from '@/lib/apiError'
import { formatUsd } from '@/lib/format'
import { isPlaceholder } from '@/lib/placeholder'
import { marketSummaryApi, type MarketSummaryResponse } from '@/services/api'

interface SummaryData {
  raw: MarketSummaryResponse
  generatedAt: string
  placeholder: boolean
}

/** 三栏：核心看涨逻辑 / 主要风险 / 市场共识。 */
function Points({ title, points }: { title: string; points: string[] }) {
  if (points.length === 0) return null
  return (
    <div className="panel">
      <h3 className="panel__title">{title}</h3>
      <ul className="point-list">
        {points.map((point, index) => (
          <li key={`${index}-${point}`}>{point}</li>
        ))}
      </ul>
    </div>
  )
}

/**
 * 市场总结：三栏要点 + 综合判断 + 核心观点 + 风险提示与免责声明。
 *
 * 每段逐项判空：接口没给哪一段就不渲染哪一段，不用写死的文案补位
 * （取不到价格时尤其不摆「当前价格」）。
 */
export default function Conclusion() {
  const [data, setData] = useState<SummaryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSummary = useCallback(async (refresh = false) => {
    if (refresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const response = await marketSummaryApi.getMarketSummary(refresh)
      setData({
        raw: response,
        generatedAt: response.metadata?.generated_at ?? '',
        // 市场总结用 cache_source === 'default' 标记占位内容（其余区块用 status）。
        placeholder: isPlaceholder(response.metadata),
      })
    } catch (err) {
      setError(
        describeApiError(err, {
          fallback: '获取最新分析失败。',
          timeout: '分析耗时较长，请稍后重试刷新。',
        }),
      )
      // 不填充任何编造的结论或数字：保持为空，由下面的空状态如实说明。
      setData(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void fetchSummary()
  }, [fetchSummary])

  const refreshButton = (
    <RefreshButton onClick={() => void fetchSummary(true)} busy={refreshing} label="重新分析" />
  )

  const summary = data?.raw
  const judgment = summary?.comprehensive_judgment
  const hasContent = Boolean(
    summary &&
      (summary.core_bullish_logic?.length ||
        summary.main_risks?.length ||
        summary.market_consensus?.length ||
        summary.institution_targets?.length ||
        summary.core_view ||
        summary.investment_recommendation ||
        summary.confidence_level ||
        summary.time_horizon ||
        (judgment && Object.values(judgment).some(Boolean))),
  )

  let body

  if (!hasContent || !summary) {
    if (loading) {
      body = <StateBlock title="正在读取市场总结…" testId="conclusion-loading" />
    } else if (data?.placeholder) {
      body = (
        <StateBlock
          kind="analyzing"
          testId="conclusion-analyzing"
          title="市场总结正在分析中"
          detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置结论 —— 编造的判断与真实分析长得一样，用户分不出来。"
        />
      )
    } else {
      body = (
        <StateBlock
          kind="unavailable"
          testId="conclusion-unavailable"
          title="市场总结暂不可用"
          detail={error ?? '没能取到分析结果。这里不显示任何内置结论 —— 与其摆一段编造的判断，不如如实说明取不到。'}
        />
      )
    }
  } else {
    const targets = summary.institution_targets ?? []

    body = (
      <div className="space-y-8">
        <PlaceholderNotice show={data.placeholder} testId="conclusion-placeholder" />

        <div className="grid gap-8 lg:grid-cols-3">
          <Points title="核心看涨逻辑" points={summary.core_bullish_logic ?? []} />
          <Points title="主要风险" points={summary.main_risks ?? []} />
          <Points title="市场共识" points={summary.market_consensus ?? []} />
        </div>

        {judgment && Object.values(judgment).some(Boolean) ? (
          <div className="panel">
            <h3 className="panel__title">综合判断</h3>
            {judgment.bullish_summary ? (
              <div className="doc-block">
                <h4>看多理由</h4>
                <p>{judgment.bullish_summary}</p>
              </div>
            ) : null}
            {judgment.bearish_summary ? (
              <div className="doc-block">
                <h4>看空理由</h4>
                <p>{judgment.bearish_summary}</p>
              </div>
            ) : null}
            {judgment.neutral_summary ? (
              <div className="doc-block">
                <h4>中性观点</h4>
                <p>{judgment.neutral_summary}</p>
              </div>
            ) : null}
          </div>
        ) : null}

        {summary.core_view || summary.investment_recommendation ? (
          <div className="panel">
            <h3 className="panel__title">核心观点</h3>
            {summary.core_view ? <p className="lead">{summary.core_view}</p> : null}
            <dl className="metrics">
              {summary.investment_recommendation ? (
                <div>
                  <dt>投资建议</dt>
                  <dd className="metrics__note">{summary.investment_recommendation}</dd>
                </div>
              ) : null}
              {summary.confidence_level ? (
                <div>
                  <dt>置信度</dt>
                  <dd>{summary.confidence_level}</dd>
                </div>
              ) : null}
              {summary.time_horizon ? (
                <div>
                  <dt>时间框架</dt>
                  <dd>{summary.time_horizon}</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}

        {targets.length > 0 ? (
          <div className="panel">
            <h3 className="panel__title">目标价参考</h3>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">机构</th>
                    <th scope="col" className="num">
                      目标价
                    </th>
                    <th scope="col">置信度</th>
                    <th scope="col">时间框架</th>
                  </tr>
                </thead>
                <tbody>
                  {targets.map((item) => (
                    <tr key={item.institution}>
                      <th scope="row">{item.institution}</th>
                      <td className="num">{formatUsd(item.target)}</td>
                      <td>{item.probability || '—'}</td>
                      <td>{item.timeframe || '—'}</td>
                    </tr>
                  ))}
                  {summary.current_price ? (
                    <tr>
                      <th scope="row">当前价格</th>
                      <td className="num">{formatUsd(summary.current_price)}</td>
                      <td>—</td>
                      <td>实时</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <p className="provenance">
              目标价来自机构公开观点（由模型整理），不是本页的价格预测；当前价格取自行情数据。
            </p>
          </div>
        ) : null}

        {error ? <p className="panel__error">刷新失败：{error}</p> : null}

        <div className="panel">
          <h3 className="panel__title">风险提示与免责声明</h3>
          <p className="strategy__lead">
            黄金价格受多种因素影响，波动较大。本页分析由模型基于公开新闻与行情数据整理，可能滞后或不准确；
            数据取不到时页面会如实说明，不用内置数字替代。
          </p>
          <p className="strategy__lead" style={{ marginBottom: 0 }}>
            本页面内容仅供参考，不构成投资建议。投资有风险，入市需谨慎。过往表现不代表未来收益。
          </p>
        </div>

        <SignOff generatedAt={data.generatedAt} />
      </div>
    )
  }

  return (
    <Section
      id="conclusion"
      title="总结"
      intro="多空要点、市场共识与综合判断的收束，附风险提示与免责声明。"
      actions={refreshButton}
    >
      {body}
    </Section>
  )
}
