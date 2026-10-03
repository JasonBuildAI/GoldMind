/**
 * 折线 / 面积图的纯计算部分。
 *
 * 与渲染分开：坐标换算与刻度选取是可以单独测的纯函数，
 * 组件只负责把它们画出来。这样「轴的范围算错了」这类问题不必靠看图发现。
 */

export interface Point {
  x: number
  y: number
}

export interface Scale {
  /** 数据值 → 画布坐标 */
  (value: number): number
}

/** 线性映射；`domain` 的上下界必须不同（调用方保证，见 `paddedDomain`）。 */
export function linearScale(domain: [number, number], range: [number, number]): Scale {
  const [d0, d1] = domain
  const [r0, r1] = range
  const span = d1 - d0
  if (span === 0) return () => (r0 + r1) / 2
  return (value: number) => r0 + ((value - d0) / span) * (r1 - r0)
}

/**
 * 给数据上下各留 6% 的余量，避免极值贴着边框。
 * 全等（最高 = 最低）时人为撑开一点，否则 `linearScale` 会退化成一个点。
 */
export function paddedDomain(values: readonly number[]): [number, number] {
  const finite = values.filter((value) => Number.isFinite(value))
  if (finite.length === 0) return [0, 1]

  const min = Math.min(...finite)
  const max = Math.max(...finite)
  if (min === max) {
    const pad = Math.abs(min) * 0.06 || 1
    return [min - pad, max + pad]
  }
  const pad = (max - min) * 0.06
  return [min - pad, max + pad]
}

/** 把一串数值折成 SVG path 的 `d`；空数组返回空串（调用方据此不画线）。 */
export function linePath(values: readonly number[], scaleY: Scale, xs: readonly number[]): string {
  if (values.length === 0) return ''
  return values
    .map((value, index) => `${index === 0 ? 'M' : 'L'}${xs[index].toFixed(2)},${scaleY(value).toFixed(2)}`)
    .join(' ')
}

/** 面积图：在折线下方闭合到基线。 */
export function areaPath(
  values: readonly number[],
  scaleY: Scale,
  xs: readonly number[],
  baselineY: number,
): string {
  if (values.length === 0) return ''
  const top = linePath(values, scaleY, xs)
  const lastX = xs[xs.length - 1].toFixed(2)
  const firstX = xs[0].toFixed(2)
  return `${top} L${lastX},${baselineY.toFixed(2)} L${firstX},${baselineY.toFixed(2)} Z`
}

/**
 * 取「好看」的刻度值：步长落在 1 / 2 / 2.5 / 5 / 10 × 10ⁿ 上，
 * 而不是把区间硬切几刀（那样会出现 4173.62 这种刻度）。
 */
export function niceTicks(domain: [number, number], count = 5): number[] {
  const [min, max] = domain
  const span = max - min
  if (!Number.isFinite(span) || span <= 0) return [min]

  const rough = span / count
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const normalized = rough / magnitude
  const step =
    (normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10) *
    magnitude

  const ticks: number[] = []
  const start = Math.ceil(min / step) * step
  for (let value = start; value <= max + step * 1e-9; value += step) {
    ticks.push(Number(value.toFixed(10)))
  }
  return ticks
}

/**
 * 均匀取 `count` 个横轴位置（含首尾）。
 * 数据点少于 count 时逐个返回，避免出现重复的刻度标签。
 */
export function evenIndices(length: number, count: number): number[] {
  if (length <= 0) return []
  if (length <= count) return Array.from({ length }, (_, index) => index)
  const step = (length - 1) / (count - 1)
  return Array.from({ length: count }, (_, index) => Math.round(index * step))
}
