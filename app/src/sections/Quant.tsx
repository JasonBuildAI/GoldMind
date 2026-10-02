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
  type QuantDecomposition,
  type QuantFactorSnapshot,
  type QuantFactorsResponse,
  type QuantMonitorResponse,
  type QuantMonitorRow,
  type QuantPredictionItem,
  type QuantPredictionsResponse,
  type QuantScenario,
} from '@/services/api'

const HORIZONS = [1, 5, 20, 60, 250]

const SCALE_SHORT: Record<number, string> = {
  1: '1 日',
  5: '1 周',
  20: '1 月',
  60: '1 季',
  250: '1 年',
}

const STATUS_LABEL: Record<string, string> = {
  ok: '正常',
  stale: '陈旧',
  missing: '无数据',
  warming: '样本不足',
  skipped: '未到期',
  error: '不可用',
}

function horizonLabel(days: number): string {
  return SCALE_SHORT[days] ?? `${days} 个交易日`
}

/** 涨跌方向：符号 + 文字一起给，颜色只是加强。 */
function Direction({ direction }: { direction: 'up' | 'down' | 'flat' | null }) {
  if (direction === 'up') return <span className="is-up">▲ 看涨</span>
  if (direction === 'down') return <span className="is-down">▼ 看跌</span>
  if (direction === 'flat') return <span>＝ 持平</span>
  return <span>—</span>
}

/** 未校准的因子偏向：合成得分的符号 + 数值，只作对照，不代表模型结论。 */
function FactorTilt({ score }: { score: number | null }) {
  if (score === null) return <span>—</span>
  const label = score > 0 ? '偏多' : score < 0 ? '偏空' : '中性'
  return (
    <span>
      {label} {score.toFixed(2)}
    </span>
  )
}

function statusTag(status: string) {
  if (status === 'ok') return null
  return <span className="tag">{STATUS_LABEL[status] ?? status}</span>
}

function scenarioRange(scenario: QuantScenario): string {
  if (scenario.price_low !== null && scenario.price_high !== null) {
    return `${formatUsd(scenario.price_low)} ~ ${formatUsd(scenario.price_high)}`
  }
  if (scenario.price_low !== null) return `${formatUsd(scenario.price_low)} 以上`
  if (scenario.price_high !== null) return `${formatUsd(scenario.price_high)} 以下`
  return '—'
}

/** 三情景：区间来自预测分布分位数；触发条件出现就改情景，失效条件出现就作废。 */
function ScenarioTable({ prediction }: { prediction: QuantPredictionItem }) {
  if (prediction.scenarios.length === 0) {
    return (
      <p className="note" data-testid={`quant-scenarios-unavailable-${prediction.horizon_days}`}>
        三情景不可用：{prediction.scenario_reason ?? '预测分布或历史样本不足，这里不摆区间。'}
      </p>
    )
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="note">
          三情景由该尺度预测分布 N(μ, σ²) 的分位数定义：Base 50%、Bull 25%、Bear 25%。
          点位必须带失效条件 —— 触发条件出现就切换情景，失效条件出现就作废。
        </caption>
        <thead>
          <tr>
            <th scope="col">情景</th>
            <th scope="col" className="num">
              概率
            </th>
            <th scope="col">
              价格区间
            </th>
            <th scope="col">触发条件</th>
            <th scope="col">失效条件</th>
          </tr>
        </thead>
        <tbody>
          {prediction.scenarios.map((scenario) => (
            <tr key={scenario.key}>
              <th scope="row">{scenario.label}</th>
              <td className="num">{formatShare(scenario.probability * 100, 0)}</td>
              <td className="num">{scenarioRange(scenario)}</td>
              <td className="note">{scenario.trigger}</td>
              <td className="note">{scenario.invalidation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 公允价：把市场价拆成宏观锚、需求溢价、风险溢价与情绪残差。 */
function FairValuePanel({ decomposition }: { decomposition: QuantDecomposition }) {
  if (decomposition.status !== 'ok') {
    return (
      <StateBlock
        kind="unavailable"
        testId="quant-fair-value-unavailable"
        title="公允价值分解不可用"
        detail={
          decomposition.reason ??
          '回归样本或回归量不足。这里不显示编出来的公允价 —— 宁可只给市场价。'
        }
      />
    )
  }
  return (
    <div className="space-y-6" data-testid="quant-fair-value">
      <dl className="metrics">
        <div>
          <dt>市场价</dt>
          <dd className="num">{formatUsd(decomposition.market_price)}</dd>
        </div>
        <div>
          <dt>公允价</dt>
          <dd className="num">{formatUsd(decomposition.fair_value)}</dd>
        </div>
        <div>
          <dt>偏离度</dt>
          <dd>
            {decomposition.deviation_pct === null
              ? '—'
              : formatPercent(decomposition.deviation_pct * 100)}
          </dd>
        </div>
        <div>
          <dt>拟合 R²</dt>
          <dd>{decomposition.r2 === null ? '—' : decomposition.r2.toFixed(3)}</dd>
        </div>
        <div>
          <dt>回归样本</dt>
          <dd>{decomposition.samples}</dd>
        </div>
        <div>
          <dt>数据截至</dt>
          <dd>{displayStamp(decomposition.as_of) ?? '—'}</dd>
        </div>
      </dl>

      <div className="table-scroll">
        <table className="data-table">
          <caption className="note">
            四块之和恒等于市场价：中枢 + 需求溢价 + 风险溢价 + 情绪残差（残差走阔 = 模型外因素在定价）。
          </caption>
          <thead>
            <tr>
              <th scope="col">分块</th>
              <th scope="col" className="num">
                美元
              </th>
              <th scope="col" className="num">
                占比
              </th>
              <th scope="col">驱动</th>
            </tr>
          </thead>
          <tbody>
            {decomposition.blocks.map((block) => (
              <tr key={block.key}>
                <th scope="row">{block.name}</th>
                <td className="num">{formatUsd(block.usd)}</td>
                <td className="num">
                  {block.share_pct === null ? '—' : formatShare(block.share_pct, 1)}
                </td>
                <td className="note">
                  {block.drivers.map((driver) => driver.name).join('、') || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const SIGNAL_TEXT: Record<string, string> = {
  bull: '▲ 看涨',
  bear: '▼ 看跌',
  neutral: '— 中性',
}

/**
 * 按量级取舍小数位：800000 不该显示成 800000.00，
 * 铜金比 0.0016 也不该显示成 0.00（两位小数会把非零的值压成零，等同丢数）。
 */
function formatMagnitude(abs: number): string {
  if (abs > 0 && abs < 0.01) return abs.toPrecision(3)
  return abs.toFixed(abs >= 100 ? 0 : 2)
}

/** 变化量按量级给小数位：0.12 -> +0.12；123456 -> +12.3 万。 */
function formatChange(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '\u2212' : ''
  const abs = Math.abs(value)
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(1)} 万`
  return `${sign}${formatMagnitude(abs)}`
}

/** 仪表盘的值：正值不带符号，负值用真正的减号。 */
function formatMonitorValue(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 10000) return formatChange(value)
  return value < 0 ? `\u2212${formatMagnitude(abs)}` : formatMagnitude(abs)
}

function MonitorSignal({ row }: { row: QuantMonitorRow }) {
  if (row.status !== 'ok') return <span className="tag">不可用</span>
  const text = row.signal === null ? null : SIGNAL_TEXT[row.signal]
  if (text === null) return <span className="note">{row.signal_label}</span>
  return (
    <span className={row.signal === 'bull' ? 'is-up' : row.signal === 'bear' ? 'is-down' : ''}>
      {text}
    </span>
  )
}

/**
 * 监测仪表盘：方法论第七节的周更表。
 *
 * 每行给频率、来源、最新值与数据截至，避免「拿三个月前的数当今天」；
 * 取不到就说原因（宁可标不可用），信息型指标不给方向。
 */
function MonitorTable({ monitor }: { monitor: QuantMonitorResponse }) {
  if (monitor.rows.length === 0) {
    return (
      <StateBlock
        kind="unavailable"
        testId="quant-monitor-unavailable"
        title="监测仪表盘不可用"
        detail="接口没有返回任何监测行。"
      />
    )
  }
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid="quant-monitor-table">
        <caption className="note">
          周更表：阈值是确定性规则（见各行说明），信号只是把规则翻译成多空；
          数据截至一列是每个指标的观测日 —— 值越旧，越要打折看。
          {monitor.as_of ? ` 全部指标中最新观测日：${monitor.as_of}。` : ''}
        </caption>
        <thead>
          <tr>
            <th scope="col">指标</th>
            <th scope="col">频率</th>
            <th scope="col">来源</th>
            <th scope="col" className="num">
              最新值
            </th>
            <th scope="col" className="num">
              变化
            </th>
            <th scope="col">数据截至</th>
            <th scope="col">信号</th>
            <th scope="col">说明</th>
          </tr>
        </thead>
        <tbody>
          {monitor.rows.map((row) => (
            <tr key={row.key} data-testid={`quant-monitor-row-${row.key}`}>
              <th scope="row">{row.name}</th>
              <td className="note">{row.frequency}</td>
              <td className="note">{row.source}</td>
              <td className="num">
                {row.value === null ? '—' : `${formatMonitorValue(row.value)} ${row.unit}`}
              </td>
              <td className="num">{row.change === null ? '—' : formatChange(row.change)}</td>
              <td>{row.obs_date ?? '—'}</td>
              <td>
                <MonitorSignal row={row} />
              </td>
              <td className="note">
                {row.note}
                {row.reason ? (
                  <span className="note" data-testid={`quant-monitor-reason-${row.key}`}>
                    （{row.reason}）
                  </span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
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
    <div className="space-y-6" data-testid={`quant-prediction-${prediction.horizon_days}`}>
      <dl className="metrics">
        <div>
          <dt>方向</dt>
          <dd>
            <Direction direction={prediction.direction} />
            <span className="metrics__note">（{horizonLabel(prediction.horizon_days)} · 校准后的漂移）</span>
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
          <dd>
            {prediction.expected_return === null ? '—' : formatPercent(prediction.expected_return * 100)}
            {prediction.expected_capped ? (
              <span
                className="metrics__note"
                data-testid={`quant-prediction-capped-${prediction.horizon_days}`}
              >
                （已封顶：模型原本想报更夸张的幅度，被护栏夹回市场真动过的量级）
              </span>
            ) : null}
          </dd>
        </div>
        <div>
          <dt>不确定度</dt>
          <dd>
            {prediction.uncertainty === null ? '—' : `±${formatShare(prediction.uncertainty * 100, 2)}`}
            {prediction.interval_nominal === null ? null : (
              <span
                className="metrics__note"
                data-testid={`quant-prediction-nominal-${prediction.horizon_days}`}
              >
                （名义 {formatShare(prediction.interval_nominal * 100, 1)}
                {prediction.distribution_mode === 'normal' ? ' · 正态兜底' : ' · 经验分布'}）
              </span>
            )}
          </dd>
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

      <details
        className="row-details"
        data-testid={`quant-prediction-tilt-${prediction.horizon_days}`}
      >
        <summary>因子偏向（未校准）：只作对照，不参与方向</summary>
        <p className="note">
          这 {prediction.available_factors} 个因子按方向对齐加权后的原始倾向：
          <FactorTilt score={prediction.score} />
          （只作对照；方向、概率、目标价与区间都出自校准后的分布，不取它）。
        </p>
      </details>

      {prediction.headline ? (
        <p className="note" data-testid={`quant-prediction-headline-${prediction.horizon_days}`}>
          本尺度的主输出：{prediction.headline}
        </p>
      ) : null}

      {prediction.scale_description ? (
        <p className="note">该尺度的主控层：{prediction.scale_description}</p>
      ) : null}

      <ScenarioTable prediction={prediction} />

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
        方向 = 校准后的期望收益（漂移）符号，与目标价、上行概率、区间、情景出自同一个分布；
        因子偏向（未校准）是这 {prediction.available_factors} 个因子加权后的原始倾向，收在上面的折叠说明里，只作对照，不顶替方向。
        数据源不可用时该因子不参与，并在下面的因子表里标注原因。
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

  const tilt =
    typeof row.metrics.score_direction_accuracy === 'number'
      ? row.metrics.score_direction_accuracy
      : null
  const summary = [
    { label: '本模型', value: row.accuracy },
    { label: '永远看多', value: row.baseline_up_accuracy },
    { label: '动量（60 日）', value: row.baseline_momentum_accuracy },
    { label: '抛硬币', value: 0.5 },
  ]
  const coverage =
    typeof row.metrics.interval_coverage_80 === 'number' ? row.metrics.interval_coverage_80 : null
  const regimes = row.metrics.regimes
  const regimeRows = [regimes?.pre, regimes?.post].filter(
    (block): block is NonNullable<typeof block> => Boolean(block),
  )

  return (
    <div className="space-y-6" data-testid={`quant-accuracy-${row.horizon_days}`}>
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

      {tilt !== null ? (
        <details className="row-details" data-testid={`quant-accuracy-tilt-${row.horizon_days}`}>
          <summary>因子偏向（未校准）：这段历史里的单独成绩</summary>
          <p className="note">
            合成得分符号的命中率 {formatShare(tilt * 100, 1)}，只作对照；主表只列本模型与三个基准。
          </p>
        </details>
      ) : null}

      {coverage !== null ? (
        <p className="note">
          80% 名义区间的实际覆盖率 {formatShare(coverage * 100, 1)}（理想值 80%）：低于 80%
          说明不确定度被低估，区间比真实波动窄。
        </p>
      ) : null}

      {regimeRows.length > 0 ? (
        <div className="table-scroll">
          <table className="data-table">
            <caption className="note">
              以 {regimes?.split_date ?? '2022-01-01'} 为界分段{regimes?.note ? `（${regimes.note}）` : ''}：
              2022 年前后的定价函数可能不同，分段成绩比一个总数更可核对。
            </caption>
            <thead>
              <tr>
                <th scope="col">区间</th>
                <th scope="col" className="num">
                  本模型
                </th>
                <th scope="col" className="num">
                  永远看多
                </th>
                <th scope="col" className="num">
                  样本
                </th>
                <th scope="col">覆盖时段 / 原因</th>
              </tr>
            </thead>
            <tbody>
              {regimeRows.map((block) => (
                <tr key={block.label}>
                  <th scope="row">{block.label}</th>
                  <td className="num">
                    {block.accuracy === null ? '—' : formatShare(block.accuracy * 100, 1)}
                  </td>
                  <td className="num">
                    {block.baseline_up_accuracy === null
                      ? '—'
                      : formatShare(block.baseline_up_accuracy * 100, 1)}
                  </td>
                  <td className="num">{block.sample_size}</td>
                  <td className="note">
                    {block.reason ?? `${block.window_start ?? '—'} ~ ${block.window_end ?? '—'}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <p className="provenance">
        走查式回测：{row.window_start ?? '—'} ~ {row.window_end ?? '—'}，样本 {row.sample_size} 个交易日，
        {row.brier_score === null ? '' : ` Brier 分数 ${row.brier_score.toFixed(3)}，`}
        评估时间 {displayStamp(row.evaluated_at) ?? '—'}。「本模型」= 校准后的期望收益方向，
        「因子偏向（未校准）」= 合成得分的符号，作为对照单独折叠展示。命中率不看永远看多这一档 ——
        牛市里它天然很高，不并排给出几个基准，「60%」就没有意义。
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
  monitor: QuantMonitorResponse
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
      const [factors, predictions, accuracy, monitor] = await Promise.all([
        quantApi.getFactors(),
        quantApi.getPredictions(),
        quantApi.getAccuracy(),
        quantApi.getMonitor(),
      ])
      setData({ factors, predictions, accuracy, monitor })
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
    const okSources = data.factors.sources.filter((source) => source.status === 'ok').length

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

        <details className="row-details" data-testid="quant-sources-details">
          <summary>
            数据源状态（{okSources}/{data.factors.sources.length} 正常，展开看逐个源）
          </summary>
          {data.factors.sources.length > 0 ? (
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
                  {data.factors.sources.map((source) => (
                    <tr key={source.name}>
                      <th scope="row">{source.label ?? source.name}</th>
                      <td>{STATUS_LABEL[source.status] ?? source.status}</td>
                      <td className="note">{source.error ?? source.reason ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="note">还没有同步记录 —— 点右上角「重新抓取」跑一轮。</p>
          )}
          {data.factors.sync.finished_at ? (
            <p className="note">
              最近一次同步完成 {displayStamp(data.factors.sync.finished_at) ?? data.factors.sync.finished_at}；
              「未到期」表示本轮按各源的最小间隔跳过，不是失败。
            </p>
          ) : null}
        </details>

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
          <h3 className="panel__title">公允价值分解</h3>
          <FairValuePanel decomposition={data.predictions.fair_value} />
        </div>

        <div className="panel">
          <h3 className="panel__title">监测仪表盘（周更表）</h3>
          <MonitorTable monitor={data.monitor} />
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
      intro="按 1 日 / 1 周 / 1 月 / 1 季 / 1 年五个尺度，用「货币政策与利率 / 避险与信用 / 供需结构 / 市场与技术面」四类因素合成校准后的方向、目标价与三情景，并把未校准的因子偏向收进折叠说明作对照；另给公允价分解、周更监测仪表盘，以及走查式回测的命中率与基准对照。"
      actions={refreshButton}
    >
      {body}
    </Section>
  )
}
