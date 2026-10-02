import { useCallback, useEffect, useState } from 'react'

import DataTable, { type Column } from '@/components/DataTable'
import PlaceholderNotice from '@/components/PlaceholderNotice'
import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import SignOff from '@/components/SignOff'
import StateBlock from '@/components/StateBlock'
import { useFreshnessBlock } from '@/contexts/FreshnessContext'
import { describeApiError } from '@/lib/apiError'
import { displayStamp, formatUsd } from '@/lib/format'
import { isPlaceholder } from '@/lib/placeholder'
import { marketSummaryApi, type MarketSummaryResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

interface SummaryData {
  raw: MarketSummaryResponse
  generatedAt: string
  placeholder: boolean
}

interface TargetRow {
  institution: string
  target: number
  probability: string
  timeframe: string
}

const TARGET_COLUMNS: ReadonlyArray<Column<TargetRow>> = [
  {
    key: 'institution',
    header: '机构',
    render: (row) => <span data-testid={fieldTestId('summary.institution_targets.institution')}>{row.institution}</span>,
  },
  {
    key: 'target',
    header: '目标价',
    numeric: true,
    source: '机构公开观点（模型整理）',
    render: (row) => (
      <span data-testid={fieldTestId('summary.institution_targets.target')}>
        {row.target ? formatUsd(row.target) : '—'}
      </span>
    ),
  },
  {
    key: 'probability',
    header: '置信度',
    render: (row) => (
      <span data-testid={fieldTestId('summary.institution_targets.probability')}>
        {row.probability || '—'}
      </span>
    ),
  },
  {
    key: 'timeframe',
    header: '时间框架',
    render: (row) => (
      <span data-testid={fieldTestId('summary.institution_targets.timeframe')}>
        {row.timeframe || '—'}
      </span>
    ),
  },
]

function PointGroup({ title, points, testId }: { title: string; points: string[]; testId: string }) {
  if (points.length === 0) return null
  return (
    <div>
      <h3 className="panel__title">{title}</h3>
      <ul className="point-list" data-testid={testId}>
        {points.map((point, index) => (
          <li key={`${index}-${point}`}>{point}</li>
        ))}
      </ul>
    </div>
  )
}

/**
 * 今日结论：全页第一屏的收束 —— 一行核心观点 + 关键数字，论据收进一层折叠。
 * 数字进表格；取不到就整段如实说明，不用写死的文案补位。
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
        placeholder: isPlaceholder(response.metadata),
      })
    } catch (err) {
      setError(
        describeApiError(err, {
          fallback: '获取最新分析失败。',
          timeout: '分析耗时较长，请稍后重试刷新。',
        }),
      )
      setData(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void fetchSummary()
  }, [fetchSummary])

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

  useFreshnessBlock(
    'conclusion',
    '今日结论',
    data?.placeholder ? 'analyzing' : error ? 'unavailable' : hasContent ? 'fresh' : 'pending',
    data?.generatedAt || null,
  )

  const refreshButton = (
    <RefreshButton onClick={() => void fetchSummary(true)} busy={refreshing} label="重新分析" />
  )

  let body
  if (!hasContent || !summary) {
    if (loading) {
      body = <StateBlock title="正在读取今日结论…" testId="conclusion-loading" />
    } else if (data?.placeholder) {
      body = (
        <StateBlock
          kind="analyzing"
          testId="conclusion-analyzing"
          title="今日结论正在分析中"
          detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置结论 —— 编造的判断与真实分析长得一样，用户分不出来。"
          actions={refreshButton}
        />
      )
    } else {
      body = (
        <StateBlock
          kind="unavailable"
          testId="conclusion-unavailable"
          title="今日结论暂不可用"
          detail={error ?? '没能取到分析结果。这里不显示任何内置结论 —— 与其摆一段编造的判断，不如如实说明取不到。'}
          actions={refreshButton}
        />
      )
    }
  } else {
    const metadata = summary.metadata
    const targets = (summary.institution_targets ?? []) as TargetRow[]

    body = (
      <div className="space-y-8" data-testid={TESTIDS.conclusionSummary}>
        <PlaceholderNotice show={data.placeholder} testId="conclusion-placeholder" />

        <p className="section__conclusion" data-testid={fieldTestId('summary.core_view')}>
          {summary.core_view || '—'}
        </p>

        <dl className="metrics">
          <div>
            <dt>当前价格</dt>
            <dd className="num" data-testid={fieldTestId('summary.current_price')}>
              {summary.current_price ? formatUsd(summary.current_price) : '—'}
            </dd>
          </div>
          <div>
            <dt>置信度</dt>
            <dd data-testid={fieldTestId('summary.confidence_level')}>
              {summary.confidence_level || '—'}
            </dd>
          </div>
          <div>
            <dt>时间框架</dt>
            <dd data-testid={fieldTestId('summary.time_horizon')}>{summary.time_horizon || '—'}</dd>
          </div>
          <div>
            <dt>投资建议</dt>
            <dd className="metrics__note" data-testid={fieldTestId('summary.investment_recommendation')}>
              {summary.investment_recommendation || '—'}
            </dd>
          </div>
        </dl>

        <details className="row-details" data-testid={TESTIDS.conclusionDetails}>
          <summary>展开论据：多空要点与综合判断</summary>
          <div className="grid gap-8 lg:grid-cols-3" style={{ marginTop: 12 }}>
            <PointGroup
              title="核心看涨逻辑"
              points={summary.core_bullish_logic ?? []}
              testId={fieldTestId('summary.core_bullish_logic')}
            />
            <PointGroup
              title="主要风险"
              points={summary.main_risks ?? []}
              testId={fieldTestId('summary.main_risks')}
            />
            <PointGroup
              title="市场共识"
              points={summary.market_consensus ?? []}
              testId={fieldTestId('summary.market_consensus')}
            />
          </div>

          {judgment && Object.values(judgment).some(Boolean) ? (
            <div className="doc-block">
              <h3 className="panel__title">综合判断</h3>
              {judgment.bullish_summary ? (
                <div className="doc-block">
                  <h4>看多理由</h4>
                  <p data-testid={fieldTestId('summary.comprehensive_judgment.bullish_summary')}>
                    {judgment.bullish_summary}
                  </p>
                </div>
              ) : null}
              {judgment.bearish_summary ? (
                <div className="doc-block">
                  <h4>看空理由</h4>
                  <p data-testid={fieldTestId('summary.comprehensive_judgment.bearish_summary')}>
                    {judgment.bearish_summary}
                  </p>
                </div>
              ) : null}
              {judgment.neutral_summary ? (
                <div className="doc-block">
                  <h4>中性观点</h4>
                  <p data-testid={fieldTestId('summary.comprehensive_judgment.neutral_summary')}>
                    {judgment.neutral_summary}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}

          {metadata ? (
            <div style={{ marginTop: 12 }}>
              <h3 className="panel__title">生成信息</h3>
              <dl className="metrics">
                <div>
                  <dt>状态</dt>
                  <dd data-testid={fieldTestId('metadata.status')}>{metadata.status ?? '—'}</dd>
                </div>
                <div>
                  <dt>缓存</dt>
                  <dd data-testid={fieldTestId('metadata.cached')}>
                    {metadata.cached === undefined ? '—' : metadata.cached ? '缓存' : '本次现算'}
                  </dd>
                </div>
                <div>
                  <dt>缓存来源</dt>
                  <dd data-testid={fieldTestId('metadata.cache_source')}>
                    {metadata.cache_source ?? '—'}
                  </dd>
                </div>
                <div>
                  <dt>提示</dt>
                  <dd data-testid={fieldTestId('metadata.message')}>{metadata.message ?? '—'}</dd>
                </div>
                <div>
                  <dt>生成时间</dt>
                  <dd data-testid={fieldTestId('metadata.generated_at')}>
                    {displayStamp(metadata.generated_at) ?? '—'}
                  </dd>
                </div>
                <div>
                  <dt>数据来源</dt>
                  <dd data-testid={fieldTestId('metadata.data_sources')}>
                    {metadata.data_sources?.join('、') || '—'}
                  </dd>
                </div>
                <div>
                  <dt>分析方法</dt>
                  <dd data-testid={fieldTestId('metadata.analysis_method')}>
                    {metadata.analysis_method ?? '—'}
                  </dd>
                </div>
              </dl>
            </div>
          ) : null}
        </details>

        {targets.length > 0 ? (
          <div className="panel">
            <h3 className="panel__title">目标价参考</h3>
            <div data-testid={TESTIDS.conclusionTargets}>
              <DataTable
                rows={targets}
                columns={TARGET_COLUMNS}
                rowKey={(row) => row.institution}
                caption="目标价来自机构公开观点（由模型整理），不是本页的价格预测；当前价格为行情数据。"
              />
            </div>
          </div>
        ) : null}

        {error ? <p className="panel__error">刷新失败：{error}</p> : null}

        <SignOff generatedAt={data.generatedAt} />
      </div>
    )
  }

  return (
    <Section
      id="conclusion"
      title="今日结论"
      intro="先读这一节：一行核心观点与关键数字；多空要点、综合判断与生成信息收在展开层里。"
      actions={refreshButton}
    >
      {body}
    </Section>
  )
}