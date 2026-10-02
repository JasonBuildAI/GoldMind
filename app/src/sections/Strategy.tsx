import { useCallback, useEffect, useState } from 'react'

import PlaceholderNotice from '@/components/PlaceholderNotice'
import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import SignOff from '@/components/SignOff'
import StateBlock from '@/components/StateBlock'
import StrategyColumns from '@/components/StrategyColumns'
import { describeApiError } from '@/lib/apiError'
import { isPlaceholder } from '@/lib/placeholder'
import {
  investmentAdviceApi,
  type AdvicePriceSnapshot,
  type CorePrinciple,
  type InvestmentStrategy,
  type MarketAssessment,
} from '@/services/api'

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
  generatedAt: string
  placeholder: boolean
  degraded: boolean
  priceSnapshot: AdvicePriceSnapshot | null
}

/**
 * 投资策略：市场评估 + 保守 / 均衡 / 机会三档横向对照。
 *
 * 三档策略来自同一次分析，字段一样，读的时候可以横向比；
 * 取不到就整段留白，不摆一套内置策略。
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
        generatedAt: response.metadata?.generated_at ?? '',
        // 先记占位标记：后端在「正在分析」时返回的是空内容，
        // 放在长度判断里面就永远设不上，页面会把「正在分析」错报成「暂不可用」。
        placeholder: isPlaceholder(response.metadata),
        // 数据不足是第三种状态：不是「正在分析」，也不是「不可用」。
        degraded:
          response.metadata?.status === 'insufficient_data' ||
          response.analysis_status === 'insufficient_data',
        priceSnapshot: response.price_snapshot ?? null,
      })
    } catch (err) {
      setError(
        describeApiError(err, {
          fallback: '获取最新分析失败。',
          timeout: '分析耗时较长，请稍后重试刷新。',
        }),
      )
      // 不填充任何编造的策略：保持为空，由下面的空状态如实说明。
      setData(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void fetchAdvice()
  }, [fetchAdvice])

  const refreshButton = (
    <RefreshButton onClick={() => void fetchAdvice(true)} busy={refreshing} label="重新分析" />
  )

  // 后端在「正在分析」时返回的是空内容：strategies / core_principles 为空数组、
  // market_assessment 为空对象 —— 空对象是真值，只判 `!assessment` 会把空壳当成有内容。
  const assessment =
    data?.assessment && Object.keys(data.assessment).length > 0 ? data.assessment : null

  let body

  if (data && data.degraded) {
    // 输入不足时后端不调模型，只给行情统计；这里如实展示，不摆任何策略。
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
            <h3 className="panel__title">行情统计（仅供参考）</h3>
            <dl className="metrics">
              <div>
                <dt>最新收盘</dt>
                <dd>${data.priceSnapshot.latest_price.toFixed(2)}</dd>
              </div>
              <div>
                <dt>{data.priceSnapshot.label}涨跌</dt>
                <dd>
                  {data.priceSnapshot.change_pct >= 0 ? '+' : ''}
                  {data.priceSnapshot.change_pct.toFixed(2)}%
                </dd>
              </div>
              <div>
                <dt>期间最高 / 最低</dt>
                <dd>
                  ${data.priceSnapshot.high.toFixed(2)} / ${data.priceSnapshot.low.toFixed(2)}
                </dd>
              </div>
              <div>
                <dt>高低振幅</dt>
                <dd>{data.priceSnapshot.amplitude_pct.toFixed(2)}%</dd>
              </div>
            </dl>
          </div>
        ) : null}
        <SignOff generatedAt={data.generatedAt} />
      </div>
    )
  } else if (!data || (data.strategies.length === 0 && data.principles.length === 0 && !assessment)) {
    if (loading) {
      body = <StateBlock title="正在读取投资策略…" testId="strategy-loading" />
    } else if (data?.placeholder) {
      body = (
        <StateBlock
          kind="analyzing"
          testId="strategy-analyzing"
          title="投资策略正在分析中"
          detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一套内置策略 —— 编造的建议与真实分析长得一样，用户分不出来。"
        />
      )
    } else {
      body = (
        <StateBlock
          kind="unavailable"
          testId="strategy-unavailable"
          title="投资策略暂不可用"
          detail={error ?? '没能取到分析结果。这里不显示任何内置策略 —— 与其摆一套编造的建议，不如如实说明取不到。'}
        />
      )
    }
  } else {
    body = (
      <div className="space-y-8">
        <PlaceholderNotice show={data.placeholder} testId="strategy-placeholder" />

        {assessment ? (
          <div className="panel">
            <h3 className="panel__title">市场评估</h3>
            <dl className="metrics">
              <div>
                <dt>当前位置</dt>
                <dd>{assessment.current_position || '—'}</dd>
              </div>
              <div>
                <dt>风险等级</dt>
                <dd>{RISK_LABEL[assessment.risk_level] ?? '未知'}</dd>
              </div>
              <div>
                <dt>建议策略</dt>
                <dd>{assessment.recommended_approach || '—'}</dd>
              </div>
              <div>
                <dt>关键考量</dt>
                <dd className="metrics__note">{assessment.key_considerations.join('；') || '—'}</dd>
              </div>
            </dl>
          </div>
        ) : null}

        {data.strategies.length > 0 ? (
          <StrategyColumns strategies={data.strategies} testId="strategy-columns" />
        ) : null}

        {data.principles.length > 0 ? (
          <div className="panel">
            <h3 className="panel__title">执行原则</h3>
            <dl className="principles">
              {data.principles.map((principle) => (
                <div key={principle.title}>
                  <dt>{principle.title}</dt>
                  <dd>{principle.description}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}

        {data.riskWarning ? (
          <div className="panel">
            <h3 className="panel__title">风险提示</h3>
            <p className="strategy__lead">{data.riskWarning}</p>
          </div>
        ) : null}

        {error ? <p className="panel__error">刷新失败：{error}</p> : null}

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
