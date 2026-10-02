import { useCallback, useEffect, useState } from 'react'

import Section from '@/components/Section'
import StateBlock from '@/components/StateBlock'
import { describeApiError } from '@/lib/apiError'
import { displayStamp } from '@/lib/format'
import { quantApi } from '@/services/api'
import type {
  ForwardWindowReadiness,
  HorizonResearch,
  QuantResearchResponse,
  ResearchPeriod,
} from '@/services/api'

import CoverageChart from './CoverageChart'

const SUB_STYLE = {
  display: 'block',
  fontSize: 'var(--text-xs)',
  fontWeight: 400,
  color: 'var(--ink-muted)',
} as const

const pct = (value: number | null | undefined, digits = 1): string =>
  value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`

const pp = (value: number | null): string =>
  value === null ? '—' : `${value >= 0 ? '+' : '−'}${Math.abs(value * 100).toFixed(1)}pp`

const num = (value: number | null | undefined, digits = 3): string =>
  value === null || value === undefined ? '—' : value.toFixed(digits)

const interval = (pair: number[] | null | undefined): string =>
  pair && pair.length === 2 ? `${pct(pair[0])} ~ ${pct(pair[1])}` : '—'

/** 与「永远看多」的差：用符号 + 颜色同时表达，颜色只是加强。 */
function Diff({ value }: { value: number | null }) {
  if (value === null) return <>—</>
  const cls = value > 0 ? 'is-up' : value < 0 ? 'is-down' : undefined
  return <span className={cls}>{pp(value)}</span>
}

function SkillTable({ horizons }: { horizons: HorizonResearch[] }) {
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid="research-overview">
        <caption className="note">
          命中率 = 方向命中；「差」= 留出期命中率 − 永远看多；Brier 技能分要在 HAC
          DM 单尾 p &lt; 0.05 下为正才算显著。这一列的「留出期」是**历史**留出期
          （已被前两轮裁决看过，只作记录）；裁决窗口的成绩见上一节。样本不足的格子
          显示「—」，鼠标悬停给出原因。
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
                <td className="num">{pct(holdout?.interval_coverage_80)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** 裁决窗口的进度：还差多少个交易日才够独立下注数 —— 「为什么还没有结论」的答案。 */
function ForwardWindow({ horizons }: { horizons: HorizonResearch[] }) {
  return (
    <div className="table-scroll">
      <table className="data-table" data-testid="research-forward-window">
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
              还差约（交易日）
            </th>
            <th scope="col">状态</th>
          </tr>
        </thead>
        <tbody>
          {horizons.map((horizon) => {
            const readiness: ForwardWindowReadiness = horizon.forward_readiness
            return (
              <tr key={horizon.horizon_days}>
                <th scope="row">{horizon.label}</th>
                <td>{readiness.window_start}</td>
                <td className="num">{readiness.observations}</td>
                <td className="num">{readiness.independent_bets}</td>
                <td className="num">{readiness.required_bets}</td>
                <td className="num">
                  {readiness.decidable ? '—' : readiness.approx_trading_days_needed}
                </td>
                <td>{readiness.decidable ? '可判' : '尚不可判'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function PeriodDetail({ horizon }: { horizon: HorizonResearch }) {
  const rows: Array<ResearchPeriod> = [
    horizon.periods.development,
    horizon.periods.holdout,
    horizon.periods.forward,
    horizon.periods.full,
  ]
  return (
    <div className="table-scroll">
      <table className="data-table">
        <caption className="note">
          「独立下注」= 把逐日样本按尺度（stride = 天数）抽成互不相干的下注后的次数；
          「独立命中 / 独立覆盖」只在独立下注 ≥ 30 次时给数，否则显示「—」——
          250 日的留出期有几千个重叠样本，却只有个位数次下注，两者不能混着读。
        </caption>
        <thead>
          <tr>
            <th scope="col">样本期</th>
            <th scope="col">窗口</th>
            <th scope="col" className="num">
              可评估样本
            </th>
            <th scope="col" className="num">
              独立下注
            </th>
            <th scope="col" className="num">
              命中率
            </th>
            <th scope="col" className="num">
              独立命中
            </th>
            <th scope="col" className="num">
              95% CI
            </th>
            <th scope="col" className="num">
              永远看多
            </th>
            <th scope="col" className="num">
              动量基准
            </th>
            <th scope="col" className="num">
              Brier
            </th>
            <th scope="col" className="num">
              覆盖率
            </th>
            <th scope="col" className="num">
              独立覆盖
            </th>
            <th scope="col">说明</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((period) => (
            <tr key={period.label}>
              <th scope="row">{period.label}</th>
              <td>
                {period.window_start && period.window_end
                  ? `${period.window_start} ~ ${period.window_end}`
                  : '—'}
              </td>
              <td className="num">{period.sample_size}</td>
              <td
                className="num"
                title={
                  period.independent_bet_stride
                    ? `每 ${period.independent_bet_stride} 个交易日算一次独立下注 —— 重叠样本不是独立证据`
                    : undefined
                }
              >
                {period.independent_bets ?? '—'}
              </td>
              <td className="num">{pct(period.accuracy)}</td>
              <td className="num">{pct(period.accuracy_independent_bets)}</td>
              <td className="num">{interval(period.accuracy_ci95)}</td>
              <td className="num">{pct(period.baseline_up_accuracy)}</td>
              <td className="num">{pct(period.baseline_momentum_accuracy)}</td>
              <td className="num">{num(period.brier_score)}</td>
              <td className="num">{pct(period.interval_coverage_80)}</td>
              <td className="num">{pct(period.interval_coverage_80_independent_bets)}</td>
              <td className="note">{period.reason ?? ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ReliabilityDetails({ horizons }: { horizons: HorizonResearch[] }) {
  return (
    <>
      {horizons.map((horizon, index) => (
        <details key={horizon.horizon_days} open={index === 0} className="factor">
          <summary>
            <span className="factor__title">{horizon.label} · 可靠性分桶</span>
            <span className="factor__subtitle">
              全样本；每桶对比「平均预测概率」与「实际频率」，两者差距越小，概率越可信。
            </span>
          </summary>
          <div className="factor__body">
            {horizon.reliability_bins.length === 0 ? (
              <p className="note">没有足够的概率样本，未给出分桶。</p>
            ) : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">预测概率区间</th>
                      <th scope="col" className="num">
                        样本
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
                    {horizon.reliability_bins.map((bin, binIndex) => (
                      <tr key={binIndex}>
                        <th scope="row">
                          {bin.lo === null || bin.hi === null
                            ? '—'
                            : `${(bin.lo * 100).toFixed(0)}–${(bin.hi * 100).toFixed(0)}%`}
                        </th>
                        <td className="num">{bin.count}</td>
                        <td className="num">{pct(bin.mean_predicted)}</td>
                        <td className="num">{pct(bin.frequency)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </details>
      ))}
    </>
  )
}

function FactorDetails({ horizons }: { horizons: HorizonResearch[] }) {
  return (
    <>
      {horizons.map((horizon, index) => (
        <details key={horizon.horizon_days} open={index === 0} className="factor">
          <summary>
            <span className="factor__title">{horizon.label} · 因子拆解</span>
            <span className="factor__subtitle">
              全样本口径；命中率低于 50% 说明该因子的方向先验与实际相反，是下一轮候选的线索。
            </span>
          </summary>
          <div className="factor__body">
            <div className="table-scroll">
              <table className="data-table">
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
                  </tr>
                </thead>
                <tbody>
                  {horizon.factors.map((factor) => (
                    <tr key={factor.key}>
                      <th scope="row">
                        {factor.name}
                        <span style={SUB_STYLE}>{factor.key}</span>
                      </th>
                      <td>{factor.category_name}</td>
                      <td className="num">{factor.weight.toFixed(2)}</td>
                      <td>{factor.sign > 0 ? '正向' : factor.sign < 0 ? '反向' : '—'}</td>
                      <td className="num">{factor.samples}</td>
                      <td className="num">{pct(factor.hit_rate)}</td>
                      <td className="num">{num(factor.ic)}</td>
                      <td className="num">{num(factor.rank_ic)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      ))}
    </>
  )
}

function VerdictPanel({ data }: { data: QuantResearchResponse }) {
  const stamp = displayStamp(data.generated_at)
  return (
    <div className="panel" data-testid="research-verdict">
      <div className="panel__head">
        <h3 className="panel__title">{data.verdict.label}</h3>
        <span className="tag">{data.model_version}</span>
      </div>
      <p className="note">{data.verdict.detail}</p>
      <dl className="metrics">
        <div>
          <dt>模型版本</dt>
          <dd>{data.model_version}</dd>
        </div>
        <div>
          <dt>历史留出期起点</dt>
          <dd>{data.holdout_start}</dd>
        </div>
        <div>
          <dt>前向留出期起点</dt>
          <dd>{data.active_holdout_start}</dd>
        </div>
        <div>
          <dt>数据截至</dt>
          <dd>{data.as_of ?? '—'}</dd>
        </div>
        <div>
          <dt>报告生成</dt>
          <dd>{stamp ?? '—'}</dd>
        </div>
        <div>
          <dt>本次结果</dt>
          <dd>{data.cached ? '来自 1 小时缓存' : '本次现算'}</dd>
        </div>
      </dl>
    </div>
  )
}

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; data: QuantResearchResponse }

export default function ResearchPage() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })

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

  useEffect(() => {
    void load()
  }, [load])

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
            <a href="#skills">技能</a>
            <a href="#reliability">可靠性</a>
            <a href="#factors">因子</a>
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
                intro="预注册封板日之后新增的观测才干净：这一段够不够判、还差多少，是「为什么现在没有结论」的唯一答案。"
              >
                <ForwardWindow horizons={state.data.horizons} />
              </Section>

              <Section
                id="skills"
                title="技能总览"
                intro="五个尺度的方向命中率、基准对照、Brier 技能分与区间覆盖率；数字全部来自走查式回测。留出期一列是历史记录（已被前两轮裁决看过），不是干净的样本外证据。"
              >
                <SkillTable horizons={state.data.horizons} />
                <div style={{ marginTop: 18 }}>
                  <CoverageChart horizons={state.data.horizons} />
                </div>
                {state.data.horizons.map((horizon) => (
                  <details key={horizon.horizon_days} className="factor">
                    <summary>
                      <span className="factor__title">{horizon.label} · 四个样本期明细</span>
                      <span className="factor__subtitle">
                        开发 / 历史留出 / 前向留出（裁决）/ 全样本；样本不足的格子给出原因。
                      </span>
                    </summary>
                    <div className="factor__body">
                      <PeriodDetail horizon={horizon} />
                    </div>
                  </details>
                ))}
              </Section>

              <Section
                id="reliability"
                title="可靠性分桶"
                intro="把预测概率分成十桶，比较「平均预测」与「实际频率」——两者差距越小，概率越可信。"
              >
                <ReliabilityDetails horizons={state.data.horizons} />
              </Section>

              <Section
                id="factors"
                title="因子拆解"
                intro="逐因子的命中率与 IC（全样本口径）。低命中率不是丢脸的指标，是下一轮候选的线索。"
              >
                <FactorDetails horizons={state.data.horizons} />
              </Section>

              <section className="section">
                <p className="note">
                  评估口径、预注册规则与复现命令见仓库内 docs/specs/2026-10-02-研究台报告.md
                  与 docs/specs/2026-10-02-量化策略提升路线图.md；数据不可用时本页只显示原因，不补任何数字。
                </p>
              </section>
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
