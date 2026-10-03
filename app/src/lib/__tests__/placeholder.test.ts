import { describe, expect, it } from 'vitest'

import { isPlaceholder, PLACEHOLDER_NOTICE } from '../placeholder'

describe('isPlaceholder', () => {
  it('识别因子/机构/建议的占位标记（status === analyzing）', () => {
    expect(isPlaceholder({ cached: false, status: 'analyzing' })).toBe(true)
  })

  it('识别市场总结的占位标记（cache_source === default）', () => {
    // 两种服务的标记不同，只认其中一个就会漏掉另一半
    expect(isPlaceholder({ cached: true, cache_source: 'default' })).toBe(true)
  })

  it('真实分析结果不算占位', () => {
    expect(isPlaceholder({ cached: true, cache_source: 'file' })).toBe(false)
    expect(isPlaceholder({ cached: true, status: 'ready' })).toBe(false)
  })

  it('没有 metadata 时按真实结果处理', () => {
    expect(isPlaceholder(undefined)).toBe(false)
    expect(isPlaceholder(null)).toBe(false)
    expect(isPlaceholder({})).toBe(false)
  })

  it('提示语明确说明这不是分析结果', () => {
    expect(PLACEHOLDER_NOTICE).toContain('占位内容')
    expect(PLACEHOLDER_NOTICE).toContain('不是本次分析结果')
  })
})
