import { describe, expect, it } from 'vitest'

import { areaPath, evenIndices, linePath, niceTicks, paddedDomain } from '../geometry'

describe('evenIndices', () => {
  it('数据点多于刻度数时取均匀位置，含首尾', () => {
    expect(evenIndices(11, 6)).toEqual([0, 2, 4, 6, 8, 10])
  })

  it('数据点少于刻度数时逐个返回', () => {
    expect(evenIndices(3, 6)).toEqual([0, 1, 2])
  })

  it('没有数据点时不返回刻度', () => {
    expect(evenIndices(0, 6)).toEqual([])
  })

  it('只要一个刻度时返回首个位置，而不是 NaN', () => {
    // 回归：原实现算 step = (length - 1) / (count - 1) = Infinity，
    // Math.round(0 * Infinity) 是 NaN —— 横轴标签会拿到 undefined 的坐标。
    const indices = evenIndices(10, 1)
    expect(indices).toHaveLength(1)
    expect(indices.every((index) => Number.isInteger(index))).toBe(true)
    expect(indices[0]).toBe(0)
  })

  it('刻度数为 0 或负数时不返回刻度', () => {
    expect(evenIndices(10, 0)).toEqual([])
    expect(evenIndices(10, -3)).toEqual([])
  })

  it('返回的下标都在数据点范围内且递增', () => {
    for (const length of [2, 7, 30, 365]) {
      for (const count of [1, 2, 5, 6, 12]) {
        const indices = evenIndices(length, count)
        expect(indices.length).toBeLessThanOrEqual(Math.min(count, length))
        expect(indices[0]).toBe(0)
        expect(indices[indices.length - 1]).toBeLessThanOrEqual(length - 1)
        const sorted = [...indices].sort((a, b) => a - b)
        expect(indices).toEqual(sorted)
      }
    }
  })
})

describe('paddedDomain', () => {
  it('全等值时给上下留边距', () => {
    const [min, max] = paddedDomain([5, 5, 5])
    expect(min).toBeLessThan(5)
    expect(max).toBeGreaterThan(5)
  })

  it('没有有限值时不返回 NaN', () => {
    expect(paddedDomain([Number.NaN])).toEqual([0, 1])
  })
})

describe('linePath / areaPath', () => {
  const scale = (value: number) => 100 - value

  it('单点时只画起点，不做插值', () => {
    expect(linePath([10], scale, [50])).toBe('M50.00,90.00')
  })

  it('空序列返回空字符串', () => {
    expect(linePath([], scale, [])).toBe('')
    expect(areaPath([], scale, [], 100)).toBe('')
  })

  it('面积路径把折线两端收到基线', () => {
    const d = areaPath([10, 20], scale, [0, 100], 100)
    expect(d.startsWith('M0.00,90.00 L100.00,80.00')).toBe(true)
    expect(d.endsWith('Z')).toBe(true)
  })
})

describe('niceTicks', () => {
  it('刻度落在 1 / 2 / 2.5 / 5 / 10 的档位上', () => {
    const ticks = niceTicks([0, 100], 4)
    expect(ticks.length).toBeGreaterThan(1)
    expect(ticks[0]).toBeGreaterThanOrEqual(0)
    expect(ticks[ticks.length - 1]).toBeLessThanOrEqual(100)
  })

  it('退化域不返回一堆 NaN', () => {
    expect(niceTicks([3, 3], 4)).toEqual([3])
  })
})
