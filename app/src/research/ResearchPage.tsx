import { useCallback, useEffect, useState, type ReactNode } from 'react'

import Section from '@/components/Section'
import StateBlock from '@/components/StateBlock'
import { describeApiError } from '@/lib/apiError'
import { displayStamp } from '@/lib/format'
import { interval, num, pct, pp } from '@/sections/quant/shared'
import {
  quantApi,
  sourcesApi,
  type HorizonResearch,
  type QuantResearchResponse,
  type ResearchFactor,
  type ResearchPeriod,
  type SourcesStatusResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

import CoverageChart from './CoverageChart'

const field = fieldTestId

const SUB_STYLE = {
  display: 'block',
  fontSize: 'var(--text-xs)',
  fontWeight: 400,
  color: 'var(--ink-muted)',
} as const

/** 与「永远看多」的差：用符号 + 颜色同时表达，颜色只是加强。 */
function Diff({ value }: { value: number | null }) {
  if (value === null) return <>—</>
  const cls = value > 0 ? 'is-up' : value < 0 ? 'is-down' : undefined
  return <span className={cls}>{pp(value)}</span>
}

/**
 * 版本与裁决：所有顶层字段逐一给展示位。
 * 裁决只看前向留出期；状态不是 ok 时整页诚实降级（见页面底部）。
 */
function VerdictPanel({ data }: { data: QuantResearchResponse }) {
  const stamp = displayStamp(data.generated_at)
  return (
    <div className="panel" data-testid={TESTIDS.researchVerdict}>
      <div className="panel__head">
        <h3 className="panel__title" data-testid={field('research.verdict.label')}>
          {data.verdict.label}
        </h3>
        <span className="tag" data-testid={field('research.verdict.status')}>
          {data.verdict.status}
        </span>
      </div>
      <p className="section__conclusion" data-testid={field('research.verdict.detail')}>
        {data.verdict.detail}
      </p>

      <dl className="metrics">
        <div>
          <dt>模型版本</dt>
          <dd data-testid={field('research.model_version')}>{data.model_version}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd data-testid={field('research.status')}>{data.status}</dd>
        </div>
        <div>
          <dt>历史留出期起点</dt>
          <dd data-testid={field('research.holdout_start')}>{data.holdout_start}</dd>
        </div>
        <div>
          <dt>前向留出期起点（裁决窗口）</dt>
          <dd data-testid={field('research.active_holdout_start')}>{data.active_holdout_start}</dd>
        </div>
        <div>
          <dt>数据截至</dt>
          <dd data-testid={field('research.as_of')}>{data.as_of ?? '—'}</dd>
        </div>
        <div>
          <dt>数据窗口（本页数字来源）</dt>
          <dd data-testid={TESTIDS.researchDataWindow}>
            {data.data_window ? (
              <>
                <span data-testid={field('research.data_window.start')}>
                  {data.data_window.start}
                </span>
                {' → '}
                <span data-testid={field('research.data_window.end')}>{data.data_window.end}</span>
                {' · '}
                <span data-testid={field('research.data_window.trading_days')}>
                  {data.data_window.trading_days} 个交易日
                </span>
                {' · 约 '}
                <span data-testid={field('research.data_window.years')}>
                  {data.data_window.years} 年
                </span>
              </>
            ) : (
              <>
                <span data-testid={field('research.data_window.start')}>—</span>
                <span data-testid={field('research.data_window.trading_days')}>—</span>
                <span data-testid={field('research.data_window.years')}>—</span>
              </>
            )}
          </dd>
        </div>
        <div>
          <dt>报告生成</dt>
          <dd data-testid={field('research.generated_at')}>{stamp ?? '—'}</dd>
        </div>
        <div>
          <dt>本次结果</dt>
          <dd data-testid={field('research.cached')}>
            {data.cached ? '来自 1 小时缓存' : '本次现算'}
          </dd>
        </div>
        <div>
          <dt>不可用原因</dt>
          <dd data-testid={field('research.reason')}>{data.reason ?? '—'}</dd>
        </div>
      </dl>

      <p className="note">
        本页所有数字都基于当前库的这个窗口现算（缓存 1 小时），各样本期的可评估窗口见
        「覆盖度」里的窗口列。README 与历史研究台报告引用的是各自时点的快照 ——
        两者对不上时以本页为准。
      </p>
    </div>
  )
}

/** 前向裁决窗口：够不够判、还差多少，逐字段给展示位。 */
function ForwardWindow({ horizons }: { horizons: HorizonResearch[] }) {
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid={TESTIDS.researchForwardWindow}>
        <caption className="note">
          裁决只认前向留出期：预注册封板日之后**新增**的观测。窗口内的观测按尺度折算成
          互不相干的独立下注，够 20 次才有资格说「有 / 没有优势」；在那之前状态一律是
          「尚不可判」，不用历史留出期的成绩顶替。
        </caption>
        <thead>
          <tr>
            <th scope="col">尺度</th>
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
          {horizons.map((horizon) => {
            const readiness = horizon.forward_readiness
            return (
              <tr key={horizon.horizon_days}>
                <th scope="row">
                  <span data-testid={field('research.horizons.label')}>{horizon.label}</span>
                  <span className="note" data-testid={field('research.horizons.horizon_days')}>
                    {horizon.horizon_days} 个交易日
                  </span>
                  <span className="note" data-testid={field('research.horizons.headline')}>
                    {horizon.headline}
                  </span>
                </th>
                <td data-testid={field('research.horizons.forward_readiness.window_start')}>
                  {readiness.window_start}
                </td>
                <td className="num" data-testid={field('research.horizons.forward_readiness.observations')}>
                  {readiness.observations}
                </td>
                <td
                  className="num"
                  data-testid={field('research.horizons.forward_readiness.independent_bets')}
                >
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
                  {readiness.decidable ? '—' : readiness.approx_trading_days_needed}
                </td>
                <td data-testid={field('research.horizons.forward_readiness.decidable')}>
                  {readiness.decidable ? '可判' : '尚不可判'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
/** Beta 后验：独立下注口径的成功 / 失败合成后验，与 CRPS 并排。 */
function PosteriorBlock({ horizons }: { horizons: HorizonResearch[] }) {
  const anyPosterior = horizons.some((horizon) => Boolean(horizon.forward_posterior))
  return (
    <div className="space-y-4">
      <div className="table-scroll">
        <table className="data-table">
          <caption className="note">
            先验 Beta(1,1)；α = 命中数 + 先验，β = 未命中数 + 先验。独立下注口径把重叠样本
            折成互不相干的证据，次数少时后验会很宽 —— 宽就是宽，不缩。
          </caption>
          <thead>
            <tr>
              <th scope="col">尺度</th>
              <th scope="col">先验</th>
              <th scope="col" className="num">
                α
              </th>
              <th scope="col" className="num">
                β
              </th>
              <th scope="col" className="num">
                命中数
              </th>
              <th scope="col" className="num">
                独立下注
              </th>
              <th scope="col" className="num">
                后验均值
              </th>
              <th scope="col" className="num">
                95% CI
              </th>
              <th scope="col" className="num">
                阈值
              </th>
              <th scope="col" className="num">
                高于阈值概率
              </th>
              <th scope="col" className="num">
                平均 CRPS
              </th>
              <th scope="col" className="num">
                CRPS 技能
              </th>
            </tr>
          </thead>
          <tbody>
            {horizons.map((horizon) => {
              const posterior = horizon.forward_posterior ?? null
              const cells: Array<{ path: string; value: string }> = [
                { path: 'prior', value: posterior ? `Beta(${posterior.prior.join(', ')})` : '—' },
                { path: 'alpha', value: posterior ? num(posterior.alpha) : '—' },
                { path: 'beta', value: posterior ? num(posterior.beta) : '—' },
                { path: 'successes', value: posterior ? String(posterior.successes) : '—' },
                { path: 'independent_bets', value: posterior ? String(posterior.independent_bets) : '—' },
                { path: 'mean', value: posterior ? pct(posterior.mean) : '—' },
                { path: 'ci95', value: posterior ? interval(posterior.ci95) : '—' },
                { path: 'threshold', value: posterior ? pct(posterior.threshold) : '—' },
                {
                  path: 'probability_above_threshold',
                  value: posterior ? pct(posterior.probability_above_threshold) : '—',
                },
                { path: 'mean_crps', value: posterior ? num(posterior.mean_crps) : '—' },
                {
                  path: 'crps_skill_vs_flat',
                  value: posterior ? num(posterior.crps_skill_vs_flat) : '—',
                },
              ]
              return (
                <tr key={horizon.horizon_days}>
                  <th scope="row">{horizon.label}</th>
                  {cells.map((cell) => (
                    <td
                      key={cell.path}
                      className={cell.path === 'prior' ? undefined : 'num'}
                      data-testid={field(`research.horizons.forward_posterior.${cell.path}`)}
                    >
                      {cell.value}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {anyPosterior ? null : (
        <p className="note">
          后端响应未透出 Beta 后验字段（HorizonResearch 响应模型尚未声明）——
          这里是如实标注，不摆替代数字。
        </p>
      )}
    </div>
  )
}

/** 技能总览：五个尺度一行，基准并排；数字全部来自走查式回测。 */
function SkillTable({ horizons }: { horizons: HorizonResearch[] }) {
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid={TESTIDS.researchOverview}>
        <caption className="note">
          命中率 = 方向命中；「差」= 留出期命中率 − 永远看多；Brier 技能分要在 HAC DM
          单尾 p &lt; 0.05 下为正才算显著。这一列的「留出期」是**历史**留出期（已被前两轮
          裁决看过，只作记录）；裁决窗口的成绩见「前向留出期」。CRPS 技能分是整张分布
          （不只涨 / 跌方向）相对「零漂移」基准的改进，&gt; 0 才算给幅度信息加了分。
        </caption>
        <thead>
          <tr>
            <th scope="col">尺度</th>
            <th scope="col" className="num">
              开发期命中
            </th>
            <th scope="col" className="num">
              留出期命中（历史）
            </th>
            <th scope="col" className="num">
              永远看多
            </th>
            <th scope="col" className="num">
              差
            </th>
            <th scope="col" className="num">
              p(&gt;看多)
            </th>
            <th scope="col" className="num">
              Brier 技能
            </th>
            <th scope="col" className="num">
              CRPS 技能
            </th>
            <th scope="col" className="num">
              覆盖率（历史留出）
            </th>
          </tr>
        </thead>
        <tbody>
          {horizons.map((horizon) => {
            const development = horizon.periods.development
            const holdout = horizon.periods.holdout
            return (
              <tr key={horizon.horizon_days}>
                <th scope="row">
                  {horizon.label}
                  <span style={SUB_STYLE}>{horizon.headline}</span>
                </th>
                <td className="num" title={development?.reason ?? undefined}>
                  {pct(development?.accuracy)}
                </td>
                <td className="num" title={holdout?.reason ?? undefined}>
                  {pct(holdout?.accuracy)}
                </td>
                <td className="num">{pct(holdout?.baseline_up_accuracy)}</td>
                <td className="num">
                  <Diff value={holdout?.accuracy_diff_vs_up ?? null} />
                </td>
                <td className="num">{num(holdout?.p_value_vs_up)}</td>
                <td className="num">{num(holdout?.brier_skill_score)}</td>
                <td className="num">{num(holdout?.crps_skill_vs_flat)}</td>
                <td className="num">{pct(holdout?.interval_coverage_80)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
type PeriodRow = { key: string; label: string; value: (period: ResearchPeriod) => ReactNode }

/**
 * 四个样本期 × 全部字段的对照网格：行是字段、列是样本期。
 * 每个格子都有字段级选择器 —— 少一个字段都算口径不完整。
 */
const PERIOD_ROWS: ReadonlyArray<PeriodRow> = [
  { key: 'label', label: '样本期', value: (period) => period.label },
  { key: 'window_start', label: '窗口起点', value: (period) => period.window_start ?? '—' },
  { key: 'window_end', label: '窗口终点', value: (period) => period.window_end ?? '—' },
  { key: 'sample_size', label: '可评估样本', value: (period) => period.sample_size },
  { key: 'accuracy', label: '命中率', value: (period) => pct(period.accuracy) },
  {
    key: 'baseline_up_accuracy',
    label: '永远看多',
    value: (period) => pct(period.baseline_up_accuracy),
  },
  {
    key: 'baseline_momentum_accuracy',
    label: '动量基准（60 日）',
    value: (period) => pct(period.baseline_momentum_accuracy),
  },
  { key: 'brier_score', label: 'Brier 分数', value: (period) => num(period.brier_score) },
  {
    key: 'brier_skill_score',
    label: 'Brier 技能分',
    value: (period) => num(period.brier_skill_score),
  },
  {
    key: 'brier_skill_p_value',
    label: 'Brier 技能 p 值',
    value: (period) => num(period.brier_skill_p_value),
  },
  { key: 'mean_crps', label: '平均 CRPS', value: (period) => num(period.mean_crps) },
  {
    key: 'crps_skill_vs_flat',
    label: 'CRPS 技能 vs 零漂移',
    value: (period) => num(period.crps_skill_vs_flat),
  },
  {
    key: 'accuracy_diff_vs_up',
    label: '与「永远看多」的差',
    value: (period) => pp(period.accuracy_diff_vs_up),
  },
  {
    key: 'direction_edge_vs_up_ci95',
    label: '方向增量 95% CI',
    value: (period) => interval(period.direction_edge_vs_up_ci95),
  },
  { key: 'down_calls', label: '看空喊话次数', value: (period) => period.down_calls ?? '—' },
  {
    key: 'down_call_accuracy',
    label: '看空命中率',
    value: (period) => pct(period.down_call_accuracy),
  },
  {
    key: 'down_call_edge_vs_up',
    label: '看空相对看多增量',
    value: (period) => pp(period.down_call_edge_vs_up),
  },
  { key: 'accuracy_ci95', label: '命中率 95% CI', value: (period) => interval(period.accuracy_ci95) },
  { key: 'p_value_vs_up', label: 'p 值 vs 看多', value: (period) => num(period.p_value_vs_up) },
  {
    key: 'interval_coverage_80',
    label: '80% 区间覆盖率',
    value: (period) => pct(period.interval_coverage_80),
  },
  {
    key: 'interval_coverage_ci95',
    label: '覆盖率 95% CI',
    value: (period) => interval(period.interval_coverage_ci95),
  },
  {
    key: 'effective_sample_size',
    label: '有效样本量',
    value: (period) => num(period.effective_sample_size, 1),
  },
  { key: 'independent_bets', label: '独立下注', value: (period) => period.independent_bets ?? '—' },
  {
    key: 'independent_bet_stride',
    label: '独立下注步长（交易日）',
    value: (period) => period.independent_bet_stride ?? '—',
  },
  {
    key: 'accuracy_independent_bets',
    label: '独立命中率',
    value: (period) => pct(period.accuracy_independent_bets),
  },
  {
    key: 'interval_coverage_80_independent_bets',
    label: '独立覆盖率',
    value: (period) => pct(period.interval_coverage_80_independent_bets),
  },
  {
    key: 'expected_cap_rate',
    label: '期望封顶比例',
    value: (period) => pct(period.expected_cap_rate),
  },
  { key: 'reason', label: '说明 / 原因', value: (period) => period.reason ?? '—' },
]

function PeriodGrid({ horizon }: { horizon: HorizonResearch }) {
  const periods: Array<{ key: string; period: ResearchPeriod }> = [
    { key: 'development', period: horizon.periods.development },
    { key: 'holdout', period: horizon.periods.holdout },
    { key: 'forward', period: horizon.periods.forward },
    { key: 'full', period: horizon.periods.full },
  ]
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="note">
          「独立下注」= 把逐日样本按尺度（stride = 天数）抽成互不相干的下注后的次数；
          250 日的留出期有几千个重叠样本，却只有个位数次下注，两者不能混着读。
        </caption>
        <thead>
          <tr>
            <th scope="col">字段</th>
            {periods.map(({ key, period }) => (
              <th key={key} scope="col">
                {period.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {PERIOD_ROWS.map((row) => (
            <tr key={row.key}>
              <th scope="row">{row.label}</th>
              {periods.map(({ key, period }) => (
                <td key={key} data-testid={field(`research.periods.${key}.${row.key}`)}>
                  {row.value(period)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
/** 校准诊断：预测概率分桶 vs 实际频率。 */
function ReliabilityTables({ horizon }: { horizon: HorizonResearch }) {
  if (horizon.reliability_bins.length === 0) {
    return <p className="note">{horizon.label}：没有可靠性分桶。</p>
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="note">
          {horizon.label}：每桶对比「平均预测概率」与「实际频率」，两者差距越小，概率越可信。
        </caption>
        <thead>
          <tr>
            <th scope="col" className="num">
              区间下界
            </th>
            <th scope="col" className="num">
              区间上界
            </th>
            <th scope="col" className="num">
              样本数
            </th>
            <th scope="col" className="num">
              平均预测
            </th>
            <th scope="col" className="num">
              实际频率
            </th>
          </tr>
        </thead>
        <tbody>
          {horizon.reliability_bins.map((bin, index) => (
            <tr key={`${bin.lo}-${index}`}>
              <td className="num" data-testid={field('research.reliability.lo')}>
                {pct(bin.lo)}
              </td>
              <td className="num" data-testid={field('research.reliability.hi')}>
                {pct(bin.hi)}
              </td>
              <td className="num" data-testid={field('research.reliability.count')}>
                {bin.count}
              </td>
              <td className="num" data-testid={field('research.reliability.mean_predicted')}>
                {pct(bin.mean_predicted)}
              </td>
              <td className="num" data-testid={field('research.reliability.frequency')}>
                {pct(bin.frequency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 逐因子拆解：命中率、IC 与 HAC 对齐检验全给。 */
function FactorTable({ factors }: { factors: ResearchFactor[] }) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="note">
          逐因子全样本口径；「对齐度」是因子方向与「永远看多」的同向程度，
          HAC t / p 是对齐度的显著性检验（只进研究台，不改变生产口径）。
        </caption>
        <thead>
          <tr>
            <th scope="col">因子</th>
            <th scope="col">类别</th>
            <th scope="col" className="num">
              权重
            </th>
            <th scope="col">先验方向</th>
            <th scope="col" className="num">
              样本
            </th>
            <th scope="col" className="num">
              命中率
            </th>
            <th scope="col" className="num">
              IC
            </th>
            <th scope="col" className="num">
              Rank IC
            </th>
            <th scope="col" className="num">
              对齐度
            </th>
            <th scope="col" className="num">
              HAC t
            </th>
            <th scope="col" className="num">
              p 值
            </th>
            <th scope="col" className="num">
              朴素 t
            </th>
          </tr>
        </thead>
        <tbody>
          {factors.map((factor) => (
            <tr key={factor.key}>
              <th scope="row">
                <span data-testid={field('research.factors.name')}>{factor.name}</span>
                <span className="note" data-testid={field('research.factors.key')}>
                  {factor.key}
                </span>
              </th>
              <td>
                <span data-testid={field('research.factors.category_name')}>
                  {factor.category_name}
                </span>
                <span className="note" data-testid={field('research.factors.category')}>
                  {factor.category}
                </span>
              </td>
              <td className="num" data-testid={field('research.factors.weight')}>
                {factor.weight.toFixed(2)}
              </td>
              <td data-testid={field('research.factors.sign')}>
                {factor.sign > 0 ? '正向' : factor.sign < 0 ? '反向' : '—'}
              </td>
              <td className="num" data-testid={field('research.factors.samples')}>
                {factor.samples}
              </td>
              <td className="num" data-testid={field('research.factors.hit_rate')}>
                {pct(factor.hit_rate)}
              </td>
              <td className="num" data-testid={field('research.factors.ic')}>
                {num(factor.ic)}
              </td>
              <td className="num" data-testid={field('research.factors.rank_ic')}>
                {num(factor.rank_ic)}
              </td>
              <td className="num" data-testid={field('research.factors.alignment')}>
                {num(factor.alignment)}
              </td>
              <td className="num" data-testid={field('research.factors.alignment_t')}>
                {num(factor.alignment_t)}
              </td>
              <td className="num" data-testid={field('research.factors.alignment_p_value')}>
                {num(factor.alignment_p_value)}
              </td>
              <td className="num" data-testid={field('research.factors.alignment_naive_t')}>
                {num(factor.alignment_naive_t)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
/** 同步报告：研究数字所依赖的量化同步渠道与状态。 */
function SyncReport({
  sources,
  error,
}: {
  sources: SourcesStatusResponse | null
  error: string | null
}) {
  const quant = sources?.sources.filter((source) => source.channel === 'quant_sync') ?? []
  return (
    <div className="space-y-4" data-testid={TESTIDS.researchSync}>
      {sources ? (
        <p className="section__conclusion">
          数据源状态生成于 {displayStamp(sources.generated_at) ?? '—'}：共 {sources.summary.total} 个渠道，
          可用 {sources.summary.ok} · 不可用 {sources.summary.error} · 本轮跳过 {sources.summary.skipped} ·
          陈旧 {sources.summary.stale}。
        </p>
      ) : (
        <p className="note">数据源状态不可用：{error ?? '接口没有返回。'}</p>
      )}
      {quant.length > 0 ? (
        <div className="table-scroll">
          <table className="data-table">
            <caption className="note">
              量化同步渠道最近一次尝试：状态、完成时间、条目数与错误原文。
            </caption>
            <thead>
              <tr>
                <th scope="col">来源</th>
                <th scope="col">状态</th>
                <th scope="col">完成</th>
                <th scope="col" className="num">
                  条目
                </th>
                <th scope="col">错误</th>
              </tr>
            </thead>
            <tbody>
              {quant.map((source) => (
                <tr key={source.source_key}>
                  <th scope="row">{source.source_key}</th>
                  <td>
                    {source.status_label}
                    <span className="note">（{source.status}）</span>
                  </td>
                  <td>{displayStamp(source.finished_at) ?? '—'}</td>
                  <td className="num">{source.items ?? '—'}</td>
                  <td className="note">{source.error ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : sources ? (
        <p className="note">没有量化同步渠道的记录 —— 量化接口可能还没跑过同步。</p>
      ) : null}
      <p className="provenance">
        评估口径、预注册规则与复现命令见仓库内 docs/specs/2026-10-02-研究台报告.md 与
        docs/specs/2026-10-02-量化策略提升路线图.md；数据不可用时本页只显示原因，不补任何数字。
      </p>
    </div>
  )
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; data: QuantResearchResponse }

/** 研究页：裁决 → 前向留出期 → 覆盖度 → 校准诊断 → 分段 → 因子 → 基准 → 同步报告。 */
export default function ResearchPage() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  const [sources, setSources] = useState<SourcesStatusResponse | null>(null)
  const [sourcesError, setSourcesError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await quantApi.getResearch()
      setState({ kind: 'ready', data })
    } catch (error) {
      setState({
        kind: 'error',
        message: describeApiError(error, {
          fallback: '研究数据加载失败。',
          timeout: '研究计算超时，请稍后重试。',
        }),
      })
    }
  }, [])

  const loadSources = useCallback(async () => {
    try {
      setSources(await sourcesApi.getStatus())
      setSourcesError(null)
    } catch (error) {
      setSourcesError(describeApiError(error, { fallback: '数据源状态加载失败。' }))
    }
  }, [])

  useEffect(() => {
    void load()
    void loadSources()
  }, [load, loadSources])

  const stamp = state.kind === 'ready' ? displayStamp(state.data.generated_at) : null

  return (
    <>
      <a className="skip-link no-print" href="#main">
        跳到主要内容
      </a>

      <header className="masthead no-print">
        <div className="wrap masthead__row">
          <div className="masthead__brand">
            <h1 className="masthead__name">GoldMind</h1>
            <span className="masthead__sub">量化研究 · 技能评估</span>
          </div>

          <nav className="masthead__nav" aria-label="页面导航">
            <a href="./">看板</a>
            <a href="#verdict">裁决</a>
            <a href="#forward">前向留出期</a>
            <a href="#coverage">覆盖度</a>
            <a href="#diagnostics">诊断</a>
            <a href="#regimes">分段</a>
            <a href="#factors">因子</a>
            <a href="#benchmarks">基准</a>
            <a href="#sync">同步报告</a>
          </nav>

          {stamp ? <p className="masthead__stamp">报告生成：{stamp}</p> : null}
        </div>
      </header>

      <main id="main">
        <div className="wrap">
          {state.kind === 'loading' ? (
            <section className="section">
              <StateBlock
                kind="analyzing"
                title="正在计算技能指标…"
                detail="技能指标是走查式回测，首次约数秒；结果缓存 1 小时。"
              />
            </section>
          ) : null}

          {state.kind === 'error' ? (
            <section className="section">
              <StateBlock
                kind="unavailable"
                title="研究数据不可用"
                detail={state.message}
                actions={
                  <button
                    type="button"
                    className="btn"
                    onClick={() => {
                      setState({ kind: 'loading' })
                      void load()
                    }}
                  >
                    重试
                  </button>
                }
              />
            </section>
          ) : null}

          {state.kind === 'ready' && state.data.status !== 'ok' ? (
            <section className="section">
              <StateBlock
                kind="unavailable"
                testId="research-verdict"
                title={state.data.verdict.label}
                detail={state.data.reason ?? state.data.verdict.detail}
              />
            </section>
          ) : null}
          {state.kind === 'ready' && state.data.status === 'ok' ? (
            <>
              <Section
                id="verdict"
                title="版本与裁决"
                intro="先看裁决：裁决只看前向留出期（预注册封板之后的观测）；窗口没攒够就说「尚不可判」，还差多少个交易日一并摊开。"
              >
                <VerdictPanel data={state.data} />
              </Section>

              <Section
                id="forward"
                title="前向留出期（裁决窗口）"
                intro="预注册封板日之后新增的观测才干净：这一段够不够判、还差多少，是「为什么现在没有结论」的唯一答案；Beta 后验给同口径的证据。"
              >
                <ForwardWindow horizons={state.data.horizons} />
                <div style={{ marginTop: 18 }}>
                  <h3 className="panel__title">Beta 后验与 CRPS</h3>
                  <PosteriorBlock horizons={state.data.horizons} />
                </div>
              </Section>

              <Section
                id="coverage"
                title="覆盖度"
                intro="五个尺度的方向命中率、基准对照、Brier 与 CRPS 技能分、区间覆盖率；数字全部来自走查式回测。"
              >
                <SkillTable horizons={state.data.horizons} />
                <div style={{ marginTop: 18 }}>
                  <CoverageChart horizons={state.data.horizons} />
                </div>
                <div className="space-y-6" style={{ marginTop: 18 }} data-testid={TESTIDS.researchCoverage}>
                  {state.data.horizons.map((horizon) => (
                    <details key={horizon.horizon_days} className="factor">
                      <summary>
                        <span className="factor__title">{horizon.label} · 四个样本期明细</span>
                        <span className="factor__subtitle">
                          开发 / 历史留出 / 前向留出（裁决）/ 全样本；样本不足的格子给出原因。
                        </span>
                      </summary>
                      <div className="factor__body">
                        <PeriodGrid horizon={horizon} />
                      </div>
                    </details>
                  ))}
                </div>
              </Section>

              <Section
                id="diagnostics"
                title="校准诊断"
                intro="把预测概率分成十桶，比较「平均预测」与「实际频率」——两者差距越小，概率越可信。"
              >
                <div className="space-y-6" data-testid={TESTIDS.researchDiagnostics}>
                  {state.data.horizons.map((horizon) => (
                    <ReliabilityTables key={horizon.horizon_days} horizon={horizon} />
                  ))}
                </div>
              </Section>

              <Section
                id="regimes"
                title="分段与 Regime 候选"
                intro="第四轮 Regime 候选登记表：lab_only 只进研究台；过前向窗口闸门之前不应出现别的取值。"
              >
                <div className="table-scroll" data-testid={TESTIDS.researchRegimes}>
                  <table className="data-table">
                    <caption className="note">
                      候选 regime 序列的登记信息；状态与说明照后端原文显示，不在前端推断。
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">候选</th>
                        <th scope="col">序列</th>
                        <th scope="col">说明</th>
                        <th scope="col">状态</th>
                        <th scope="col">备注</th>
                      </tr>
                    </thead>
                    <tbody>
                      {state.data.regime_candidates.map((regime) => (
                        <tr key={regime.key}>
                          <th scope="row" data-testid={field('research.regimes.name')}>
                            {regime.name}
                            <span className="note" data-testid={field('research.regimes.key')}>
                              {regime.key}
                            </span>
                          </th>
                          <td data-testid={field('research.regimes.series_key')}>
                            {regime.series_key}
                          </td>
                          <td className="note" data-testid={field('research.regimes.description')}>
                            {regime.description}
                          </td>
                          <td data-testid={field('research.regimes.status')}>{regime.status}</td>
                          <td className="note" data-testid={field('research.regimes.note')}>
                            {regime.note}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>

              <Section
                id="factors"
                title="因子拆解"
                intro="逐因子的命中率、IC 与「永远看多」对齐度（HAC t / p）。低命中率不是丢脸的指标，是下一轮候选的线索。"
              >
                <div className="space-y-6" data-testid={TESTIDS.researchFactors}>
                  {state.data.horizons.map((horizon) => (
                    <div key={horizon.horizon_days}>
                      <h4>{horizon.label}</h4>
                      <FactorTable factors={horizon.factors} />
                    </div>
                  ))}
                </div>
              </Section>

              <Section
                id="benchmarks"
                title="基准候选"
                intro="研究基准的口径（含不含展期）与对照候选：口径提示必须让读者知道收益里有没有换月价差。"
              >
                <div className="space-y-4" data-testid={TESTIDS.researchBenchmarks}>
                  <p className="section__conclusion">
                    研究基准：
                    <span data-testid={field('research.benchmark.name')}>
                      {state.data.benchmark.name}
                    </span>
                    <span className="note" data-testid={field('research.benchmark.key')}>
                      {state.data.benchmark.key}
                    </span>
                    ——
                    <span data-testid={field('research.benchmark.note')}>
                      {state.data.benchmark.note}
                    </span>
                  </p>
                  <div className="table-scroll">
                    <table className="data-table">
                      <caption className="note">
                        对照候选：可用性由后端判定；不可用的候选给出原因，不替它编一个数字。
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">候选</th>
                          <th scope="col">口径说明</th>
                          <th scope="col">可用</th>
                          <th scope="col">原因</th>
                        </tr>
                      </thead>
                      <tbody>
                        {state.data.benchmark.alternatives.map((alternative) => (
                          <tr key={alternative.key}>
                            <th scope="row">
                              <span data-testid={field('research.benchmark.alternatives.name')}>
                                {alternative.name}
                              </span>
                              <span className="note" data-testid={field('research.benchmark.alternatives.key')}>
                                {alternative.key}
                              </span>
                            </th>
                            <td className="note" data-testid={field('research.benchmark.alternatives.note')}>
                              {alternative.note}
                            </td>
                            <td data-testid={field('research.benchmark.alternatives.available')}>
                              {alternative.available ? '可用' : '不可用'}
                            </td>
                            <td className="note" data-testid={field('research.benchmark.alternatives.reason')}>
                              {alternative.reason}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </Section>

              <Section
                id="sync"
                title="同步报告"
                intro="本页数字依赖的数据源最近一次同步：状态、时间与错误原文；不可用时不补数字。"
              >
                <SyncReport sources={sources} error={sourcesError} />
              </Section>
            </>
          ) : null}
        </div>
      </main>

      <footer className="footer">
        <div className="wrap footer__bottom">GoldMind · 量化研究页 · MIT License</div>
      </footer>
    </>
  )
}