import { describe, expect, it } from 'vitest'

import { describeApiError } from './apiError'

/**
 * 各区块原先各自写死两句文案，于是**任何**非超时的失败都显示
 * 「获取最新分析失败」—— 包括 429 限流。那既不准确（限流不是分析失败），
 * 也不可操作（没说等多久）。后端的 429 其实带了 `retry_after`，
 * 只是没人用。
 */
const FALLBACK = { fallback: '获取最新分析失败。', timeout: 'AI 分析耗时较长，请稍后重试刷新。' }

function axiosError(status: number, data: unknown = {}, headers: Record<string, string> = {}) {
  return { response: { status, data, headers }, message: `Request failed with status code ${status}` }
}

describe('describeApiError', () => {
  it('429 说清要等多久，而不是笼统的「失败」', () => {
    const message = describeApiError(axiosError(429, { retry_after: 42 }), FALLBACK)

    expect(message).toContain('请求过于频繁')
    expect(message).toContain('42')
    expect(message).not.toContain('分析失败')
  })

  it('429 没给 retry_after 时也能给出可操作的话', () => {
    const message = describeApiError(axiosError(429), FALLBACK)

    expect(message).toContain('请求过于频繁')
    expect(message).toContain('稍后')
  })

  it('能从标准的 Retry-After 头读到等待时间', () => {
    // 后端同时给了 body 与标准头；客户端两种都要认
    const message = describeApiError(axiosError(429, {}, { 'retry-after': '7' }), FALLBACK)

    expect(message).toContain('7')
  })

  it('503 用后端给的原因', () => {
    const message = describeApiError(axiosError(503, { detail: '无法获取实时美元指数' }), FALLBACK)

    expect(message).toBe('无法获取实时美元指数')
  })

  it('503 没有原因时给一句可读的兜底', () => {
    expect(describeApiError(axiosError(503), FALLBACK)).toContain('后端暂时不可用')
  })

  it('其它 4xx 优先用后端的说明', () => {
    const message = describeApiError(axiosError(422, { detail: 'start_date 的格式应为 YYYY-MM-DD' }), FALLBACK)

    expect(message).toContain('YYYY-MM-DD')
  })

  it('超时用超时文案', () => {
    const err = { code: 'ECONNABORTED', message: 'timeout of 120000ms exceeded' }

    expect(describeApiError(err, FALLBACK)).toBe('AI 分析耗时较长，请稍后重试刷新。')
  })

  it('超时也可以从 message 认出来', () => {
    expect(describeApiError({ message: 'timeout of 30000ms exceeded' }, FALLBACK)).toContain('AI 分析耗时较长')
  })

  it('没有 response 时说明是连不上后端', () => {
    expect(describeApiError(new Error('Network Error'), FALLBACK)).toContain('无法连接后端')
  })

  it('认不出的错误才用兜底文案', () => {
    expect(describeApiError(axiosError(500), FALLBACK)).toBe('获取最新分析失败。')
    expect(describeApiError(undefined, FALLBACK)).toContain('无法连接后端')
  })

  it('不给超时文案时退回兜底', () => {
    const err = { code: 'ECONNABORTED' }

    expect(describeApiError(err, { fallback: '取不到行情数据。' })).toBe('取不到行情数据。')
  })

  it('retry_after 是小数时向上取整（等待时间说整数更自然）', () => {
    const message = describeApiError(axiosError(429, { retry_after: 3.2 }), FALLBACK)

    expect(message).toContain('4')
  })
})
