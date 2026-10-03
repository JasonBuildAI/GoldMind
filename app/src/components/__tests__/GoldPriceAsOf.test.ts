import { afterEach, describe, expect, it } from 'vitest'

import { byTestId, createBlockHarness } from '@/test/harness'

import GoldPriceAsOf from '../GoldPriceAsOf.vue'

/**
 * 「金价刷新时间」这句话的唯一写法。
 *
 * 这一层守住的是**诚实性**，不是排版：
 * 1. 时间只来自传进来的 as-of 字段 —— 组件不许自己取当前时间（那会造出一个
 *    看起来像「刚刚」、实际没有任何依据的时间）；
 * 2. as-of 缺失时如实写「时间未知（后端未返回）」，不留空白、不写「刚刚」；
 * 3. 口径与来源有就一起给（没有口径的价格无法与页面其它数字对照）。
 */
const harness = createBlockHarness()

afterEach(() => {
  harness.cleanup()
})

describe('GoldPriceAsOf', () => {
  it('有 as-of 时给出时间、口径与来源', () => {
    const { root } = harness.mount(GoldPriceAsOf, {
      props: {
        asOf: '2026-10-03T12:40:00',
        basisLabel: '实时报价',
        source: '腾讯财经-纽约黄金',
        asOfField: 'stats.price_as_of',
      },
    })

    expect(root.textContent).toContain('金价刷新')
    expect(root.textContent).toContain('2026-10-03 12:40')
    expect(root.textContent).toContain('实时报价')
    expect(root.textContent).toContain('腾讯财经-纽约黄金')
    // 字段级选择器挂在时间那一格上（字段覆盖守卫按它盘点）
    expect(byTestId(root, 'field-stats.price_as_of')?.textContent).toContain('2026-10-03 12:40')
  })

  it('as-of 缺失时如实写「时间未知」，不拿当前时间顶替', () => {
    const { root } = harness.mount(GoldPriceAsOf, {
      props: { asOf: null, asOfField: 'summary.price_as_of' },
    })

    const slot = byTestId(root, 'field-summary.price_as_of')!
    expect(slot.textContent).toContain('时间未知')
    expect(slot.textContent).toContain('后端未返回')
    // 不许出现今天的日期 —— 那是浏览器时钟算出来的，不是数据自带的时间
    const today = new Date().toISOString().slice(0, 10)
    expect(root.textContent).not.toContain(today)
  })

  it('只给时间、没有口径与来源时不留下多余的分隔符', () => {
    const { root } = harness.mount(GoldPriceAsOf, {
      props: { asOf: '2026-10-03T12:40:00' },
    })

    expect(root.textContent).toContain('2026-10-03 12:40')
    expect(root.textContent).not.toContain('·')
  })

  it('前缀用于点名是哪个价格（基准价 / 快照价 / 当前价格）', () => {
    const { root } = harness.mount(GoldPriceAsOf, {
      props: { asOf: '2026-09-30', label: '基准价' },
    })

    expect(root.textContent).toContain('基准价 金价刷新 2026-09-30')
  })

  it('日期型 as-of（只有年月日）原样展示，不补一个假时分', () => {
    const { root } = harness.mount(GoldPriceAsOf, {
      props: { asOf: '2026-10-01', basisLabel: '日收盘' },
    })

    expect(root.textContent).toContain('2026-10-01')
    expect(root.textContent).not.toContain('00:00')
  })
})
