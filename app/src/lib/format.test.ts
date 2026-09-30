import { describe, expect, it } from 'vitest'

import {
  displayStamp,
  formatNumber,
  formatPercent,
  formatShare,
  formatUsd,
  formatUsdCompact,
  trendOf,
} from './format'

describe('formatUsd', () => {
  it('千分位加两位小数', () => {
    expect(formatUsd(4702.2)).toBe('$4,702.20')
  })
})

describe('formatUsdCompact', () => {
  it('坐标轴用的紧凑金额', () => {
    expect(formatUsdCompact(4702.2)).toBe('$4,702')
  })
})

describe('formatNumber', () => {
  it('固定小数位', () => {
    expect(formatNumber(98.421)).toBe('98.42')
    expect(formatNumber(98, 1)).toBe('98.0')
  })
})

describe('formatShare', () => {
  it('不带正负号的百分比（波动率这类大小）', () => {
    expect(formatShare(6.59)).toBe('6.6%')
  })
})

describe('formatPercent', () => {
  it('正数带 +，负数用真正的减号', () => {
    expect(formatPercent(3.852)).toBe('+3.85%')
    expect(formatPercent(-0.5)).toBe('\u22120.50%')
    expect(formatPercent(0)).toBe('+0.00%')
  })
})

describe('trendOf', () => {
  it('方向同时给符号与文字 —— 颜色之外还有第二种信号', () => {
    expect(trendOf(1)).toEqual({ symbol: '▲', label: '涨' })
    expect(trendOf(-1)).toEqual({ symbol: '▼', label: '跌' })
    expect(trendOf(0)).toEqual({ symbol: '—', label: '持平' })
  })
})

describe('displayStamp', () => {
  it('后端给的时间字段按原样展示，不重新推算时区', () => {
    expect(displayStamp('2026-02-03T10:00:00')).toBe('2026-02-03 10:00')
    expect(displayStamp('2026-02-03 10:00:00')).toBe('2026-02-03 10:00')
  })

  it('没有值就返回 null，由调用方决定不显示', () => {
    expect(displayStamp(undefined)).toBeNull()
    expect(displayStamp(null)).toBeNull()
    expect(displayStamp('')).toBeNull()
  })
})
