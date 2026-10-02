import type { ReactNode } from 'react'

import DataTable, { type Column } from '@/components/DataTable'
import StateBlock from '@/components/StateBlock'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { displayStamp, formatShare } from '@/lib/format'
import type {
  QuantAccuracyResponse,
  QuantAccuracyRow,
  QuantFactorPerformance,
  QuantResearchResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import {
  HORIZONS,
  PosteriorTable,
  horizonLabel,
  interval,
  num,
  pct,
  pp,
} from './shared'

const field = fieldTestId

function SkillRow({
  label,
  value,
  note,
}: {
  label: ReactNode
  value: ReactNode
  note?: ReactNode
}) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td className="num">{value}</td>
      {note === undefined ? null : <td className="note">{note}</td>}
    </tr>
  )
}

/** 前向裁决窗口：够不够判 + Beta 后验；与历史留出期分开，不互相顶替。 */
function ForwardVerdict({
  research,
  horizonDays,
}: {
  research: QuantResearchResponse | null
  horizonDays: number
}) {
  if (!research || research.status !== 'ok') {
    return (
      <p className="note" data-testid={`quant-accuracy-posterior-${horizonDays}`}>
        前向裁决数据不可用：{research?.reason ?? '接口没有返回研究结果'}。这里不用历史留出期顶替。
      </p>
    )
  }
  const horizon = research.horizons.find((item) => item.horizon_days === horizonDays)
  if (!horizon) {
    return (
      <p className="note" data-testid={`quant-accuracy-posterior-${horizonDays}`}>
        这个尺度没有研究裁决数据。
      </p>
    )
  }
  const readiness = horizon.forward_readiness
  return (
    <div className="space-y-4" data-testid={`quant-accuracy-posterior-${horizonDays}`}>
      <div className="table-scroll">
        <table className="data-table">
          <caption className="note">
            裁决只认前向留出期：预注册封板日之后新增的观测，按尺度折算成互不相干的独立下注；
            够 {readiness.required_bets} 次才有资格下结论。
          </caption>
          <thead>
            <tr>
              <th scope="col">窗口起点</th>
              <th scope="col" className="num">
                已积累观测
              </th>
              <th scope="col" className="num">
                独立下注
              </th>
              <th scope="col" className="num">
                需要
              </th>
              <th scope="col" className="num">
                还差
              </th>
              <th scope="col" className="num">
                还差约（交易日）
              </th>
              <th scope="col">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td data-testid={field('research.horizons.forward_readiness.window_start')}>
                {readiness.window_start}
              </td>
              <td className="num" data-testid={field('research.horizons.forward_readiness.observations')}>
                {readiness.observations}
              </td>
              <td className="num" data-testid={field('research.horizons.forward_readiness.independent_bets')}>
                {readiness.independent_bets}
              </td>
              <td className="num" data-testid={field('research.horizons.forward_readiness.required_bets')}>
                {readiness.required_bets}
              </td>
              <td className="num" data-testid={field('research.horizons.forward_readiness.shortfall_bets')}>
                {readiness.shortfall_bets}
              </td>
              <td
                className="num"
                data-testid={field('research.horizons.forward_readiness.approx_trading_days_needed')}
              >
                {readiness.approx_trading_days_needed}
              </td>
              <td data-testid={field('research.horizons.forward_readiness.decidable')}>
                {readiness.decidable ? '可下结论' : '尚不可判'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PosteriorTable posterior={horizon.forward_posterior ?? null} />
    </div>
  )
}

/** 一个周期的回测：本模型 vs 三个基准 + 分布级评分 + 逐因子命中率。 */
function AccuracyPanel({
  row,
  research,
}: {
  row: QuantAccuracyRow
  research: QuantResearchResponse | null
}) {
  const horizon = row.horizon_days
  if (row.sample_size === 0 || row.accuracy === null) {
    return (
      <StateBlock
        kind="unavailable"
        testId={`quant-accuracy-unavailable-${horizon}`}
        title={`${horizonLabel(horizon)}还没有可用的回测`}
        detail={row.reason ?? '样本不足，不给出命中率。'}
      />
    )
  }

  const metrics = row.metrics
  const tilt =
    typeof metrics.score_direction_accuracy === 'number' ? metrics.score_direction_accuracy : null
  const coverage = typeof metrics.interval_coverage_80 === 'number' ? metrics.interval_coverage_80 : null
  const nominal = typeof metrics.interval_nominal_80 === 'number' ? metrics.interval_nominal_80 : null
  const regimes = metrics.regimes
  const regimeRows = [regimes?.pre, regimes?.post].filter(
    (block): block is NonNullable<typeof block> => Boolean(block),
  )

  const summaryRows: Array<{ label: string; node: ReactNode }> = [
    { label: '本模型（校准后的期望收益方向）', node: (
      <span data-testid={field('accuracy.latest.accuracy')}>{pct(row.accuracy)}</span>
    ) },
    { label: '永远看多', node: (
      <span data-testid={field('accuracy.latest.baseline_up_accuracy')}>
        {pct(row.baseline_up_accuracy)}
      </span>
    ) },
    { label: '动量（60 日）', node: (
      <span data-testid={field('accuracy.latest.baseline_momentum_accuracy')}>
        {pct(row.baseline_momentum_accuracy)}
      </span>
    ) },
    { label: '抛硬币', node: '50.0%' },
    { label: '与「永远看多」的差', node: (
      <span data-testid={field('accuracy.metrics.accuracy_diff_vs_up')}>
        {pp(metrics.accuracy_diff_vs_up as number | null | undefined)}
      </span>
    ) },
    { label: 'p 值（vs 永远看多）', node: (
      <span data-testid={field('accuracy.metrics.p_value_vs_up')}>
        {num(metrics.p_value_vs_up as number | null | undefined)}
      </span>
    ) },
    { label: '命中率 95% 置信区间', node: (
      <span data-testid={field('accuracy.metrics.accuracy_ci95')}>
        {interval(metrics.accuracy_ci95 as number[] | null | undefined)}
      </span>
    ) },
    { label: '方向增量 95% CI（相对看多，下界 > 0 才算有增量）', node: (
      <span data-testid={field('accuracy.metrics.direction_edge_vs_up_ci95')}>
        {interval(metrics.direction_edge_vs_up_ci95 as number[] | null | undefined)}
      </span>
    ) },
    { label: 'Brier 分数', node: (
      <span data-testid={field('accuracy.latest.brier_score')}>{num(row.brier_score)}</span>
    ) },
    { label: '区间名义水平', node: (
      <span data-testid={field('accuracy.latest.metrics.interval_nominal_80')}>
        {nominal === null ? '—' : formatShare(nominal * 100, 1)}
      </span>
    ) },
    { label: '区间实际覆盖率（80% 名义）', node: (
      <span data-testid={field('accuracy.latest.metrics.interval_coverage_80')}>
        {coverage === null ? '—' : formatShare(coverage * 100, 1)}
      </span>
    ) },
    { label: '区间平均锐度（越小越锐）', node: (
      <span data-testid={field('accuracy.metrics.interval_sharpness_80')}>
        {num(metrics.interval_sharpness_80 as number | null | undefined)}
      </span>
    ) },
    { label: '平均 CRPS（整张分布）', node: (
      <span data-testid={field('accuracy.metrics.mean_crps')}>
        {num(metrics.mean_crps as number | null | undefined)}
      </span>
    ) },
    { label: '零漂移基准 CRPS', node: (
      <span data-testid={field('accuracy.metrics.mean_crps_flat')}>
        {num(metrics.mean_crps_flat as number | null | undefined)}
      </span>
    ) },
    { label: 'CRPS 技能分（> 0 才算给幅度加分）', node: (
      <span data-testid={field('accuracy.metrics.crps_skill_vs_flat')}>
        {num(metrics.crps_skill_vs_flat as number | null | undefined)}
      </span>
    ) },
    { label: 'CRPS 样本', node: (
      <span data-testid={field('accuracy.metrics.crps_samples')}>
        {String(metrics.crps_samples ?? '—')}
      </span>
    ) },
    { label: '独立下注样本', node: (
      <span data-testid={field('accuracy.metrics.nonoverlapping_samples')}>
        {String(metrics.nonoverlapping_samples ?? '—')}
      </span>
    ) },
    { label: '独立下注命中率', node: (
      <span data-testid={field('accuracy.metrics.accuracy_nonoverlapping')}>
        {pct(metrics.accuracy_nonoverlapping as number | null | undefined)}
      </span>
    ) },
    { label: '独立下注覆盖率', node: (
      <span data-testid={field('accuracy.metrics.coverage_nonoverlapping')}>
        {pct(metrics.coverage_nonoverlapping as number | null | undefined)}
      </span>
    ) },
    { label: '有效样本量', node: (
      <span data-testid={field('accuracy.metrics.effective_sample_size')}>
        {num(metrics.effective_sample_size as number | null | undefined)}
      </span>
    ) },
    { label: '期望收益被护栏封顶的样本占比', node: (
      <span data-testid={field('accuracy.metrics.expected_cap_rate')}>
        {pct(metrics.expected_cap_rate as number | null | undefined)}
      </span>
    ) },
    { label: '幅度 MAPE', node: (
      <span data-testid={field('accuracy.metrics.magnitude_mape')}>
        {num(metrics.magnitude_mape as number | null | undefined)}
      </span>
    ) },
    { label: '幅度技能 vs 零漂移', node: (
      <span data-testid={field('accuracy.metrics.magnitude_skill_vs_flat')}>
        {num(metrics.magnitude_skill_vs_flat as number | null | undefined)}
      </span>
    ) },
    { label: '看空喊话次数', node: (
      <span data-testid={field('accuracy.metrics.down_calls')}>
        {String(metrics.down_calls ?? '—')}
      </span>
    ) },
    { label: '看空命中率', node: (
      <span data-testid={field('accuracy.metrics.down_call_accuracy')}>
        {pct(metrics.down_call_accuracy as number | null | undefined)}
      </span>
    ) },
    { label: '看空相对看多的增量', node: (
      <span data-testid={field('accuracy.metrics.down_call_edge_vs_up')}>
        {pp(metrics.down_call_edge_vs_up as number | null | undefined)}
      </span>
    ) },
    { label: '样本量', node: (
      <span data-testid={field('accuracy.latest.sample_size')}>{row.sample_size}</span>
    ) },
    { label: '评估窗口', node: (
      <span>
        <span data-testid={field('accuracy.latest.window_start')}>{row.window_start ?? '—'}</span>
        {' ~ '}
        <span data-testid={field('accuracy.latest.window_end')}>{row.window_end ?? '—'}</span>
      </span>
    ) },
    { label: '评估时间', node: (
      <span data-testid={field('accuracy.latest.evaluated_at')}>
        {displayStamp(row.evaluated_at) ?? '—'}
      </span>
    ) },
    { label: '样本不足原因', node: (
      <span data-testid={field('accuracy.latest.reason')}>{row.reason ?? '—'}</span>
    ) },
  ]

  const factorColumns: ReadonlyArray<Column<QuantFactorPerformance>> = [
    {
      key: 'name',
      header: '因子',
      render: (factor) => (
        <>
          <span data-testid={field('accuracy.factors.name')}>{factor.name}</span>
          <span className="note" data-testid={field('accuracy.factors.key')}>
            {factor.key}
          </span>
        </>
      ),
    },
    {
      key: 'category',
      header: '类别',
      render: (factor) => (
        <>
          <span data-testid={field('accuracy.factors.category_name')}>{factor.category_name}</span>
          <span className="note" data-testid={field('accuracy.factors.category')}>
            {factor.category}
          </span>
        </>
      ),
    },
    {
      key: 'weight',
      header: '权重',
      numeric: true,
      render: (factor) => <span data-testid={field('accuracy.factors.weight')}>{factor.weight}</span>,
    },
    {
      key: 'sign',
      header: '方向',
      render: (factor) => (
        <span data-testid={field('accuracy.factors.sign')}>
          {factor.sign > 0 ? '上升利多' : '上升利空'}
        </span>
      ),
    },
    {
      key: 'hit_rate',
      header: '单独命中率',
      numeric: true,
      render: (factor) => (
        <span data-testid={field('accuracy.factors.hit_rate')}>{pct(factor.hit_rate)}</span>
      ),
    },
    {
      key: 'ic',
      header: 'IC',
      numeric: true,
      render: (factor) => <span data-testid={field('accuracy.factors.ic')}>{num(factor.ic, 2)}</span>,
    },
    {
      key: 'rank_ic',
      header: 'Rank IC',
      numeric: true,
      render: (factor) => (
        <span data-testid={field('accuracy.factors.rank_ic')}>{num(factor.rank_ic, 2)}</span>
      ),
    },
    {
      key: 'samples',
      header: '样本',
      numeric: true,
      render: (factor) => (
        <span data-testid={field('accuracy.factors.samples')}>{factor.samples}</span>
      ),
    },
  ]

  return (
    <div className="space-y-6" data-testid={`quant-accuracy-${horizon}`}>
      <p className="section__conclusion">
        <span data-testid={field('accuracy.latest.horizon_days')}>{horizonLabel(horizon)}</span>
        ：本模型命中率 <span data-testid={field('accuracy.latest.accuracy')}>{pct(row.accuracy)}</span>
        ，永远看多 <span data-testid={field('accuracy.latest.baseline_up_accuracy')}>
          {pct(row.baseline_up_accuracy)}
        </span>
        ，差 <span data-testid={field('accuracy.metrics.accuracy_diff_vs_up')}>
          {pp(metrics.accuracy_diff_vs_up as number | null | undefined)}
        </span>
        （p = <span data-testid={field('accuracy.metrics.p_value_vs_up')}>
          {num(metrics.p_value_vs_up as number | null | undefined)}
        </span>
        ，样本 <span data-testid={field('accuracy.latest.sample_size')}>{row.sample_size}</span>）。
      </p>

      <div className="table-scroll">
        <table className="data-table">
          <caption className="note">
            本模型 = 校准后的期望收益方向；「永远看多」与「动量（60 日）」是并排基准 ——
            不并排给出几个基准，单一命中率没有意义。CRPS 评整张分布，不只评涨 / 跌方向。
          </caption>
          <thead>
            <tr>
              <th scope="col">项目</th>
              <th scope="col" className="num">
                值
              </th>
            </tr>
          </thead>
          <tbody>
            {summaryRows.map((item) => (
              <SkillRow key={item.label} label={item.label} value={item.node} />
            ))}
          </tbody>
        </table>
      </div>

      {regimeRows.length > 0 ? (
        <div className="table-scroll">
          <table className="data-table">
            <caption className="note">
              分段走查：{regimes?.split_date ?? '—'} 前后各一段；{regimes?.note ?? '按市场结构分段复核'}
            </caption>
            <thead>
              <tr>
                <th scope="col">分段</th>
                <th scope="col" className="num">
                  本模型命中率
                </th>
                <th scope="col" className="num">
                  永远看多
                </th>
                <th scope="col" className="num">
                  动量基准（60 日）
                </th>
                <th scope="col" className="num">
                  样本
                </th>
                <th scope="col">覆盖时段 / 原因</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="note" data-testid={field('accuracy.latest.metrics.regimes.split_date')}>
                  分段日 {regimes?.split_date ?? '—'}
                </td>
                <td className="note" colSpan={4} data-testid={field('accuracy.latest.metrics.regimes.note')}>
                  {regimes?.note ?? '—'}
                </td>
                <td className="note" data-testid={field('accuracy.latest.metrics.reason')}>
                  {String(metrics.reason ?? '—')}
                </td>
              </tr>
              {regimeRows.map((block, index) => {
                const prefix = index === 0 ? 'pre' : 'post'
                return (
                  <tr key={block.label}>
                    <th scope="row" data-testid={field(`accuracy.regimes.${prefix}.label`)}>
                      {block.label}
                    </th>
                    <td className="num" data-testid={field(`accuracy.regimes.${prefix}.accuracy`)}>
                      {pct(block.accuracy)}
                    </td>
                    <td
                      className="num"
                      data-testid={field(`accuracy.regimes.${prefix}.baseline_up_accuracy`)}
                    >
                      {pct(block.baseline_up_accuracy)}
                    </td>
                    <td
                      className="num"
                      data-testid={field(`accuracy.regimes.${prefix}.baseline_momentum_accuracy`)}
                    >
                      {pct(block.baseline_momentum_accuracy)}
                    </td>
                    <td className="num" data-testid={field(`accuracy.regimes.${prefix}.sample_size`)}>
                      {block.sample_size}
                    </td>
                    <td className="note">
                      <span data-testid={field(`accuracy.regimes.${prefix}.window_start`)}>
                        {block.window_start ?? '—'}
                      </span>
                      {' ~ '}
                      <span data-testid={field(`accuracy.regimes.${prefix}.window_end`)}>
                        {block.window_end ?? '—'}
                      </span>
                      <span data-testid={field(`accuracy.regimes.${prefix}.reason`)}>
                        {block.reason ? `（${block.reason}）` : ''}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <div>
        <h4>前向裁决（独立下注口径）</h4>
        <ForwardVerdict research={research} horizonDays={horizon} />
      </div>

      <details className="row-details" data-testid={`quant-accuracy-tilt-${horizon}`}>
        <summary>未校准的因子偏向（对照）与逐因子单独检验</summary>
        <p className="note">
          未校准的合成得分方向命中率：
          <span data-testid={field('accuracy.latest.metrics.score_direction_accuracy')}>
            {pct(tilt)}
          </span>
          （只作对照 —— 生产口径是校准后的期望收益方向，不取它）。
        </p>
        {row.factors.length > 0 ? (
          <DataTable
            rows={row.factors}
            columns={factorColumns}
            rowKey={(factor) => factor.key}
            caption="逐个因子单独检验：命中率低于 50% 说明它的方向先验在这段历史里与实际相反，权重可能失效。"
          />
        ) : (
          <p className="note">没有逐因子回测记录。</p>
        )}
      </details>

      <p className="provenance">
        走查式回测：{row.window_start ?? '—'} ~ {row.window_end ?? '—'}，样本 {row.sample_size} 个交易日
        {row.brier_score === null ? '' : `，Brier 分数 ${row.brier_score.toFixed(3)}`}
        ，评估时间 {displayStamp(row.evaluated_at) ?? '—'}。命中率不看永远看多这一档 ——
        牛市里它天然很高。
      </p>
    </div>
  )
}

/** 回测评估：五个尺度的 tab + 历史评估记录；每个数字都注明口径。 */
export default function Accuracy({
  accuracy,
  research,
  horizon,
  onHorizonChange,
}: {
  accuracy: QuantAccuracyResponse
  research: QuantResearchResponse | null
  horizon: string
  onHorizonChange: (value: string) => void
}) {
  const byHorizon = new Map(accuracy.latest.map((row) => [row.horizon_days, row]))
  const historyColumns: ReadonlyArray<Column<QuantAccuracyRow>> = [
    {
      key: 'evaluated_at',
      header: '评估时间',
      render: (row) => (
        <span data-testid={field('accuracy.history.evaluated_at')}>
          {displayStamp(row.evaluated_at) ?? '—'}
        </span>
      ),
    },
    {
      key: 'horizon',
      header: '尺度',
      render: (row) => (
        <span data-testid={field('accuracy.history.horizon_days')}>{horizonLabel(row.horizon_days)}</span>
      ),
    },
    {
      key: 'window',
      header: '评估窗口',
      render: (row) => (
        <span>
          <span data-testid={field('accuracy.history.window_start')}>{row.window_start ?? '—'}</span>
          {' ~ '}
          <span data-testid={field('accuracy.history.window_end')}>{row.window_end ?? '—'}</span>
        </span>
      ),
    },
    {
      key: 'sample_size',
      header: '样本',
      numeric: true,
      render: (row) => (
        <span data-testid={field('accuracy.history.sample_size')}>{row.sample_size}</span>
      ),
    },
    {
      key: 'accuracy',
      header: '命中率',
      numeric: true,
      render: (row) => (
        <span data-testid={field('accuracy.history.accuracy')}>{pct(row.accuracy)}</span>
      ),
    },
    {
      key: 'brier',
      header: 'Brier',
      numeric: true,
      render: (row) => (
        <span data-testid={field('accuracy.history.brier_score')}>{num(row.brier_score)}</span>
      ),
    },
    {
      key: 'crps',
      header: 'CRPS',
      numeric: true,
      render: (row) => (
        <span data-testid={field('accuracy.history.mean_crps')}>
          {num(row.metrics.mean_crps as number | null | undefined)}
        </span>
      ),
    },
    {
      key: 'reason',
      header: '原因',
      render: (row) => <span data-testid={field('accuracy.history.reason')}>{row.reason ?? '—'}</span>,
    },
  ]

  return (
    <div className="space-y-4">
      <p className="note">
        模型版本 <span data-testid={field('accuracy.model_version')}>{accuracy.model_version}</span>
        。每个尺度给一行结论与完整指标；没有样本的尺度如实说明，不给数字。
      </p>

      <Tabs value={horizon} onValueChange={onHorizonChange}>
        <TabsList aria-label="回测周期">
          {HORIZONS.map((days) => (
            <TabsTrigger key={days} value={String(days)}>
              {horizonLabel(days)}
            </TabsTrigger>
          ))}
        </TabsList>
        {HORIZONS.map((days) => {
          const row = byHorizon.get(days)
          return (
            <TabsContent key={days} value={String(days)}>
              {row ? (
                <AccuracyPanel row={row} research={research} />
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

      {accuracy.history.length > 0 ? (
        <details className="row-details" data-testid={TESTIDS.quantAccuracyHistory}>
          <summary>历史评估记录（{accuracy.history.length} 次）</summary>
          <DataTable
            rows={accuracy.history}
            columns={historyColumns}
            rowKey={(row, index) => `${row.evaluated_at ?? 'record'}-${row.horizon_days}-${index}`}
            caption="每次滚动评估的存档：同一模型在不同时间的成绩，用来看稳定性，不顶替最新一档。"
          />
        </details>
      ) : null}
    </div>
  )
}