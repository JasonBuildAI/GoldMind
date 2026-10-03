import { readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/**
 * 设计令牌守卫：组件里不许写死颜色。
 *
 * 为什么这是一条测试：令牌的唯一真源是 `styles/tokens.css`，但「只准引用变量」
 * 这条规矩在代码评审里很容易被放过 —— 一个 `#fff` 在深色底、打印样式或
 * 对比度调整时不会跟着变，而问题只在某一种环境下显形。
 *
 * 例外（都在下面逐个列明）：
 *   - `styles/tokens.css` 本身：令牌定义处；
 *   - `lib/tokens.ts`：SVG 的 stroke / fill 不认 CSS 变量，必须有一份运行时兜底；
 *   - `styles/base.css`：只允许在 `:focus-visible` 的焦点环里用带透明度的
 *     强调色（`box-shadow` 无法直接吃 `color-mix`，见该处注释）。
 */
const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '../..')

/** 十六进制颜色：`#fff` / `#ffffff` / `#ffffffcc`。 */
const HEX = /#[0-9a-fA-F]{3,8}\b/g

const ALLOWED = new Set([
  path.join(SRC, 'styles', 'tokens.css'),
  path.join(SRC, 'lib', 'tokens.ts'),
  path.join(SRC, 'styles', 'base.css'),
])

async function walk(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true })
  const files: string[] = []
  for (const entry of entries) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') continue
      files.push(...(await walk(full)))
    } else if (/\.(vue|css|ts)$/.test(entry.name)) {
      files.push(full)
    }
  }
  return files
}

describe('设计令牌守卫', () => {
  it('组件与样式里不出现写死的十六进制颜色', async () => {
    const files = await walk(SRC)
    expect(files.length, '没扫到任何文件，守卫形同虚设').toBeGreaterThan(20)

    const offenders: string[] = []
    for (const file of files) {
      if (ALLOWED.has(file)) continue
      const text = await readFile(file, 'utf8')
      for (const match of text.matchAll(HEX)) {
        const line = text.slice(0, match.index).split('\n').length
        offenders.push(`${path.relative(SRC, file)}:${line} ${match[0]}`)
      }
    }

    expect(
      offenders,
      '组件里写死了颜色。请改用 tokens.css 里的变量（新增令牌时同步改 docs/20-前端设计规范.md）',
    ).toEqual([])
  })

  it('令牌文件本身真的定义了那些变量（守卫不是空转）', async () => {
    const css = await readFile(path.join(SRC, 'styles', 'tokens.css'), 'utf8')
    const rootBlock = css.match(/:root\s*\{([\s\S]*?)\n\}/)?.[1] ?? ''
    const declared = new Set(
      [...rootBlock.matchAll(/(--[a-z0-9-]+):/gim)].map((match) => match[1]),
    )

    // 抽查几个被组件广泛引用的令牌
    for (const name of ['--surface', '--separator', '--text', '--gold', '--up', '--down']) {
      expect(declared.has(name), `tokens.css 没有定义 ${name}`).toBe(true)
    }
  })

  it('组件只引用令牌，不出现裸的颜色关键字（如 white / black）', async () => {
    const files = await walk(SRC)
    const offenders: string[] = []
    for (const file of files) {
      if (ALLOWED.has(file)) continue
      if (!file.endsWith('.vue') && !file.endsWith('.css')) continue
      const text = await readFile(file, 'utf8')
      // 只查样式块里「属性: white」这类写法；文案里出现「白」不算
      for (const match of text.matchAll(/:\s*(white|black)\s*[;}]/g)) {
        const line = text.slice(0, match.index).split('\n').length
        offenders.push(`${path.relative(SRC, file)}:${line}`)
      }
    }
    expect(offenders, '样式里用了 white / black 关键字，请改用 --surface / --text').toEqual([])
  })
})
