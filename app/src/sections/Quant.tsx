import { useCallback, useEffect, useState } from 'react'

import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import StateBlock from '@/components/StateBlock'
import { useFreshnessBlock } from '@/contexts/FreshnessContext'
import { describeApiError } from '@/lib/apiError'
import { displayStamp, formatShare, formatUsd } from '@/lib/format'
import {
  quantApi,
  type QuantAccuracyResponse,
  type QuantFactorsResponse,
  type QuantMonitorResponse,
  type QuantPredictionsResponse,
  type QuantResearchResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import Accuracy from './quant/Accuracy'
import FactorTables from './quant/FactorTables'
import FairValue from './quant/FairValue'
import Monitor from './quant/Monitor'
import ScaleTab from './quant/ScaleTab'
import SourcesStatus from './quant/SourcesStatus'

const field = fieldTestId

interface QuantData {
  factors: QuantFactorsResponse
  predictions: QuantPredictionsResponse
  accuracy: QuantAccuracyResponse
  monitor: QuantMonitorResponse
  research: QuantResearchResponse | null
}

/** 一年尺度的一句话结论（没有就退回最短尺度）。 */
function headlineOf(predictions: QuantPredictionsResponse): string {
  const items = [...predictions.predictions].sort(
    (left, right) => right.horizon_days - left.horizon_days,
  )
  const item = items.find((prediction) => prediction.headline) ?? items[0]
  if (!item) return '接口没有返回任何尺度的预测。'
  if (item.headline) return item.headline
  const direction =
    item.direction === 'up'
      ? '▲ 看涨'
      : item.direction === 'down'
        ? '▼ 看跌'
        : item.direction === 'flat'
          ? '＝ 持平'
          : '方向未发布'
  return `${item.horizon_days} 日尺度：${direction}，目标价 ${formatUsd(item.target_price)}`
}

/**
 * 量化预测：决策尺度 tab、公允价值、监测信号、回测评估、四类因素表。
 *
 * 所有数字都由后端给出；任一环节算不出来都如实标注，不摆内置数字。
 * 研究接口只用于回测面板里的前向裁决证据（Beta 后验），取不到不影响其余面板。
 */
export default function Quant() {
  const [data, setData] = useState<QuantData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshInfo, setRefreshInfo] = useState<{ success: boolean; message: string } | null>(null)
  const [horizon, setHorizon] = useState('5')

  const fetchAll = useCallback(async (refresh = false) => {
    if (refresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      if (refresh) {
        const result = await quantApi.refresh()
        setRefreshInfo({ success: result.success, message: result.message })
      }
      const [factors, predictions, accuracy, monitor] = await Promise.all([
        quantApi.getFactors(),
        quantApi.getPredictions(),
        quantApi.getAccuracy(),
        quantApi.getMonitor(),
      ])
      let research: QuantResearchResponse | null = null
      try {
        research = await quantApi.getResearch()
      } catch {
        research = null
      }
      setData({ factors, predictions, accuracy, monitor, research })
    } catch (err) {
      setError(
        describeApiError(err, {
          fallback: '获取量化数据失败。',
          timeout: '抓取数据源耗时较长，请稍后重试。',
        }),
      )
      setData(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void fetchAll()
  }, [fetchAll])

  useFreshnessBlock(
    'quant',
    '量化预测',
    loading ? 'pending' : error || !data ? 'unavailable' : 'fresh',
    data?.factors.as_of ?? data?.predictions.as_of ?? null,
  )

  const refreshButton = (
    <RefreshButton onClick={() => void fetchAll(true)} busy={refreshing} label="重新抓取" />
  )

  let body
  if (loading) {
    body = <StateBlock title="正在读取量化因子与预测…" testId="quant-loading" />
  } else if (!data) {
    body = (
      <StateBlock
        kind="unavailable"
        testId={TESTIDS.quantUnavailable}
        title="量化数据不可用"
        detail={error ?? '没能取到因子与预测。这里不显示任何内置数字。'}
      />
    )
  } else {
    const failedSources = data.factors.sources.filter((source) => source.status === 'error')
    const latest = [...data.predictions.predictions].sort(
      (left, right) => right.horizon_days - left.horizon_days,
    )[0]

    body = (
      <div className="space-y-8">
        <p className="section__conclusion">
          <span data-testid={field('predictions.model_version')}>
            模型 {data.predictions.model_version}
          </span>
          {' · 因子 '}
          <span data-testid={field('quant.available_factors')}>{data.factors.available_factors}</span>
          {'/'}
          <span data-testid={field('quant.total_factors')}>{data.factors.total_factors}</span>
          {' 可用（截至 '}
          <span data-testid={field('predictions.as_of')}>
            {displayStamp(data.predictions.as_of) ?? data.predictions.as_of ?? '—'}
          </span>
          {'）· '}
          {headlineOf(data.predictions)}
          {latest?.probability_up === null || latest === undefined
            ? ''
            : `（上行概率 ${formatShare(latest.probability_up * 100, 0)}）`}
        </p>

        {failedSources.length > 0 ? (
          <p className="panel__error">
            数据源不可用：
            {failedSources
              .map((source) => `${source.label ?? source.name}（${source.error ?? '原因未知'}）`)
              .join('；')}
          </p>
        ) : null}

        {refreshInfo ? (
          <p className={refreshInfo.success ? 'note' : 'panel__error'}>
            <span data-testid={field('quant.refresh.success')}>
              重新抓取{refreshInfo.success ? '成功' : '失败'}
            </span>
            <span data-testid={field('quant.refresh.message')}>{refreshInfo.message}</span>
          </p>
        ) : null}

        <SourcesStatus factors={data.factors} />

        <div className="panel">
          <h3 className="panel__title">决策尺度</h3>
          <ScaleTab
            predictions={data.predictions}
            horizon={horizon}
            onHorizonChange={setHorizon}
          />
        </div>

        <div className="panel">
          <h3 className="panel__title">公允价值分解</h3>
          <FairValue decomposition={data.predictions.fair_value} />
        </div>

        <div className="panel">
          <h3 className="panel__title">监测信号（周更表）</h3>
          <Monitor monitor={data.monitor} />
        </div>

        <div className="panel">
          <h3 className="panel__title">回测评估</h3>
          <Accuracy
            accuracy={data.accuracy}
            research={data.research}
            horizon={horizon}
            onHorizonChange={setHorizon}
          />
        </div>

        <div className="panel">
          <h3 className="panel__title">四类影响因素</h3>
          <FactorTables factors={data.factors} />
        </div>

        {error ? <p className="panel__error">刷新失败：{error}</p> : null}
      </div>
    )
  }

  return (
    <Section
      id="quant"
      title="量化预测"
      intro="按 1 日 / 1 周 / 1 月 / 1 季 / 1 年五个尺度，用「货币政策与利率 / 避险与信用 / 供需结构 / 市场与技术面」四类因素合成校准后的方向、目标价与三情景；另给公允价分解、周更监测信号，以及走查式回测的命中率、CRPS 与前向裁决证据。"
      actions={refreshButton}
    >
      {body}
    </Section>
  )
}