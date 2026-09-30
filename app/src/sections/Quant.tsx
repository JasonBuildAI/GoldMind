import { useCallback, useEffect, useState } from 'react'

import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import StateBlock from '@/components/StateBlock'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { describeApiError } from '@/lib/apiError'
import { displayStamp, formatPercent, formatShare, formatUsd } from '@/lib/format'
import {
  quantApi,
  type QuantAccuracyResponse,
  type QuantAccuracyRow,
  type QuantFactorSnapshot,
  type QuantFactorsResponse,
  type QuantPredictionItem,
  type QuantPredictionsResponse,
} from '@/services/api'

const HORIZONS = [1, 5, 20]

const STATUS_LABEL: Record<string, string> = {
  ok: '正常',
  stale: '陈旧',
  missing: '无数据',
  warming: '样本不足',
  skipped: '未到期',
  error: '不可用',
}

function horizonLabel(days: number): string {
  return `${days} 个交易日`
}

/** 涨跌方向：符号 + 文字一起给，颜色只是加强。 */
function Direction({ direction }: { direction: 'up' | 'down' | null }) {
  if (direction === 'up') return <span className="is-up">▲ 看涨</span>
  if (direction === 'down') return <span className="is-down">▼ 看跌</span>
  return <span>—</span>
}

function statusTag(status: string) {
  if (status === 'ok') return null
  return <span className="tag">{STATUS_LABEL[status] ?? status}</span>
}

/**
 * 一个周期的结论：方向、概率、基准价与目标价、逐因子贡献。
 *
 * 后端说不可用时，这里只显示原因 —— 不摆方向、不摆数字。
 */
function PredictionPanel({ prediction }: { prediction: QuantPredictionItem }) {
  if (prediction.status !== 'ok') {
    return (
      <StateBlock
        kind="unavailable"
        testId={`quant-prediction-unavailable-${prediction.horizon_days}`}
        title={`${horizonLabel(prediction.horizon_days)}的预测不可用`}
        detail={prediction.reason ?? '因子数据不足。这里不显示方向与目标价 —— 与其给一个编出来的数，不如如实说明。'}
      />
    )
  }

  const contributions = prediction.factors
    .filter((factor) => factor.contribution !== null)
    .sort((left, right) => Math.abs(right.contribution ?? 0) - Math.abs(left.contribution ?? 0))

  return (
    <div className="space-y-6">
      <dl className="metrics">
        <div>
          <dt>方向</dt>
          <dd>
            <Direction direction={prediction.direction} />
            <span className="metrics__note">（{horizonLabel(prediction.horizon_days)}）</span>
          </dd>
        </div>
        <div>
          <dt>上行概率</dt>
          <dd>
            {prediction.probability_up === null
              ? '不可用（历史样本不足）'
              : formatShare(prediction.probability_up * 100, 0)}
          </dd>
        </div>
        <div>
          <dt>基准价</dt>
          <dd className="num">{formatUsd(prediction.base_price)}</dd>
        </div>
        <div>
          <dt>目标价</dt>
          <dd className="num">{formatUsd(prediction.target_price)}</dd>
        </div>
        <div>
          <dt>期望收益</dt>
          <dd>{prediction.expected_return === null ? '—' : formatPercent(prediction.expected_return * 100)}</dd>
        </div>
        <div>
          <dt>不确定度</dt>
          <dd>{prediction.uncertainty === null ? '—' : `±${formatShare(prediction.uncertainty * 100, 2)}`}</dd>
        </div>
        <div>
          <dt>可用因子</dt>
          <dd>
            {prediction.available_factors}/{prediction.total_factors}
          </dd>
        </div>
        <div>
          <dt>数据截至</dt>
          <dd>{displayStamp(prediction.as_of) ?? '—'}</dd>
        </div>
      </dl>

      <div className="table-scroll">
        <table className="data-table">
          <caption className="note">
            合成得分 {prediction.score === null ? '—' : prediction.score.toFixed(2)}
            （把每个因子的滚动 z 分数按方向对齐后加权平均；缺的因子按剩余权重归一，不会被当成 0）
          </caption>
          <thead>
            <tr>
              <th scope="col">因子</th>
              <th scope="col">类别</th>
              <th scope="col">数据截至</th>
              <th scope="col" className="num">
                方向信号 z
              </th>
              <th scope="col" className="num">
                贡献
              </th>
            </tr>
          </thead>
          <tbody>
            {contributions.map((factor) => (
              <tr key={factor.key}>
                <th scope="row">{factor.name}</th>
                <td>{factor.category_name}</td>
                <td>{factor.obs_date ?? '—'}</td>
                <td className="num">{factor.signed_z === null ? '—' : factor.signed_z.toFixed(2)}</td>
                <td className={factor.contribution !== null && factor.contribution < 0 ? 'num is-down' : 'num'}>
                  {factor.contribution === null ? '—' : formatPercent(factor.contribution * 100, 2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="provenance">
        方向由这 {prediction.available_factors} 个因子的加权得分决定，不是单一指标；概率是得分在历史分布中的位置，
        不是「保证」。数据源不可用时该因子不参与，并在下面的因子表里标注原因。
      </p>
    </div>
  )
}

/** 一个周期的回测：本模型 vs 三个基准 + 逐因子命中率。 */
function AccuracyPanel({ row }: { row: QuantAccuracyRow }) {
  if (row.sample_size === 0 || row.accuracy === null) {
    return (
      <StateBlock
        kind="unavailable"
        testId={`quant-accuracy-unavailable-${row.horizon_days}`}
        title={`${horizonLabel(row.horizon_days)}还没有可用的回测`}
        detail={row.reason ?? '样本不足，不给出命中率。'}
      />
    )
  }

  const summary = [
    { label: '本模型', value: row.accuracy },
    { label: '永远看多', value: row.baseline_up_accuracy },
    { label: '动量（60 日）', value: row.baseline_momentum_accuracy },
    { label: '抛硬币', value: 0.5 },
  ]

  return (
    <div className="space-y-6">
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">口径</th>
              <th scope="col" className="num">
                命中率
              </th>
            </tr>
          </thead>
          <tbody>
            {summary.map((item) => (
              <tr key={item.label}>
                <th scope="row">{item.label}</th>
                <td className="num">
                  {item.value === null ? '—' : formatShare(item.value * 100, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="provenance">
        走查式回测：{row.window_start ?? '—'} ~ {row.window_end ?? '—'}，样本 {row.sample_size} 个交易日，
        {row.brier_score === null ? '' : ` Brier 分数 ${row.brier_score.toFixed(3)}，`}
        评估时间 {displayStamp(row.evaluated_at) ?? '—'}。命中率不看永远看多这一档 —— 牛市里它天然很高，
        不并排给出三个基准，「60%」就没有意义。
      </p>

      {row.factors.length > 0 ? (
        <div className="table-scroll">
          <table className="data-table">
            <caption className="note">逐个因子单独检验：命中率低于 50% 说明它的方向先验在这段历史里与实际相反，权重可能失效。</caption>
            <thead>
              <tr>
                <th scope="col">因子</th>
                <th scope="col" className="num">
                  单独命中率
                </th>
                <th scope="col" className="num">
                  IC
                </th>
                <th scope="col" className="num">
                  样本
                </th>
              </tr>
            </thead>
            <tbody>
              {row.factors.map((factor) => (
                <tr key={factor.key}>
                  <th scope="row">{factor.name}</th>
                  <td className="num">{factor.hit_rate === null ? '—' : formatShare(factor.hit_rate * 100, 1)}</td>
                  <td className="num">{factor.ic === null ? '—' : factor.ic.toFixed(3)}</td>
                  <td className="num">{factor.samples}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}

/** 四类因素的因子表：值、数据截至、信号、贡献、来源。不可用的带原因。 */
function FactorTable({ category, factors }: { category: string; factors: QuantFactorSnapshot[] }) {
  const rows = factors.filter((factor) => factor.category === category)
  if (rows.length === 0) return null

  return (
    <div className="panel">
      <h3 className="panel__title">{rows[0].category_name}</h3>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">因子</th>
              <th scope="col" className="num">
                最新值
              </th>
              <th scope="col">数据截至</th>
              <th scope="col" className="num">
                信号 z
              </th>
              <th scope="col" className="num">
                贡献
              </th>
              <th scope="col">来源</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((factor) => (
              <tr key={factor.key}>
                <th scope="row">
                  {factor.name} {statusTag(factor.status)}
                  <span className="note">
                    {factor.sign > 0 ? ' 上升利多' : ' 上升利空'} · 权重 {factor.weight}
                  </span>
                </th>
                <td className="num">
                  {factor.value === null ? '—' : `${factor.value.toFixed(2)} ${factor.unit}`}
                </td>
                <td>
                  {factor.obs_date ?? '—'}
                  {factor.age_days !== null ? <span className="note">（{factor.age_days} 天前）</span> : null}
                </td>
                <td className="num">{factor.signed_z === null ? '—' : factor.signed_z.toFixed(2)}</td>
                <td className="num">
                  {factor.contribution === null ? '—' : formatPercent(factor.contribution * 100, 2)}
                </td>
                <td className="note">{factor.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows
        .filter((factor) => factor.status !== 'ok' && factor.reason)
        .map((factor) => (
          <p className="note" key={`${factor.key}-reason`}>
            {factor.name}：{factor.reason}
          </p>
        ))}
    </div>
  )
}

interface QuantData {
  factors: QuantFactorsResponse
  predictions: QuantPredictionsResponse
  accuracy: QuantAccuracyResponse
}

/**
 * 量化预测：结论、准确率与四类因素仪表盘。
 *
 * 三个面板用同一份因子面板计算，任一环节算不出来都如实标注；
 * 命中率与三个基准并排展示，不挑对自己有利的那一档。
 */
export default function Quant() {
  const [data, setData] = useState<QuantData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
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
        await quantApi.refresh()
      }
      const [factors, predictions, accuracy] = await Promise.all([
        quantApi.getFactors(),
        quantApi.getPredictions(),
        quantApi.getAccuracy(),
      ])
      setData({ factors, predictions, accuracy })
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
        testId="quant-unavailable"
        title="量化数据不可用"
        detail={error ?? '没能取到因子与预测。这里不显示任何内置数字。'}
      />
    )
  } else {
    const predictions = [...data.predictions.predictions].sort(
      (left, right) => left.horizon_days - right.horizon_days,
    )
    const accuracyByHorizon = new Map(data.accuracy.latest.map((row) => [row.horizon_days, row]))
    const failedSources = data.factors.sources.filter((source) => source.status === 'error')

    body = (
      <div className="space-y-8">
        <p className="note">
          模型 {data.factors.model_version} · 因子数据截至 {data.factors.as_of ?? '—'} ·{" "}
          {data.factors.available_factors}/{data.factors.total_factors} 个因子可用
          {data.factors.sync.finished_at ? ` · 最近同步 ${displayStamp(data.factors.sync.finished_at)}` : ''}
          {predictions[0]?.status !== 'ok' && predictions[0]?.reason
            ? ` · ${predictions[0].reason}`
            : ''}
        </p>

        {failedSources.length > 0 ? (
          <p className="note">
            数据源不可用：
            {failedSources.map((source) => `${source.label ?? source.name}（${source.error ?? '原因未知'}）`).join('；')}
          </p>
        ) : null}

        <div className="panel">
          <h3 className="panel__title">预测结论</h3>
          <Tabs value={horizon} onValueChange={setHorizon}>
            <TabsList aria-label="预测周期">
              {HORIZONS.map((days) => (
                <TabsTrigger key={days} value={String(days)}>
                  {horizonLabel(days)}
                </TabsTrigger>
              ))}
            </TabsList>
            {HORIZONS.map((days) => {
              const prediction = predictions.find((item) => item.horizon_days === days)
              return (
                <TabsContent key={days} value={String(days)}>
                  {prediction ? (
                    <PredictionPanel prediction={prediction} />
                  ) : (
                    <StateBlock
                      kind="unavailable"
                      title={`${horizonLabel(days)}的预测不可用`}
                      detail="接口没有返回这个周期。"
                    />
                  )}
                </TabsContent>
              )
            })}
          </Tabs>
        </div>

        <div className="panel">
          <h3 className="panel__title">回测命中率</h3>
          <Tabs value={horizon} onValueChange={setHorizon}>
            <TabsList aria-label="回测周期">
              {HORIZONS.map((days) => (
                <TabsTrigger key={days} value={String(days)}>
                  {horizonLabel(days)}
                </TabsTrigger>
              ))}
            </TabsList>
            {HORIZONS.map((days) => {
              const row = accuracyByHorizon.get(days)
              return (
                <TabsContent key={days} value={String(days)}>
                  {row ? (
                    <AccuracyPanel row={row} />
                  ) : (
                    <StateBlock
                      kind="unavailable"
                      title={`${horizonLabel(days)}还没有可用的回测`}
                      detail="接口没有返回这个周期的评估。"
                    />
                  )}
                </TabsContent>
              )
            })}
          </Tabs>
        </div>

        <div className="panel">
          <h3 className="panel__title">四类影响因素</h3>
          <div className="space-y-6">
            {data.factors.categories.map((category) => (
              <FactorTable key={category.key} category={category.key} factors={data.factors.factors} />
            ))}
          </div>
        </div>

        {error ? <p className="panel__error">刷新失败：{error}</p> : null}
      </div>
    )
  }

  return (
    <Section
      id="quant"
      title="量化预测"
      intro="按「货币政策与利率 / 避险与信用 / 供需结构 / 市场与技术面」四类因素合成方向与目标价，并给出走查式回测的命中率与基准对照。"
      actions={refreshButton}
    >
      {body}
    </Section>
  )
}
