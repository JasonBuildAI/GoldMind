import { useMemo } from 'react'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useGoldData } from '@/contexts/GoldDataContext'
import { displayStamp, formatNumber, formatShare, formatUsd, formatUsdCompact } from '@/lib/format'
import { token } from '@/lib/tokens'

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
    <circle
      cx={cx}
      cy={cy}
      r={3}
      fill={token('--gold')}
      stroke={token('--surface')}
      strokeWidth={1}
    />
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

  const chartError = dailyError ?? correlationError
  const chartLoading = dailyLoading || correlationLoading

  function chartState(testId: string) {
    if (chartError) {
      return (
        <StateBlock
          kind="unavailable"
          testId={testId}
          title="价格数据暂不可用"
          detail={chartError}
        />
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

  return (
    <Section
      id="market"
      title="行情"
      intro="纽约黄金与美元指数的当日报价与近期走势。取不到数据时如实说明，不用内置序列顶替。"
      actions={
        stats ? (
          <span className="tag" title={stats.data_source}>
            {stats.is_realtime ? '实时报价' : '历史数据'}
          </span>
        ) : undefined
      }
    >
      {!stats && statsLoading ? <StateBlock title="正在读取行情…" /> : null}

      {!stats && !statsLoading ? (
        <StateBlock
          kind="unavailable"
          testId="market-unavailable"
          title="金价数据暂不可用"
          detail={statsError ?? '没能从后端取到行情数据，请稍后重试。'}
        />
      ) : null}

      {stats ? (
        <div className="space-y-8">
          <div className="grid gap-8 lg:grid-cols-3">
            <Quote
              label="纽约黄金"
              value={formatUsd(stats.current_price)}
              change={stats.window_return}
              changeNote={`${stats.window_label}涨跌`}
              meta={`${stats.data_source} · 数据时间 ${displayStamp(stats.updated_at) ?? '未提供'}`}
              title={stats.data_source}
            />

            {dollarRealtime ? (
              <Quote
                label="美元指数"
                value={formatNumber(dollarRealtime.price, 2)}
                change={dollarRealtime.change_percent}
                changeNote="较昨收"
                meta={`${dollarRealtime.source} · 交易日 ${dollarRealtime.date}`}
                title={dollarRealtime.source}
              />
            ) : (
              <StateBlock title="美元指数暂不可用" detail="没能取到美元指数报价。" />
            )}

            <div className="panel">
              <h3 className="panel__title">关键数据（{stats.window_label}）</h3>
              <dl className="metrics">
                <div>
                  <dt>期间最高</dt>
                  <dd>{formatUsd(stats.max_price)}</dd>
                  <dd className="metrics__note">{stats.max_date}</dd>
                </div>
                <div>
                  <dt>期间最低</dt>
                  <dd>{formatUsd(stats.min_price)}</dd>
                  <dd className="metrics__note">{stats.min_date}</dd>
                </div>
                <div>
                  <dt>高低振幅</dt>
                  <dd>{formatShare(stats.amplitude)}</dd>
                  <dd className="metrics__note">(最高−最低)/最低，非波动率</dd>
                </div>
                <div>
                  <dt>市场状态</dt>
                  <dd className={statusTone(stats.market_status)}>{stats.market_status}</dd>
                  <dd className="metrics__note">{stats.market_status_desc}</dd>
                </div>
              </dl>
            </div>
          </div>

          <div className="panel">
            <Tabs defaultValue="trend">
              <TabsList>
                <TabsTrigger value="trend">价格走势</TabsTrigger>
                <TabsTrigger value="comparison">黄金与美元指数</TabsTrigger>
              </TabsList>

              <TabsContent value="trend">
                {daily.length === 0 ? (
                  chartState('market-chart-unavailable')
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
              </TabsContent>

              <TabsContent value="comparison">
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
              </TabsContent>
            </Tabs>
          </div>

          <p className="provenance" style={{ marginTop: 0 }}>
            报价来自数据源，历史序列来自数据库；两者取不到时本页不显示替代数据。
          </p>
        </div>
      ) : null}
    </Section>
  )
}
