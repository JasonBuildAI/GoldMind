import { useGoldData } from '@/contexts/GoldDataContext'
import { displayStamp } from '@/lib/format'

const NAV = [
  { href: '#market', label: '行情' },
  { href: '#factors', label: '多空' },
  { href: '#institutions', label: '机构' },
  { href: '#messages', label: '消息' },
  { href: '#strategy', label: '策略' },
  { href: '#quant', label: '量化' },
  { href: './research.html', label: '研究' },
  { href: '#conclusion', label: '总结' },
]

/**
 * 报头：字标 + 导航（本页锚点 + 独立研究页）+ 数据来源与数据时间。
 *
 * 数据时间只展示后端返回的 `updated_at`，不用浏览器时钟推算「今天」——
 * 那会在跨时区与跨零点时给出错误的时间（见 docs/ARCHITECTURE.md 第七节）。
 */
export default function Masthead() {
  const { stats } = useGoldData()
  const stamp = displayStamp(stats?.updated_at)
  const bits = [
    stats?.data_source ? `数据来源：${stats.data_source}` : null,
    stamp ? `数据时间：${stamp}` : null,
  ].filter((bit): bit is string => Boolean(bit))

  return (
    <header className="masthead no-print">
      <div className="wrap masthead__row">
        <div className="masthead__brand">
          <h1 className="masthead__name">GoldMind</h1>
          <span className="masthead__sub">黄金市场分析</span>
        </div>

        <nav className="masthead__nav" aria-label="页面导航">
          {NAV.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>

        {bits.length > 0 ? <p className="masthead__stamp">{bits.join(' · ')}</p> : null}
      </div>
    </header>
  )
}
