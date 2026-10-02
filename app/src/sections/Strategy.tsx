import { useCallback, useEffect, useState } from 'react'

import DataTable, { type Column } from '@/components/DataTable'
import MetadataBlock from '@/components/MetadataBlock'
import PlaceholderNotice from '@/components/PlaceholderNotice'
import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import SignOff from '@/components/SignOff'
import StateBlock from '@/components/StateBlock'
import StrategyColumns from '@/components/StrategyColumns'
import { useFreshnessBlock } from '@/contexts/FreshnessContext'
import { describeApiError } from '@/lib/apiError'
import { formatPercent, formatUsd } from '@/lib/format'
import { isPlaceholder, type ApiMetadata } from '@/lib/placeholder'
import {
  investmentAdviceApi,
  type AdvicePriceSnapshot,
  type CorePrinciple,
  type InvestmentStrategy,
  type MarketAssessment,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

const RISK_LABEL: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

interface AdviceData {
  assessment: MarketAssessment | null
  strategies: InvestmentStrategy[]
  principles: CorePrinciple[]
  riskWarning: string
  disclaimer: string
  analysisStatus: string
  generatedAt: string
  placeholder: boolean
  degraded: boolean
  priceSnapshot: AdvicePriceSnapshot | null
  metadata: ApiMetadata | null
}

const PRINCIPLE_COLUMNS: ReadonlyArray<Column<CorePrinciple>> = [
  {
    key: 'title',
    header: '原则',
    render: (row) => <span data-testid={fieldTestId('advice.principles.title')}>{row.title}</span>,
  },
  {
    key: 'description',
    header: '说明',
    render: (row) => (
      <span data-testid={fieldTestId('advice.principles.description')}>{row.description}</span>
    ),
  },
]

/** 行情快照：数据不足降级时后端随附的确定性统计（不是模型输出）。 */
function SnapshotTable({ snapshot }: { snapshot: AdvicePriceSnapshot }) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <tbody>
          {(
            [
              ['标签', snapshot.label, 'advice.snapshot.label'],
              ['窗口起', snapshot.window_start, 'advice.snapshot.window_start'],
              ['窗口末', snapshot.window_end, 'advice.snapshot.window_end'],
              ['最新价', formatUsd(snapshot.latest_price), 'advice.snapshot.latest_price'],
              ['区间涨跌', formatPercent(snapshot.change_pct), 'advice.snapshot.change_pct'],
              ['期间最高', formatUsd(snapshot.high), 'advice.snapshot.high'],
              ['期间最低', formatUsd(snapshot.low), 'advice.snapshot.low'],
              ['高低振幅', formatPercent(snapshot.amplitude_pct), 'advice.snapshot.amplitude_pct'],
              ['完整窗口', snapshot.full_window ? '是（窗口数据齐全）' : '否（窗口不完整）', 'advice.snapshot.full_window'],
            ] as const
          ).map(([label, value, path]) => (
            <tr key={path}>
              <th scope="row">{label}</th>
              <td className="num" data-testid={fieldTestId(path)}>
                {value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * 投资策略：市场评估 + 保守 / 均衡 / 机会三档横向对照 + 执行原则。
 * 三档策略来自同一次分析，字段一样，读的时候可以横向比；取不到就整段留白。
 */
export default function Strategy() {
  const [data, setData] = useState<AdviceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchAdvice = useCallback(async (refresh = false) => {
    if (refresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const response = await investmentAdviceApi.getInvestmentAdvice(refresh)
      setData({
        assessment: response.market_assessment ?? null,
        strategies: response.strategies ?? [],
        principles: response.core_principles ?? [],
        riskWarning: response.risk_warning ?? '',
        disclaimer: response.disclaimer ?? '',
        analysisStatus: response.analysis_status ?? response.metadata?.status ?? '',
        generatedAt: response.metadata?.generated_at ?? '',
        placeholder: isPlaceholder(response.metadata),
        degraded:
          response.metadata?.status === 'insufficient_data' ||
          response.analysis_status === 'insufficient_data',
        priceSnapshot: response.price_snapshot ?? null,
        metadata: response.metadata ?? null,
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
    void fetchAdvice()
  }, [fetchAdvice])

  const assessment =
    data?.assessment && Object.keys(data.assessment).length > 0 ? data.assessment : null
  const hasContent = Boolean(
    data && (data.strategies.length > 0 || data.principles.length > 0 || assessment),
  )

  useFreshnessBlock(
    'strategy',
    '投资策略',
    data?.degraded
      ? 'stale'
      : data?.placeholder
        ? 'analyzing'
        : error || !hasContent
          ? 'unavailable'
          : 'fresh',
    data?.generatedAt || null,
  )

  const refreshButton = (
    <RefreshButton onClick={() => void fetchAdvice(true)} busy={refreshing} label="重新分析" />
  )

  let body
  if (data && data.degraded) {
    body = (
      <div className="space-y-8">
        <StateBlock
          kind="unavailable"
          testId="strategy-insufficient"
          title="数据不足，暂不生成策略"
          detail={data.riskWarning || '缺少可分析的数据输入，未调用模型。'}
        />
        {data.priceSnapshot ? (
          <div className="panel">
            <h3 className="panel__title">行情统计（仅供参考，全部字段）</h3>
            <SnapshotTable snapshot={data.priceSnapshot} />
          </div>
        ) : null}
        <MetadataBlock metadata={data.metadata} />
        <SignOff generatedAt={data.generatedAt} />
      </div>
    )
  } else if (!data || !hasContent) {
    if (loading) {
      body = <StateBlock title="正在读取投资策略…" testId="strategy-loading" />
    } else if (data?.placeholder) {
      body = (
        <StateBlock
          kind="analyzing"
          testId="strategy-analyzing"
          title="投资策略正在分析中"
          detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一套内置策略 —— 编造的建议与真实分析长得一样，用户分不出来。"
          actions={refreshButton}
        />
      )
    } else {
      body = (
        <StateBlock
          kind="unavailable"
          testId="strategy-unavailable"
          title="投资策略暂不可用"
          detail={error ?? '没能取到分析结果。这里不显示任何内置策略 —— 与其摆一套编造的建议，不如如实说明取不到。'}
          actions={refreshButton}
        />
      )
    }
  } else {
    body = (
      <div className="space-y-8">
        <PlaceholderNotice show={data.placeholder} testId="strategy-placeholder" />

        {assessment ? (
          <>
            <p className="section__conclusion">{assessment.current_position || '市场评估见下表。'}</p>
            <dl className="metrics">
              <div>
                <dt>当前位置</dt>
                <dd data-testid={fieldTestId('advice.assessment.current_position')}>
                  {assessment.current_position || '—'}
                </dd>
              </div>
              <div>
                <dt>风险等级</dt>
                <dd data-testid={fieldTestId('advice.assessment.risk_level')}>
                  {RISK_LABEL[assessment.risk_level] ?? '未知'}（{assessment.risk_level}）
                </dd>
              </div>
              <div>
                <dt>建议策略</dt>
                <dd data-testid={fieldTestId('advice.assessment.recommended_approach')}>
                  {assessment.recommended_approach || '—'}
                </dd>
              </div>
              <div>
                <dt>关键考量</dt>
                <dd
                  className="metrics__note"
                  data-testid={fieldTestId('advice.assessment.key_considerations')}
                >
                  {assessment.key_considerations.join('；') || '—'}
                </dd>
              </div>
            </dl>
          </>
        ) : null}

        {data.strategies.length > 0 ? (
          <StrategyColumns strategies={data.strategies} testId={TESTIDS.strategyColumns} />
        ) : null}

        {data.strategies.length > 0 ? (
          <p className="provenance">
            仓位、区间与止盈止损是模型的建议，不是收益承诺；三档字段同名同序，可横向对照。
          </p>
        ) : null}

        {data.principles.length > 0 ? (
          <div className="panel">
            <h3 className="panel__title">执行原则</h3>
            <DataTable rows={data.principles} columns={PRINCIPLE_COLUMNS} rowKey={(row) => row.title} />
          </div>
        ) : null}

        <div className="panel">
          <h3 className="panel__title">风险提示与免责声明</h3>
          <p className="strategy__lead" data-testid={fieldTestId('advice.risk_warning')}>
            {data.riskWarning || '—'}
          </p>
          <p className="strategy__lead" data-testid={fieldTestId('advice.disclaimer')}>
            {data.disclaimer || '—'}
          </p>
          <p className="note" data-testid={fieldTestId('advice.analysis_status')}>
            分析状态：{data.analysisStatus || '—'}
          </p>
        </div>

        {error ? <p className="panel__error">刷新失败：{error}</p> : null}

        <MetadataBlock metadata={data.metadata} />
        <SignOff generatedAt={data.generatedAt} />
      </div>
    )
  }

  return (
    <Section
      id="strategy"
      title="投资策略"
      intro="三档策略来自同一次分析：保守、均衡、机会，字段一致，可以横向对照。仓位与区间是模型的建议，不是收益承诺。"
      actions={refreshButton}
    >
      {body}
    </Section>
  )
}