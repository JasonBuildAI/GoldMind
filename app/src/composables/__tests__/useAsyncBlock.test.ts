import { describe, expect, it } from 'vitest'

import { useAsyncBlock } from '../useAsyncBlock'

/** 手动控制 resolve 时刻的 Promise。 */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useAsyncBlock 并发加载', () => {
  it('先发后到的旧响应不得覆盖新响应', async () => {
    // 回归：区块里同时存在「首屏加载」与用户的「重新分析」，
    // 两个请求在飞。旧实现谁最后回来谁写 data，慢的那个（旧请求）
    // 会把新结果显示成旧的 —— 页面看起来「点了没反应」。
    const first = deferred<string>()
    const second = deferred<string>()
    const pending = [first, second]
    const fetcher = () => pending.shift()!.promise

    const block = useAsyncBlock<string>(fetcher, { fallback: 'x' })

    const slow = block.load()
    const fast = block.load(true)

    second.resolve('新结果')
    await fast
    first.resolve('旧结果')
    await slow

    expect(block.data.value).toBe('新结果')
  })

  it('旧请求的失败不得盖掉后发请求的成功结果', async () => {
    const first = deferred<string>()
    const second = deferred<string>()
    const pending = [first, second]
    const fetcher = () => pending.shift()!.promise

    const block = useAsyncBlock<string>(fetcher, { fallback: '获取失败。' })

    const slow = block.load()
    const fast = block.load(true)

    second.resolve('新结果')
    await fast
    first.reject(new Error('boom'))
    await slow

    expect(block.data.value).toBe('新结果')
    expect(block.error.value).toBeNull()
  })

  it('旧请求结束时不把 loading / refreshing 提前关掉', async () => {
    const first = deferred<string>()
    const second = deferred<string>()
    const pending = [first, second]
    const fetcher = () => pending.shift()!.promise

    const block = useAsyncBlock<string>(fetcher, { fallback: 'x' })

    const slow = block.load()
    const fast = block.load(true)
    expect(block.refreshing.value).toBe(true)

    first.resolve('旧结果')
    await slow

    // 新的那次还在飞，刷新态必须保持
    expect(block.refreshing.value).toBe(true)

    second.resolve('新结果')
    await fast
    expect(block.refreshing.value).toBe(false)
    expect(block.loading.value).toBe(false)
    expect(block.data.value).toBe('新结果')
  })

  it('单个请求的正常路径不变：写入数据并清掉错误', async () => {
    let calls = 0
    const block = useAsyncBlock<string>(
      async () => {
        calls += 1
        if (calls === 1) throw new Error('boom')
        return 'ok'
      },
      { fallback: '获取失败。' },
    )

    await block.load()
    expect(block.loading.value).toBe(false)
    expect(block.error.value).not.toBeNull()

    await block.load(true)
    expect(block.data.value).toBe('ok')
    expect(block.error.value).toBeNull()
    expect(block.refreshing.value).toBe(false)
  })
})

describe('useAsyncBlock 初始状态', () => {
  it('首个请求还没回来时是 loading', () => {
    const block = useAsyncBlock<string>(async () => 'x', { fallback: 'x' })
    expect(block.loading.value).toBe(true)
    expect(block.data.value).toBeNull()
  })
})
