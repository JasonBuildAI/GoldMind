/**
 * 研究页的数值格式化入口。
 *
 * `pct / num / interval / pp` 的唯一真源是量化区块的共用模块
 * （`views/dashboard/quant/shared.ts`）—— 那里写明「只服务量化预测与研究两处」，
 * 研究页与回测必须用同一套口径，所以这里只做一次转发，不复制第二份实现。
 * 研究页自己特有的只有「与永远看多的差」的颜色判定。
 */

export { interval, num, pct, pp } from '@/views/dashboard/quant/shared'

/**
 * 与「永远看多」的差：符号由 `pp()` 给，颜色只是加强 ——
 * 不让颜色单独承载语义（见 docs/20-前端设计规范.md 第四节）。
 */
export function diffTone(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return ''
  if (value > 0) return 'is-up'
  if (value < 0) return 'is-down'
  return ''
}
