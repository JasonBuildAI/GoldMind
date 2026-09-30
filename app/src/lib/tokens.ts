/**
 * 读取设计令牌的计算值，供 SVG 图表使用。
 *
 * 颜色与字体的唯一真源是 src/styles/tokens.css，但 SVG 的 stroke / fill 属性
 * 不认 CSS 变量，只能用具体的颜色字符串，所以在运行时从 `:root` 读。
 * 测试环境没有样式表（读出来是空串），退回令牌常量 —— 这里的值必须与
 * tokens.css 保持一致，改令牌时两边一起改。
 */
const FALLBACK: Record<string, string> = {
  '--paper': '#f6f6f3',
  '--surface': '#ffffff',
  '--ink': '#17191b',
  '--ink-muted': '#5c6166',
  '--rule': '#d9dad4',
  '--gold': '#8a6a12',
  '--up': '#b4232a',
  '--down': '#16653c',
}

export function token(name: keyof typeof FALLBACK): string {
  if (typeof document === 'undefined') return FALLBACK[name]
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  return value || FALLBACK[name]
}
