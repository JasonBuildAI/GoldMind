import { useGoldData } from '@/contexts/GoldDataContext'
import {
  FRESHNESS_BLOCKS,
  FRESHNESS_STATE_LABEL,
  freshnessSummary,
  useFreshness,
} from '@/contexts/FreshnessContext'
import { displayStamp, formatNumber, formatPercent, formatUsd, trendOf } from '@/lib/format'
import { TESTIDS } from '@/testids'

const NAV = [
  { href: '#conclusion', label: '今日结论' },
  { href: '#market', label: '行情' },
  { href: '#drivers', label: '驱动' },
  { href: '#quant', label: '量化预测' },
  { href: '#strategy', label: '投资策略' },
  { href: '#data-methods', label: '数据与方法' },
  { href: './research.html', label: '研究' },
]

const STATE_TONE: Record<string, string> = {
  unavailable: 'is-down',
  stale: 'is-down',
  analyzing: '',
  pending: '',
  fresh: '',
}

/**
 * 报头：字标 + 锚点导航 + 今日速览（一行结论）+ 数据新鲜度条。
 *
 * 时间只展示后端返回的字段，不用浏览器时钟推算「今天」（见
 * docs/ARCHITECTURE.md 第七节）。新鲜度条由各区块登记，见 FreshnessContext。
 */
export default function Masthead() {
  const { stats, statsError, dollarRealtime } = useGoldData()
  const { entries } = useFreshness()

  const summary = freshnessSummary(entries)

  const bits: string[] = []
  if (stats) {
    bits.push(`纽约黄金 ${formatUsd(stats.current_price)}`)
    bits.push(`近 12 个月 ${formatPercent(stats.window_return)}`)
    const stamp = displayStamp(stats.price_as_of ?? stats.updated_at)
    if (stamp) bits.push(`价格口径 ${stats.price_basis_label || '—'}（${stamp}）`)
  } else if (statsError) {
    bits.push(`行情暂不可用（${statsError}）`)
  } else {
    bits.push('行情读取中…')
  }

  if (dollarRealtime) {
    const trend = trendOf(dollarRealtime.change_percent)
    bits.push(
      `美元指数 ${formatNumber(dollarRealtime.price, 2)} ${trend.symbol}${trend.label} ${formatPercent(
        dollarRealtime.change_percent,
      )}`,
    )
  }

  return (
    <header className="masthead no-print" data-testid={TESTIDS.header}>
      <div className="wrap masthead__row">
        <div className="masthead__brand">
          <h1 className="masthead__name">GoldMind</h1>
          <span className="masthead__sub">黄金市场分析</span>
        </div>

        <nav className="masthead__nav" aria-label="页面导航" data-testid={TESTIDS.headerNav}>
          {NAV.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>
      </div>

      <div className="wrap masthead__brief" data-testid={TESTIDS.todaySummary}>
        <span className="masthead__brief-label">今日速览</span>
        <p className="masthead__brief-line">{bits.join(' · ')}</p>
      </div>

      <div className="wrap masthead__freshness" data-testid={TESTIDS.freshnessBar}>
        <span className="masthead__freshness-label">数据新鲜度</span>
        <span
          className={`freshness__state ${STATE_TONE[summary.state] ?? ''}`}
          data-testid={TESTIDS.freshnessState}
        >
          {summary.label}
        </span>
        <ul className="freshness__list">
          {FRESHNESS_BLOCKS.map((block) => {
            const entry = entries[block.key]
            const state = entry?.state ?? 'pending'
            const stamp = displayStamp(entry?.asOf)
            return (
              <li
                key={block.key}
                className="freshness__item"
                data-testid={`${TESTIDS.freshnessItemPrefix}${block.key}`}
              >
                <span className="freshness__name">{block.label}</span>
                <span className="freshness__stamp">{stamp ?? '时间未知'}</span>
                <span className={`freshness__tag ${STATE_TONE[state] ?? ''}`}>
                  {FRESHNESS_STATE_LABEL[state]}
                </span>
              </li>
            )
          })}
        </ul>
      </div>
    </header>
  )
}