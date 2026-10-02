import { useMemo, type ReactNode } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import Quote from '@/components/Quote'
import Section from '@/components/Section'
import StateBlock from '@/components/StateBlock'
import { useFreshnessBlock } from '@/contexts/FreshnessContext'
import { useGoldData } from '@/contexts/GoldDataContext'
import { displayStamp, formatNumber, formatPercent, formatUsd, formatUsdCompact, trendOf } from '@/lib/format'
import { token } from '@/lib/tokens'
import { fieldTestId, TESTIDS } from '@/testids'

interface PricePoint {
  date: string
  price: number
}

interface ComparisonPoint {
  date: string
  gold_price: number
  dollar_index: number
}

/** 给纵轴留出上下边距，避免折线贴着坐标轴。 */
function paddedDomain(values: number[]): [number, number] {
  if (values.length === 0) return [0, 1]
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || Math.abs(max) * 0.02 || 1
  return [min - span * 0.08, max + span * 0.08]
}

/** 只在最后一个数据点上画一个静态标记表示「最新」—— 不做闪烁动画。 */
function LastPoint({
  cx,
  cy,
  index,
  count,
}: {
  cx?: number
  cy?: number
  index?: number
  count: number
}) {
  if (cx == null || cy == null || index !== count - 1) return null
  return (
    <circle cx={cx} cy={cy} r={3} fill={token('--gold')} stroke={token('--surface')} strokeWidth={1} />
  )
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="chart-tip">
      <div>{label}</div>
      {payload.map((entry: any) => (
        <div className="chart-tip__row" key={entry.dataKey}>
          <span>{entry.name}</span>
          <span className="num">{formatNumber(Number(entry.value), 2)}</span>
        </div>
      ))}
    </div>
  )
}

const AXIS_TICK = { fill: token('--ink-muted'), fontSize: 11 }

/** 市场状态只决定文字颜色（红涨绿跌），方向本身仍由文字表达。 */
function statusTone(status: string): string {
  if (status.includes('涨')) return 'is-up'
  if (status.includes('跌') || status.includes('回调')) return 'is-down'
  return ''
}

function Field({ path, children }: { path: string; children: ReactNode }) {
  return <span data-testid={fieldTestId(path)}>{children}</span>
}

/**
 * 行情：一行结论 + 报价表（每个字段都有槽位）在最上，走势图与逐日数据收进
 * 一层折叠。数字一律进表格；口径与来源固定成列。
 */
export default function Market() {
  const {
    stats,
    statsLoading,
    statsError,
    dailyPrices,
    dailyLoading,
    dailyError,
    correlationData,
    correlationLoading,
    correlationError,
    dollarRealtime,
  } = useGoldData()

  // 日期是 YYYY-MM-DD，直接按字符串排序 —— 不 new Date()（那是 UTC 解析，
  // 东八区凌晨会把交易日算错一天，见 docs/ARCHITECTURE.md 第七节）。
  const daily = useMemo<PricePoint[]>(
    () =>
      dailyPrices
        .map((item) => ({ date: item.date, price: item.price }))
        .sort((a, b) => a.date.localeCompare(b.date)),
    [dailyPrices],
  )

  const comparison = useMemo<ComparisonPoint[]>(
    () =>
      correlationData
        .map((item) => ({
          date: item.date,
          gold_price: item.gold_price,
          dollar_index: item.dollar_index,
        }))
        .sort((a, b) => a.date.localeCompare(b.date)),
    [correlationData],
  )

  const dailyRows = useMemo(
    () => [...dailyPrices].sort((a, b) => b.date.localeCompare(a.date)),
    [dailyPrices],
  )
  const correlationRows = useMemo(
    () => [...correlationData].sort((a, b) => b.date.localeCompare(a.date)),
    [correlationData],
  )

  const chartError = dailyError ?? correlationError
  const chartLoading = dailyLoading || correlationLoading

  useFreshnessBlock(
    'market',
    '行情',
    stats ? 'fresh' : statsLoading ? 'pending' : 'unavailable',
    stats?.price_as_of ?? stats?.updated_at ?? null,
  )
  useFreshnessBlock(
    'dollar',
    '美元指数',
    dollarRealtime ? 'fresh' : statsLoading ? 'pending' : 'unavailable',
    dollarRealtime?.updated_at ?? dollarRealtime?.date ?? null,
  )

  const goldTrend = stats ? trendOf(stats.window_return) : null
  const dollarTrend = dollarRealtime ? trendOf(dollarRealtime.change_percent) : null

  function chartState(testId: string) {
    if (chartError) {
      return (
        <StateBlock kind="unavailable" testId={testId} title="价格数据暂不可用" detail={chartError} />
      )
    }
    if (chartLoading) {
      return <StateBlock testId={testId} title="正在读取价格数据…" />
    }
    return (
      <StateBlock
        kind="unavailable"
        testId={testId}
        title="价格数据暂不可用"
        detail="后端还没有可用的历史行情。"
      />
    )
  }

  let body
  if (!stats && statsLoading) {
    body = <StateBlock title="正在读取行情…" />
  } else if (!stats) {
    body = (
      <StateBlock
        kind="unavailable"
        testId={TESTIDS.marketUnavailable}
        title="金价数据暂不可用"
        detail={statsError ?? '没能从后端取到行情数据，请稍后重试。'}
      />
    )
  } else {
    body = (
      <div className="space-y-8" data-testid={TESTIDS.marketStats}>
        <p className="section__conclusion">
          纽约黄金 <Field path="stats.current_price">{formatUsd(stats.current_price)}</Field>
          <span className={` ${statusTone(stats.market_status)}`}>
            （{stats.market_status || '状态未知'}
            {goldTrend ? ` ${goldTrend.symbol}${goldTrend.label}` : ''}
            {` ${formatPercent(stats.window_return)}`}）
          </span>
          <span className="note">
            {' '}
            区间：{stats.window_label}（{stats.window_start} ~ {stats.window_end}）；高低振幅{' '}
            {formatPercent(stats.amplitude)}。
          </span>
        </p>

        <div className="grid gap-8 lg:grid-cols-2">
          <div className="panel">
            <h3 className="panel__title">纽约黄金</h3>
            <Quote
              label="最新价格"
              value={formatUsd(stats.current_price)}
              change={stats.window_return}
              changeNote={stats.window_label}
              meta={`${stats.price_basis_label || '口径未知'} · 数据来源：${stats.data_source || '未知'} · 数据时间：${
                displayStamp(stats.price_as_of ?? stats.updated_at) ?? '未知'
              }`}
              title={stats.data_source}
            />
            <div data-testid={TESTIDS.goldQuote} className="note">
              {stats.is_realtime ? '实时报价' : '历史数据'} · 口径 {stats.price_basis_label || '—'}
            </div>
          </div>

          <div className="panel">
            <h3 className="panel__title">美元指数</h3>
            {dollarRealtime ? (
              <>
                <Quote
                  label="最新报价"
                  value={formatNumber(dollarRealtime.price, 2)}
                  change={dollarRealtime.change_percent}
                  changeNote="较前收"
                  meta={`数据来源：${dollarRealtime.source || '未知'} · 数据时间：${
                    displayStamp(dollarRealtime.updated_at) ?? '未知'
                  }`}
                />
                <div data-testid={TESTIDS.dollarQuote} className="note">
                  交易日 {dollarRealtime.date || '—'}
                  {dollarTrend ? ` · 方向 ${dollarTrend.symbol}${dollarTrend.label}` : ''}
                </div>
              </>
            ) : (
              <StateBlock title="美元指数暂不可用" detail="没能取到实时美元指数。" />
            )}
          </div>
        </div>

        <div className="panel">
          <h3 className="panel__title">行情快照（全部字段）</h3>
          <div className="table-scroll">
            <table className="data-table" data-testid="market-snapshot-table">
              <thead>
                <tr>
                  <th scope="col">字段</th>
                  <th scope="col">值</th>
                  <th scope="col">口径 / 来源</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['当前价', <Field path="stats.current_price">{formatUsd(stats.current_price)}</Field>, 'stats.current_price'],
                  ['区间起价', <Field path="stats.start_price">{formatUsd(stats.start_price)}</Field>, 'stats.start_price'],
                  ['区间标签', <Field path="stats.window_label">{stats.window_label || '—'}</Field>, 'stats.window_label'],
                  ['区间起', <Field path="stats.window_start">{stats.window_start || '—'}</Field>, 'stats.window_start'],
                  ['区间末', <Field path="stats.window_end">{stats.window_end || '—'}</Field>, 'stats.window_end'],
                  ['区间涨跌', <Field path="stats.window_return">{formatPercent(stats.window_return)}</Field>, 'stats.window_return'],
                  ['期间最高', <Field path="stats.max_price">{formatUsd(stats.max_price)}</Field>, 'stats.max_price'],
                  ['最高日', <Field path="stats.max_date">{stats.max_date || '—'}</Field>, 'stats.max_date'],
                  ['期间最低', <Field path="stats.min_price">{formatUsd(stats.min_price)}</Field>, 'stats.min_price'],
                  ['最低日', <Field path="stats.min_date">{stats.min_date || '—'}</Field>, 'stats.min_date'],
                  ['高低振幅', <Field path="stats.amplitude">{formatPercent(stats.amplitude)}</Field>, 'stats.amplitude'],
                  ['市场状态', <Field path="stats.market_status">{stats.market_status || '—'}</Field>, 'stats.market_status'],
                  ['状态说明', <Field path="stats.market_status_desc">{stats.market_status_desc || '—'}</Field>, 'stats.market_status_desc'],
                  ['数据时间', <Field path="stats.updated_at">{displayStamp(stats.updated_at) ?? '—'}</Field>, 'stats.updated_at'],
                  ['数据来源', <Field path="stats.data_source">{stats.data_source || '—'}</Field>, 'stats.data_source'],
                  ['是否实时', <Field path="stats.is_realtime">{stats.is_realtime ? '是（实时报价）' : '否（数据库历史）'}</Field>, 'stats.is_realtime'],
                  ['价格口径', <Field path="stats.price_basis">{stats.price_basis || '—'}</Field>, 'stats.price_basis'],
                  ['口径说明', <Field path="stats.price_basis_label">{stats.price_basis_label || '—'}</Field>, 'stats.price_basis_label'],
                  ['口径时间', <Field path="stats.price_as_of">{displayStamp(stats.price_as_of) ?? '—'}</Field>, 'stats.price_as_of'],
                ].map(([label, value, key]) => (
                  <tr key={String(key)}>
                    <th scope="row">{label}</th>
                    <td>{value}</td>
                    <td className="note">{String(key)}</td>
                  </tr>
                ))}
                {dollarRealtime ? (
                  <>
                    <tr>
                      <th scope="row">美元指数最新</th>
                      <td>
                        <Field path="dollar.price">{formatNumber(dollarRealtime.price, 2)}</Field>
                      </td>
                      <td className="note">dollar.price</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数前收</th>
                      <td>
                        <Field path="dollar.previous_close">
                          {formatNumber(dollarRealtime.previous_close, 2)}
                        </Field>
                      </td>
                      <td className="note">dollar.previous_close</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数涨跌</th>
                      <td>
                        <Field path="dollar.change">
                          {dollarRealtime.change === null || dollarRealtime.change === undefined
                            ? '—'
                            : formatNumber(dollarRealtime.change, 2)}
                        </Field>
                      </td>
                      <td className="note">dollar.change</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数涨跌幅</th>
                      <td>
                        <Field path="dollar.change_percent">
                          {formatPercent(dollarRealtime.change_percent)}
                        </Field>
                      </td>
                      <td className="note">dollar.change_percent</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数开盘</th>
                      <td>
                        <Field path="dollar.open">
                          {dollarRealtime.open === null || dollarRealtime.open === undefined
                            ? '—'
                            : formatNumber(dollarRealtime.open, 2)}
                        </Field>
                      </td>
                      <td className="note">dollar.open</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数最高</th>
                      <td>
                        <Field path="dollar.high">
                          {dollarRealtime.high === null || dollarRealtime.high === undefined
                            ? '—'
                            : formatNumber(dollarRealtime.high, 2)}
                        </Field>
                      </td>
                      <td className="note">dollar.high</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数最低</th>
                      <td>
                        <Field path="dollar.low">
                          {dollarRealtime.low === null || dollarRealtime.low === undefined
                            ? '—'
                            : formatNumber(dollarRealtime.low, 2)}
                        </Field>
                      </td>
                      <td className="note">dollar.low</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数时间</th>
                      <td>
                        <Field path="dollar.updated_at">
                          {displayStamp(dollarRealtime.updated_at) ?? '—'}
                        </Field>
                      </td>
                      <td className="note">dollar.updated_at</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数交易日</th>
                      <td>
                        <Field path="dollar.date">{dollarRealtime.date || '—'}</Field>
                      </td>
                      <td className="note">dollar.date</td>
                    </tr>
                    <tr>
                      <th scope="row">美元指数来源</th>
                      <td>
                        <Field path="dollar.source">{dollarRealtime.source || '—'}</Field>
                      </td>
                      <td className="note">dollar.source</td>
                    </tr>
                  </>
                ) : null}
              </tbody>
            </table>
          </div>
          <p className="provenance">
            报价来自数据源，历史序列来自数据库；两者取不到时本页不显示替代数据。
            价格口径的完整图例见「数据与方法」一节。
          </p>
        </div>

        <details className="row-details" data-testid={TESTIDS.marketChart}>
          <summary>展开走势图与逐日数据（{dailyRows.length} 个交易日 / {correlationRows.length} 个对比点）</summary>
          <div className="space-y-8" style={{ marginTop: 12 }}>
            {daily.length === 0 ? (
              chartState('market-daily-unavailable')
            ) : (
              <figure>
                <ResponsiveContainer width="100%" height={320}>
                  <AreaChart data={daily} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid stroke={token('--rule')} strokeDasharray="2 4" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={AXIS_TICK}
                      tickLine={false}
                      axisLine={{ stroke: token('--rule') }}
                      minTickGap={48}
                      tickFormatter={(value: string) => value.slice(5)}
                    />
                    <YAxis
                      domain={paddedDomain(daily.map((point) => point.price))}
                      tick={AXIS_TICK}
                      tickLine={false}
                      axisLine={false}
                      width={64}
                      tickFormatter={(value: number) => formatUsdCompact(value)}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="price"
                      name="纽约黄金"
                      stroke={token('--gold')}
                      strokeWidth={1.5}
                      fill={token('--gold')}
                      fillOpacity={0.08}
                      dot={((props: any) => (
                        <LastPoint cx={props.cx} cy={props.cy} index={props.index} count={daily.length} />
                      )) as any}
                      activeDot={{ r: 3, fill: token('--gold'), stroke: token('--surface') }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
                <figcaption className="provenance">
                  最近 {daily.length} 个交易日 · 来源：{stats.data_source}
                </figcaption>
              </figure>
            )}

            {comparison.length === 0 ? (
              chartState('market-comparison-unavailable')
            ) : (
              <figure>
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={comparison} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid stroke={token('--rule')} strokeDasharray="2 4" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={AXIS_TICK}
                      tickLine={false}
                      axisLine={{ stroke: token('--rule') }}
                      minTickGap={48}
                      tickFormatter={(value: string) => value.slice(5)}
                    />
                    <YAxis
                      yAxisId="left"
                      domain={paddedDomain(comparison.map((point) => point.gold_price))}
                      tick={AXIS_TICK}
                      tickLine={false}
                      axisLine={false}
                      width={64}
                      tickFormatter={(value: number) => formatUsdCompact(value)}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      domain={paddedDomain(comparison.map((point) => point.dollar_index))}
                      tick={AXIS_TICK}
                      tickLine={false}
                      axisLine={false}
                      width={48}
                      tickFormatter={(value: number) => formatNumber(value, 1)}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="gold_price"
                      name="纽约黄金"
                      stroke={token('--gold')}
                      strokeWidth={1.5}
                      dot={false}
                      activeDot={{ r: 3, fill: token('--gold'), stroke: token('--surface') }}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="dollar_index"
                      name="美元指数"
                      stroke={token('--ink')}
                      strokeWidth={1.5}
                      strokeDasharray="4 3"
                      dot={false}
                      activeDot={{ r: 3, fill: token('--ink'), stroke: token('--surface') }}
                    />
                  </LineChart>
                </ResponsiveContainer>
                <figcaption className="provenance">
                  左轴：纽约黄金（美元/盎司）· 右轴：美元指数 · 共 {comparison.length} 个交易日
                </figcaption>
              </figure>
            )}

            <div className="panel">
              <h3 className="panel__title">逐日金价（{dailyRows.length} 行）</h3>
              <div className="table-scroll">
                <table className="data-table" data-testid={TESTIDS.dailyTable}>
                  <thead>
                    <tr>
                      <th scope="col">日期</th>
                      <th scope="col" className="num">
                        价格
                      </th>
                      <th scope="col" className="num">
                        成交量
                      </th>
                      <th scope="col">口径</th>
                      <th scope="col">口径说明</th>
                      <th scope="col">来源</th>
                      <th scope="col">数据截至</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dailyRows.map((row) => (
                      <tr key={row.date}>
                        <th scope="row">
                          <Field path="daily.date">{row.date}</Field>
                        </th>
                        <td className="num">
                          <Field path="daily.price">{formatUsd(row.price)}</Field>
                        </td>
                        <td className="num">
                          <Field path="daily.volume">{formatNumber(row.volume, 0)}</Field>
                        </td>
                        <td>
                          <Field path="daily.basis">{row.basis ?? '—'}</Field>
                        </td>
                        <td>
                          <Field path="daily.basis_label">{row.basis_label ?? '—'}</Field>
                        </td>
                        <td className="note">
                          <Field path="daily.source">{row.source ?? '—'}</Field>
                        </td>
                        <td className="note">
                          <Field path="daily.as_of">{displayStamp(row.as_of) ?? '—'}</Field>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="panel">
              <h3 className="panel__title">金价与美元指数对照（{correlationRows.length} 行）</h3>
              <div className="table-scroll">
                <table className="data-table" data-testid={TESTIDS.correlationTable}>
                  <thead>
                    <tr>
                      <th scope="col">日期</th>
                      <th scope="col" className="num">
                        金价
                      </th>
                      <th scope="col">金价口径</th>
                      <th scope="col">金价来源</th>
                      <th scope="col" className="num">
                        美元指数
                      </th>
                      <th scope="col">美元口径</th>
                      <th scope="col">美元来源</th>
                      <th scope="col">数据截至</th>
                    </tr>
                  </thead>
                  <tbody>
                    {correlationRows.map((row) => (
                      <tr key={row.date}>
                        <th scope="row">
                          <Field path="correlation.date">{row.date}</Field>
                        </th>
                        <td className="num">
                          <Field path="correlation.gold_price">{formatUsd(row.gold_price)}</Field>
                        </td>
                        <td>
                          <Field path="correlation.gold_basis">{row.gold_basis ?? '—'}</Field>
                          <span className="note">
                            {' '}
                            <Field path="correlation.gold_basis_label">
                              {row.gold_basis_label ?? '—'}
                            </Field>
                          </span>
                        </td>
                        <td className="note">
                          <Field path="correlation.gold_source">{row.gold_source ?? '—'}</Field>
                        </td>
                        <td className="num">
                          <Field path="correlation.dollar_index">
                            {formatNumber(row.dollar_index, 2)}
                          </Field>
                        </td>
                        <td>
                          <Field path="correlation.dollar_basis">{row.dollar_basis ?? '—'}</Field>
                          <span className="note">
                            {' '}
                            <Field path="correlation.dollar_basis_label">
                              {row.dollar_basis_label ?? '—'}
                            </Field>
                          </span>
                        </td>
                        <td className="note">
                          <Field path="correlation.dollar_source">{row.dollar_source ?? '—'}</Field>
                        </td>
                        <td className="note">
                          <Field path="correlation.as_of">{displayStamp(row.as_of) ?? '—'}</Field>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </details>
      </div>
    )
  }

  return (
    <Section
      id="market"
      title="行情"
      intro="纽约黄金与美元指数的当日报价与近期走势；每行都带口径、来源与数据截至。取不到数据时如实说明，不用内置序列顶替。"
      actions={
        stats ? (
          <span className="tag" title={stats.data_source}>
            {stats.is_realtime ? '实时报价' : '历史数据'}
          </span>
        ) : undefined
      }
    >
      {body}
    </Section>
  )
}