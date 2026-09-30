import { describe, expect, it } from 'vitest'

import { token } from './tokens'

describe('token', () => {
  it('测试环境没有样式表时退回令牌常量，而不是返回空串', () => {
    // 返回空串会让 SVG 折线「没有颜色」，在浏览器里表现为线条消失 ——
    // 宁可退回写死的令牌值，也不要静默画出一条看不见的线。
    expect(token('--gold')).toMatch(/^#[0-9a-f]{6}$/i)
    expect(token('--rule')).toMatch(/^#[0-9a-f]{6}$/i)
    expect(token('--ink-muted')).toMatch(/^#[0-9a-f]{6}$/i)
  })
})
