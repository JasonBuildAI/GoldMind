import type { ReactNode } from 'react'

import StateBlock from '@/components/StateBlock'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { displayStamp, formatPercent, formatShare, formatUsd } from '@/lib/format'
import type { QuantPredictionItem, QuantPredictionsResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import {
  Direction,
  FactorTilt,
  HORIZONS,
  INTERVAL_ALPHA_TEXT,
  horizonLabel,
  statusLabel,
} from './shared'

const field = fieldTestId

/**
 * 三情景：区间来自预测分布分位数；触发条件出现就改情景，失效条件出现就作废。
 * 每个字段都有自己的展示位 —— 后端的数字不在这里重算。
 */
function ScenarioTable({ prediction }: { prediction: QuantPredictionItem }) {
  const horizon = prediction.horizon_days
  if (prediction.scenarios.length === 0) {
    return (
      <p className="note" data-testid={`quant-scenarios-unavailable-${horizon}`}>
        三情景不可用：{prediction.scenario_reason ?? '预测分布或历史样本不足，这里不摆区间。'}
      </p>
    )
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="note">
          三情景由该尺度预测分布的分位数定义：Base 50%、Bull 25%、Bear 25%。
          点位必须带失效条件 —— 触发条件出现就切换情景，失效条件出现就作废。
        </caption>
        <thead>
          <tr>
            <th scope="col">情景</th>
            <th scope="col" className="num">
              概率
            </th>
            <th scope="col" className="num">
              价格区间
            </th>
            <th scope="col">触发条件</th>
            <th scope="col">失效条件</th>
          </tr>
        </thead>
        <tbody>
          {prediction.scenarios.map((scenario) => (
            <tr key={scenario.key}>
              <th scope="row">
                <span data-testid={field('predictions.scenarios.label')}>{scenario.label}</span>
                <span className="note" data-testid={field('predictions.scenarios.key')}>
                  {scenario.key}
                </span>
              </th>
              <td className="num" data-testid={field('predictions.scenarios.probability')}>
                {formatShare(scenario.probability * 100, 0)}
              </td>
              <td className="num">
                {scenario.price_low !== null && scenario.price_high !== null ? (
                  <>
                    <span data-testid={field('predictions.scenarios.price_low')}>
                      {formatUsd(scenario.price_low)}
                    </span>
                    {' ~ '}
                    <span data-testid={field('predictions.scenarios.price_high')}>
                      {formatUsd(scenario.price_high)}
                    </span>
                  </>
                ) : scenario.price_low !== null ? (
                  <>
                    <span data-testid={field('predictions.scenarios.price_low')}>
                      {formatUsd(scenario.price_low)}
                    </span>{' '}
                    以上
                  </>
                ) : scenario.price_high !== null ? (
                  <>
                    <span data-testid={field('predictions.scenarios.price_high')}>
                      {formatUsd(scenario.price_high)}
                    </span>{' '}
                    以下
                  </>
                ) : (
                  '—'
                )}
              </td>
              <td className="note" data-testid={field('predictions.scenarios.trigger')}>
                {scenario.trigger}
              </td>
              <td className="note" data-testid={field('predictions.scenarios.invalidation')}>
                {scenario.invalidation}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 逐因子贡献：只展示后端算好的值，前端不重排、不补算。 */
function ContributionTable({ prediction }: { prediction: QuantPredictionItem }) {
  const contributions = [...prediction.factors].sort(
    (left, right) => Math.abs(right.contribution ?? 0) - Math.abs(left.contribution ?? 0),
  )
  if (contributions.length === 0) {
    return <p className="note">这个尺度没有可展示的因子贡献。</p>
  }
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid={TESTIDS.quantFactorTable}>
        <caption className="note">
          合成得分 {prediction.score === null ? '—' : prediction.score.toFixed(2)}
          （把每个因子的滚动 z 分数按方向对齐后加权平均；缺的因子按剩余权重归一，不会被当成 0）
        </caption>
        <thead>
          <tr>
            <th scope="col">因子</th>
            <th scope="col">类别</th>
            <th scope="col" className="num">
              权重
            </th>
            <th scope="col">数据截至</th>
            <th scope="col" className="num">
              最新值
            </th>
            <th scope="col" className="num">
              z（原始）
            </th>
            <th scope="col" className="num">
              方向信号 z
            </th>
            <th scope="col" className="num">
              贡献
            </th>
            <th scope="col">状态</th>
          </tr>
        </thead>
        <tbody>
          {contributions.map((factor) => (
            <tr key={factor.key}>
              <th scope="row">
                <span data-testid={field('predictions.factors.name')}>{factor.name}</span>
                <span className="note" data-testid={field('predictions.factors.key')}>
                  {factor.key}
                </span>
              </th>
              <td>
                <span data-testid={field('predictions.factors.category_name')}>
                  {factor.category_name}
                </span>
                <span className="note" data-testid={field('predictions.factors.category')}>
                  {factor.category}
                </span>
              </td>
              <td className="num" data-testid={field('predictions.factors.weight')}>
                {factor.weight}
                <span className="note" data-testid={field('predictions.factors.sign')}>
                  {factor.sign > 0 ? '上升利多' : '上升利空'}
                </span>
              </td>
              <td data-testid={field('predictions.factors.obs_date')}>{factor.obs_date ?? '—'}</td>
              <td className="num" data-testid={field('predictions.factors.value')}>
                {factor.value === null ? '—' : factor.value.toFixed(2)}
              </td>
              <td className="num" data-testid={field('predictions.factors.z')}>
                {factor.z === null ? '—' : factor.z.toFixed(2)}
              </td>
              <td className="num" data-testid={field('predictions.factors.signed_z')}>
                {factor.signed_z === null ? '—' : factor.signed_z.toFixed(2)}
              </td>
              <td
                className={factor.contribution !== null && factor.contribution < 0 ? 'num is-down' : 'num'}
                data-testid={field('predictions.factors.contribution')}
              >
                {factor.contribution === null ? '—' : formatPercent(factor.contribution * 100, 2)}
              </td>
              <td data-testid={field('predictions.factors.status')}>
                {statusLabel(factor.status)}
                <span className="note" data-testid={field('predictions.factors.reason')}>
                  {factor.reason ? `（${factor.reason}）` : '—'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 一个尺度的完整结论：先一行结论 + 关键数字，细节收进唯一一层折叠。 */
function PredictionPanel({ prediction }: { prediction: QuantPredictionItem }) {
  const horizon = prediction.horizon_days
  if (prediction.status !== 'ok') {
    return (
      <StateBlock
        kind="unavailable"
        testId={`quant-prediction-unavailable-${horizon}`}
        title={`${horizonLabel(horizon)}的预测不可用`}
        detail={prediction.reason ?? '因子数据不足。这里不显示方向与目标价 —— 与其给一个编出来的数，不如如实说明。'}
      />
    )
  }

  const directionText =
    prediction.direction_status === 'not_published'
      ? statusLabel('not_published')
      : prediction.direction === 'up'
        ? '▲ 看涨'
        : prediction.direction === 'down'
          ? '▼ 看跌'
          : prediction.direction === 'flat'
            ? '＝ 持平'
            : '—'
  const headline =
    prediction.headline ??
    `${horizonLabel(horizon)} ${directionText}，上行概率 ${
      prediction.probability_up === null ? '—' : formatShare(prediction.probability_up * 100, 0)
    }，目标价 ${formatUsd(prediction.target_price)}`

  const rawRows: Array<{ label: string; node: ReactNode }> = [
    { label: '尺度', node: <span data-testid={field('predictions.scale_label')}>{prediction.scale_label ?? '—'}</span> },
    { label: '尺度代号', node: <span data-testid={field('predictions.scale')}>{prediction.scale ?? '—'}</span> },
    { label: '交易日数', node: <span data-testid={field('predictions.horizon_days')}>{prediction.horizon_days} 个交易日</span> },
    { label: '主控层', node: <span data-testid={field('predictions.scale_description')}>{prediction.scale_description ?? '—'}</span> },
    { label: '状态', node: <span data-testid={field('predictions.status')}>{statusLabel(prediction.status)}</span> },
    { label: '不可用原因', node: <span data-testid={field('predictions.reason')}>{prediction.reason ?? '—'}</span> },
    { label: '基准口径', node: (
      <span>
        <span data-testid={field('predictions.base_basis_label')}>{prediction.base_basis_label}</span>
        <span className="note" data-testid={field('predictions.base_basis')}>
          {prediction.base_basis}
        </span>
      </span>
    ) },
    { label: '分布口径', node: (
      <span data-testid={field('predictions.distribution_mode')}>
        {prediction.distribution_mode === null
          ? '—'
          : INTERVAL_ALPHA_TEXT[prediction.distribution_mode] ?? prediction.distribution_mode}
      </span>
    ) },
    { label: '区间名义水平', node: (
      <span data-testid={field('predictions.interval_nominal')}>
        {prediction.interval_nominal === null ? '—' : formatShare(prediction.interval_nominal * 100, 1)}
      </span>
    ) },
    { label: '区间实际水平（1 − α）', node: (
      <span data-testid={field('predictions.interval_alpha')}>
        {prediction.interval_alpha === null
          ? '—'
          : formatShare((1 - prediction.interval_alpha) * 100, 1)}
      </span>
    ) },
    { label: '期望收益是否被护栏封顶', node: (
      <span data-testid={field('predictions.expected_capped')}>
        {prediction.expected_capped ? '是（已夹回市场真动过的量级）' : '否'}
      </span>
    ) },
    { label: '模型版本', node: <span data-testid={field('predictions.model_version')}>{prediction.model_version}</span> },
  ]

  return (
    <div className="space-y-6" data-testid={`quant-prediction-${horizon}`}>
      <p className="section__conclusion" data-testid={`quant-prediction-headline-${horizon}`}>
        <span data-testid={field('predictions.headline')}>{headline}</span>
      </p>

      <dl className="metrics">
        <div>
          <dt>方向</dt>
          <dd>
            <Direction
              direction={prediction.direction}
              directionLabel={prediction.direction_label}
              directionStatus={prediction.direction_status}
              directionReason={prediction.direction_reason}
            />
            <span className="metrics__note">（校准后的期望收益符号）</span>
          </dd>
        </div>
        <div>
          <dt>上行概率</dt>
          <dd data-testid={field('predictions.probability_up')}>
            {prediction.probability_up === null
              ? '不可用（历史样本不足）'
              : formatShare(prediction.probability_up * 100, 0)}
          </dd>
        </div>
        <div>
          <dt>基准价</dt>
          <dd className="num" data-testid={field('predictions.base_price')}>
            {formatUsd(prediction.base_price)}
          </dd>
        </div>
        <div>
          <dt>目标价</dt>
          <dd className="num" data-testid={field('predictions.target_price')}>
            {formatUsd(prediction.target_price)}
          </dd>
        </div>
        <div>
          <dt>期望收益</dt>
          <dd data-testid={field('predictions.expected_return')}>
            {prediction.expected_return === null
              ? '—'
              : formatPercent(prediction.expected_return * 100)}
            {prediction.expected_capped ? (
              <span className="metrics__note" data-testid={`quant-prediction-capped-${horizon}`}>
                （已封顶：模型原本想报更夸张的幅度，被护栏夹回市场真动过的量级）
              </span>
            ) : null}
          </dd>
        </div>
        <div>
          <dt>不确定度</dt>
          <dd data-testid={field('predictions.uncertainty')}>
            {prediction.uncertainty === null ? '—' : `±${formatShare(prediction.uncertainty * 100, 2)}`}
            {prediction.interval_nominal === null ? null : (
              <span className="metrics__note" data-testid={`quant-prediction-nominal-${horizon}`}>
                （名义 {formatShare(prediction.interval_nominal * 100, 1)}
                {prediction.distribution_mode === 'normal' ? ' · 正态兜底' : ' · 经验分布'}）
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt>区间（实际水平）</dt>
          <dd className="num">
            <span data-testid={field('predictions.range_low')}>{formatUsd(prediction.range_low)}</span>
            {' ~ '}
            <span data-testid={field('predictions.range_high')}>{formatUsd(prediction.range_high)}</span>
          </dd>
        </div>
        <div>
          <dt>可用因子</dt>
          <dd>
            <span data-testid={field('predictions.available_factors')}>{prediction.available_factors}</span>
            {' / '}
            <span data-testid={field('predictions.total_factors')}>{prediction.total_factors}</span>
          </dd>
        </div>
        <div>
          <dt>数据截至</dt>
          <dd data-testid={field('predictions.as_of')}>{displayStamp(prediction.as_of) ?? '—'}</dd>
        </div>
      </dl>

      <p className="note">
        <span>情景说明：</span>
        <span data-testid={field('predictions.scenario_reason')}>
          {prediction.scenario_reason ?? '—'}
        </span>
      </p>

      <ScenarioTable prediction={prediction} />

      <details className="row-details" data-testid={`quant-prediction-tilt-${horizon}`}>
        <summary>模型字段与口径（含未校准的因子偏向）</summary>
        <p className="note">
          这 {prediction.available_factors} 个因子按方向对齐加权后的原始倾向：
          <FactorTilt score={prediction.score} />
          （只作对照；方向、概率、目标价与区间都出自校准后的分布，不取它）。
        </p>
        <div className="table-scroll">
          <table className="data-table">
            <caption className="note">本尺度全部模型字段的原始取值与口径，供核对。</caption>
            <thead>
              <tr>
                <th scope="col">字段</th>
                <th scope="col">值</th>
              </tr>
            </thead>
            <tbody>
              {rawRows.map((row) => (
                <tr key={row.label}>
                  <th scope="row">{row.label}</th>
                  <td>{row.node}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <ContributionTable prediction={prediction} />

      <p className="provenance">
        方向 = 校准后的期望收益（漂移）符号，与目标价、上行概率、区间、情景出自同一个分布；
        因子偏向（未校准）是这 {prediction.available_factors} 个因子加权后的原始倾向，收在上面的折叠说明里，
        只作对照，不顶替方向。数据源不可用时该因子不参与，并在因子表里标注原因。
      </p>
    </div>
  )
}

/**
 * 决策尺度 tab：五个尺度共用一组 tab，切换只改视图，不重新取数。
 * 顶部先把目标价与区间所用的价格口径说清楚。
 */
export default function ScaleTab({
  predictions,
  horizon,
  onHorizonChange,
}: {
  predictions: QuantPredictionsResponse
  horizon: string
  onHorizonChange: (value: string) => void
}) {
  const basis = predictions.price_basis
  const items = [...predictions.predictions].sort(
    (left, right) => left.horizon_days - right.horizon_days,
  )
  return (
    <div className="space-y-4">
      <p className="note">
        {basis ? (
          <>
            目标价与区间口径：
            <span data-testid={field('predictions.price_basis.label')}>{basis.label}</span>
            <span className="note" data-testid={field('predictions.price_basis.basis')}>
              {basis.basis}
            </span>
            <span data-testid={field('predictions.price_basis.source')}>来源 {basis.source}</span>
            <span data-testid={field('predictions.price_basis.as_of')}>
              截至 {displayStamp(basis.as_of) ?? basis.as_of}
            </span>
          </>
        ) : (
          <span data-testid={field('predictions.price_basis.label')}>价格口径未提供</span>
        )}
      </p>

      <Tabs value={horizon} onValueChange={onHorizonChange}>
        <TabsList aria-label="预测周期">
          {HORIZONS.map((days) => (
            <TabsTrigger key={days} value={String(days)}>
              {horizonLabel(days)}
            </TabsTrigger>
          ))}
        </TabsList>
        {HORIZONS.map((days) => {
          const prediction = items.find((item) => item.horizon_days === days)
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
  )
}