/**
 * 界面上所有金额、百分比与时间戳的统一格式。
 *
 * 各区块原先各写一套 `toLocaleString` / `toFixed`，同一种数字在不同地方长得不一样。
 * 这里只做格式化，不推算日期 —— 「今天是几号」必须用后端返回的字段，
 * 不得用 `new Date()` 取（项目红线，见 docs/ARCHITECTURE.md 第七节）。
 */

const USD = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/**
 * 美元金额 4702.2 -> "$4,702.20"。
 * 没有值（目标价这类可为 null 的字段）时给「—」——
 * Intl 会把 null 当 0 渲染成 "$0.00"，那是一个并不存在的价格。
 */
export function formatUsd(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `$${USD.format(value)}`
}

/** 坐标轴用的紧凑金额 4702.2 -> "$4,702" */
export function formatUsdCompact(value: number): string {
  return `$${Math.round(value).toLocaleString('en-US')}`
}

/** 普通数值 98.421 -> "98.42" */
export function formatNumber(value: number, digits = 2): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

/** 不带正负号的百分比数值 6.59 -> "6.6%"（波动率这类「大小」而不是「涨跌」的量） */
export function formatShare(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`
}

/** 涨跌幅 3.852 -> "+3.85%"；-0.5 -> "−0.50%"（用真正的减号，不是连字符） */
export function formatPercent(value: number, digits = 2): string {
  const sign = value >= 0 ? '+' : '\u2212'
  return `${sign}${Math.abs(value).toFixed(digits)}%`
}

/**
 * 涨跌方向的符号与文字。
 *
 * 方向**不能只靠颜色**表达（红涨绿跌只是加强），所以凡是要显示涨跌的地方都从这里取
 * 「▲ 涨 / ▼ 跌 / — 持平」，与数值一起渲染。
 */
export function trendOf(value: number): { symbol: string; label: string } {
  if (value > 0) return { symbol: '▲', label: '涨' }
  if (value < 0) return { symbol: '▼', label: '跌' }
  return { symbol: '—', label: '持平' }
}

/**
 * 后端返回的时间字段按原样展示：'2026-02-03T10:00:00' -> '2026-02-03 10:00'。
 * 字段缺失时返回 null，由调用方决定「不显示」，而不是拿当前时间顶上。
 */
export function displayStamp(value?: string | null): string | null {
  if (!value) return null
  return value.replace('T', ' ').slice(0, 16)
}
