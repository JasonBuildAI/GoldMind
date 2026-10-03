/**
 * 读取设计令牌的计算值，供 SVG 图表使用。
 *
 * 颜色与字体的唯一真源是 src/styles/tokens.css，但 SVG 的 stroke / fill 属性
 * 不认 CSS 变量，只能用具体的颜色字符串，所以在运行时从 `:root` 读。
 * 测试环境没有样式表（读出来是空串），退回令牌常量 —— 这里的值必须与
 * tokens.css 保持一致，改令牌时两边一起改（`__tests__/tokens.test.ts` 会守住）。
 */
const FALLBACK: Record<string, string> = {
  '--bg': '#f2f2f7',
  '--surface': '#ffffff',
  '--surface-2': '#fbfbfd',
  '--separator': '#d8d8de',
  '--text': '#1d1d1f',
  '--text-secondary': '#6e6e73',
  '--accent': '#0071e3',
  '--gold': '#a67c00',
  '--up': '#c8102e',
  '--down': '#1d7a3e',
}

/** 图表可能用到的令牌名；写错名字在类型层面就报错。 */
export type TokenName = keyof typeof FALLBACK

export function token(name: TokenName): string {
  if (typeof document === 'undefined') return FALLBACK[name]
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  return value || FALLBACK[name]
}

/** 令牌的兜底值，给需要「一定拿得到颜色」的场景（如 SSR、导出）。 */
export function tokenFallback(name: TokenName): string {
  return FALLBACK[name]
}
