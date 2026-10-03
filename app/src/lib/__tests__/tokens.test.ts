import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { token, tokenFallback } from '../tokens'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const TOKENS_CSS = path.resolve(HERE, '../../styles/tokens.css')

describe('token', () => {
  it('测试环境没有样式表时退回令牌常量，而不是返回空串', () => {
    // 返回空串会让 SVG 折线「没有颜色」，在浏览器里表现为线条消失 ——
    // 宁可退回写死的令牌值，也不要静默画出一条看不见的线。
    expect(token('--gold')).toMatch(/^#[0-9a-f]{6}$/i)
    expect(token('--separator')).toMatch(/^#[0-9a-f]{6}$/i)
    expect(token('--text-secondary')).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('兜底值必须与 tokens.css 的声明一致（防漂移）', async () => {
    // FALLBACK 是 tokens.css 的影子：浏览器里读到的是真令牌，测试与
    // 「没有样式表的环境」读到的是影子。两边漂开时页面会静默用错颜色，
    // 这条守卫把「改令牌要一起改」变成可执行的检查。
    const css = await readFile(TOKENS_CSS, 'utf8')

    // 只取 `:root { ... }` 这一段：文件末尾的 @media print 会重新声明
    // --bg / --separator 等（打印时去底色），把它们一起收进来会误报漂移。
    const rootBlock = css.match(/:root\s*\{([\s\S]*?)\n\}/)?.[1] ?? ''
    expect(rootBlock, '没解析出 :root 块，解析逻辑失效了').not.toBe('')

    const declared = new Map<string, string>()
    for (const [, name, value] of rootBlock.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/gim)) {
      declared.set(name, value.trim().toLowerCase())
    }

    const names = [
      '--bg',
      '--surface',
      '--surface-2',
      '--separator',
      '--text',
      '--text-secondary',
      '--accent',
      '--gold',
      '--up',
      '--down',
    ] as const

    const drift = names
      .map((name) => {
        const actual = declared.get(name)
        const fallback = tokenFallback(name)
        if (!actual) return `${name} 不在 tokens.css 里`
        return actual === fallback ? null : `${name}: tokens.css=${actual} 兜底=${fallback}`
      })
      .filter((line): line is string => line !== null)

    expect(drift, '令牌兜底值与 tokens.css 漂开了').toEqual([])
  })
})
