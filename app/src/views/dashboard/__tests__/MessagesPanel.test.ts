import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { buttonByText, byTestId, createBlockHarness, hasText } from '@/test/harness'
import { newsDigestApi, type DigestItem, type DigestResponse } from '@/services/api'

import MessagesPanel from '../MessagesPanel.vue'

/**
 * 消息板块：三窗口切换、逐条元信息、展开详情、手动抓取与三态。
 *
 * 两条不能妥协的：分数与排序全部来自后端确定性评分（前端不重排、不补算）；
 * 抓不到就显示「不可用 + 原因」，不摆任何内置消息。
 */
vi.mock('@/services/api', () => ({
  newsDigestApi: { getDigest: vi.fn(), refresh: vi.fn() },
}))

const mocked = vi.mocked(newsDigestApi, true)

function item(overrides: Partial<DigestItem> = {}): DigestItem {
  return {
    rank: 1,
    id: 1,
    title: 'Gold hits a record high',
    summary: 'Central bank buying keeps pushing gold higher.',
    // 中文译文与英文原文并存
    title_zh: '金价创下新高',
    brief_zh: '央行持续购金推动金价走高。',
    translated: true,
    translation_model: 'test-model',
    translated_at: '2026-10-02T10:35:00',
    source: '路透社',
    tier: 1,
    tier_label: '一级信源',
    url: 'https://example.invalid/digest/1',
    published_at: '2026-10-02T10:30:00',
    age_hours: 1.5,
    importance: 92.4,
    confidence: 88.1,
    signals: ['一级信源：官方 / 通讯社 / 行业机构', '24 小时内发布'],
    event_tags: [],
    event_labels: [],
    via_aggregator: false,
    coverage_count: 1,
    related: [],
    ...overrides,
  }
}

const FETCH_REPORT = {
  fetched_at: '2026-10-02 11:25:00',
  total_sources: 13,
  ok_sources: 12,
  failed_sources: 1,
  entries: 40,
  kept: 12,
  new_items: 3,
  duplicates: 9,
  skipped_no_title: 0,
  skipped_no_url: 0,
  skipped_no_time: 1,
  skipped_filtered: 15,
  skipped_unstorable: 0,
  translated: 2,
  translation_reason: null,
  sources: [],
}

const ITEM_24H = item({
  id: 1,
  rank: 1,
  title_zh: '金价创下新高',
  translated: true,
  signals: ['一级信源：官方 / 通讯社 / 行业机构', '2 家来源同题报道'],
  coverage_count: 2,
  related: [
    {
      title: '同题报道：金价创下新高',
      source: '美联社',
      url: 'https://example.invalid/digest/ap',
      published_at: '2026-10-02T09:00:00',
    },
  ],
})

/** 只在 7 天窗口出现、且**还没有中文**的一条：未翻译时的降级显示靠它覆盖。 */
const ITEM_7D_ONLY = item({
  id: 2,
  rank: 2,
  title: 'Gold steadies ahead of the payrolls report',
  title_zh: null,
  brief_zh: null,
  translated: false,
  translation_model: null,
  translated_at: null,
  published_at: '2026-10-01T02:00:00',
})

const DIGEST: DigestResponse = {
  generated_at: '2026-10-02 12:00:00',
  has_data: true,
  unavailable_reason: null,
  last_fetch: FETCH_REPORT,
  translation: {
    enabled: true,
    model: 'test-model',
    pending: 1,
    reason: 'LLM 未配置：中文标题与导语暂不可用',
  },
  windows: [
    { key: '24h', label: '24 小时内', hours: 24, total_clusters: 1, items: [ITEM_24H] },
    { key: '7d', label: '7 天内', hours: 168, total_clusters: 2, items: [ITEM_24H, ITEM_7D_ONLY] },
    { key: '30d', label: '30 天内', hours: 720, total_clusters: 2, items: [ITEM_24H, ITEM_7D_ONLY] },
  ],
}

const harness = createBlockHarness()

/** 挂载并等到终态：窗口列表或「不可用」。 */
async function renderMessages() {
  const mounted = harness.mount(MessagesPanel)
  await vi.waitFor(() => {
    expect(
      mounted.root.querySelector(
        '[data-testid="messages-windows"], [data-testid="messages-unavailable"]',
      ),
    ).not.toBeNull()
  })
  return mounted
}

/** 切到某个窗口（按 tab 的可访问名点击）。 */
function clickTab(root: HTMLElement, label: string): void {
  const tab = [...root.querySelectorAll('[role="tab"]')].find((node) =>
    (node.textContent ?? '').includes(label),
  )
  expect(tab, `没有「${label}」这个窗口标签`).toBeTruthy()
  ;(tab as HTMLElement).click()
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  harness.cleanup()
})

describe('Messages', () => {
  it('三个窗口标签来自接口，默认展示 24 小时内的条目', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    const { root } = await renderMessages()

    expect(byTestId(root, 'messages-24h')).not.toBeNull()
    for (const label of ['24 小时内', '7 天内', '30 天内']) {
      expect(
        [...root.querySelectorAll('[role="tab"]')].some((node) =>
          (node.textContent ?? '').includes(label),
        ),
        `缺少窗口标签 ${label}`,
      ).toBe(true)
    }
    expect(hasText(root, '金价创下新高')).toBe(true)
    expect(hasText(root, 'Gold steadies ahead of the payrolls report')).toBe(false)
  })

  it('切换窗口后显示该窗口独有的条目', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    const { root } = await renderMessages()
    clickTab(root, '7 天内')

    await vi.waitFor(() => {
      expect(hasText(root, 'Gold steadies ahead of the payrolls report')).toBe(true)
    })
  })

  it('有中文译文时：中文标题为主，英文原题仍在，导语与 AI 标注在折叠态可见', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    const { root } = await renderMessages()

    const row = byTestId(root, 'message-1')!
    // 中文标题是标题本身
    expect(byTestId(root, 'field-digest.items.title_zh')?.textContent).toContain('金价创下新高')
    // 英文原题**始终可见**（叠加不是替换）：否则读者无法把译文对回原文
    expect(byTestId(root, 'field-digest.items.title')?.textContent).toContain(
      'Gold hits a record high',
    )
    expect(row.querySelector('[data-testid="field-digest.items.title"]')).not.toBeNull()
    // 导语：不必展开就能读到「这条讲了什么」
    expect(byTestId(root, 'field-digest.items.brief_zh')?.textContent).toContain(
      '央行持续购金推动金价走高',
    )
    // AI 产出必须带标注
    expect(byTestId(root, 'field-digest.items.translated')?.textContent).toContain('AI 译')
  })

  it('没有中文译文时：英文标题就是标题，并说明为什么没有中文', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    const { root } = await renderMessages()
    clickTab(root, '7 天内')

    await vi.waitFor(() => {
      expect(byTestId(root, 'message-2')).not.toBeNull()
    })
    const row = byTestId(root, 'message-2')!
    expect(row.textContent).toContain('Gold steadies ahead of the payrolls report')
    // 原因来自后端（translation.reason），不是前端编的一句话
    expect(row.textContent).toContain('中文翻译暂不可用')
    expect(row.textContent).toContain('LLM 未配置')
    // 不许出现任何凭空的中文标题/导语
    expect(byTestId(row, 'field-digest.items.title_zh')).toBeNull()
    expect(byTestId(row, 'field-digest.items.brief_zh')).toBeNull()
  })

  it('翻译状态一行如实展示开关、模型、待翻译条数与原因', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    const { root } = await renderMessages()

    expect(byTestId(root, 'field-digest.translation.enabled')?.textContent).toContain('已开启')
    expect(byTestId(root, 'field-digest.translation.model')?.textContent).toContain('test-model')
    expect(byTestId(root, 'field-digest.translation.pending')?.textContent).toContain('待翻译 1 条')
    expect(byTestId(root, 'field-digest.translation.reason')?.textContent).toContain('LLM 未配置')
  })

  it('展开后英文原文与「中文是谁生成的」都在，读者可以逐条核对', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    const { root } = await renderMessages()

    const details = byTestId(root, 'message-1')!.querySelector('details')!
    details.setAttribute('open', '')

    expect(byTestId(root, 'field-digest.items.title')?.textContent).toContain('Gold hits')
    expect(byTestId(root, 'field-digest.items.summary')?.textContent).toContain(
      'Central bank buying keeps pushing gold higher',
    )
    const note = byTestId(root, 'message-translation-1')!
    expect(note.textContent).toContain('test-model')
    expect(note.textContent).toContain('2026-10-02 10:35')
    expect(note.textContent).toContain('只压缩原文已有的事实')
  })

  it('每条给出序号、来源、时间、重要性与置信度，原文链接新窗口打开', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    const { root } = await renderMessages()

    const row = byTestId(root, 'message-1')!
    expect(row.textContent).toContain('1')
    expect(row.textContent).toContain('路透社')
    expect(row.textContent).toContain('发布 2026-10-02 10:30')
    expect(row.textContent).toContain('重要性 92.4')
    expect(row.textContent).toContain('置信度 88.1')

    const link = row.querySelector<HTMLAnchorElement>('a[href="https://example.invalid/digest/1"]')!
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
    // 可访问名用**英文原题**：读屏用户听到的就是来源给的那个标题
    expect(link.getAttribute('aria-label')).toContain('原文：Gold hits a record high')
  })

  it('展开详情后能看到摘要、评分依据与同题报道链接', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    const { root } = await renderMessages()

    const details = byTestId(root, 'message-1')!.querySelector('details')!
    details.setAttribute('open', '')
    // happy-dom 不派发 toggle，直接同步 DOM 后再断言即可
    expect(byTestId(root, 'message-summary-1')?.textContent).toContain(
      'Central bank buying keeps pushing gold higher',
    )
    const signals = byTestId(root, 'message-signals-1')!
    expect(signals.textContent).toContain('2 家来源同题报道')
    const related = byTestId(root, 'message-related-1')!
    const relatedLink = related.querySelector<HTMLAnchorElement>('a')!
    expect(relatedLink.textContent).toContain('同题报道：金价创下新高')
    expect(relatedLink.getAttribute('target')).toBe('_blank')
    expect(related.textContent).toContain('美联社')
  })

  it('点击「抓取最新消息」先抓取再重读，并显示本次抓取报告', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)
    mocked.refresh.mockResolvedValue({ success: true, ...FETCH_REPORT, skipped_unstorable: 2 })

    const { root } = await renderMessages()
    buttonByText(root, '抓取最新消息')?.click()

    await vi.waitFor(() => {
      expect(byTestId(root, 'messages-report')).not.toBeNull()
    })
    expect(mocked.refresh).toHaveBeenCalledTimes(1)
    expect(mocked.getDigest).toHaveBeenCalledTimes(2)
    const report = byTestId(root, 'messages-report')!
    expect(report.textContent).toContain('本次抓取：12/13 个来源成功')
    expect(report.textContent).toContain('新增 3 条')
    expect(report.textContent).toContain('落库失败跳过 2 条')
    expect(report.textContent).toContain('失败 1 个来源')
  })

  it('抓取进行中按钮显示「抓取中…」并禁用', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)
    let resolveRefresh: (value: unknown) => void = () => {}
    mocked.refresh.mockImplementation(
      () => new Promise((resolve) => (resolveRefresh = resolve)) as never,
    )

    const { root } = await renderMessages()
    buttonByText(root, '抓取最新消息')?.click()

    await vi.waitFor(() => {
      expect(buttonByText(root, '抓取中…')).toBeTruthy()
    })
    expect(buttonByText(root, '抓取中…')?.disabled).toBe(true)

    resolveRefresh({ success: true, ...FETCH_REPORT })
    await vi.waitFor(() => {
      expect(buttonByText(root, '抓取最新消息')?.disabled).toBe(false)
    })
  })

  it('抓取失败时保留已有消息，并说明失败原因', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)
    mocked.refresh.mockRejectedValue(new Error('boom'))

    const { root } = await renderMessages()
    buttonByText(root, '抓取最新消息')?.click()

    await vi.waitFor(() => {
      expect(hasText(root, /刷新失败：/)).toBe(true)
    })
    expect(hasText(root, '金价创下新高')).toBe(true)
  })

  it('空库时只显示不可用原因，不出现任何消息条目', async () => {
    mocked.getDigest.mockResolvedValue({
      ...DIGEST,
      has_data: false,
      last_fetch: null,
      unavailable_reason: '尚未抓取过消息。点击「抓取最新消息」从高权威来源拉取。',
      windows: [
        { key: '24h', label: '24 小时内', hours: 24, total_clusters: 0, items: [] },
        { key: '7d', label: '7 天内', hours: 168, total_clusters: 0, items: [] },
        { key: '30d', label: '30 天内', hours: 720, total_clusters: 0, items: [] },
      ],
    })

    const { root } = await renderMessages()

    expect(byTestId(root, 'messages-unavailable')).not.toBeNull()
    expect(hasText(root, /尚未抓取过消息/)).toBe(true)
    expect(byTestId(root, 'messages-24h')).toBeNull()
    expect(hasText(root, '金价创下新高')).toBe(false)
  })

  it('接口失败时如实说「暂不可用」，不摆任何内置消息', async () => {
    mocked.getDigest.mockRejectedValue(new Error('boom'))

    const { root } = await renderMessages()

    expect(byTestId(root, 'messages-unavailable')).not.toBeNull()
    expect(hasText(root, '消息暂不可用')).toBe(true)
    expect(hasText(root, /无法连接后端/)).toBe(true)
    expect(byTestId(root, 'messages-24h')).toBeNull()
  })

  it('上次抓取报告收在一层折叠里，展开可见逐源明细', async () => {
    mocked.getDigest.mockResolvedValue({
      ...DIGEST,
      last_fetch: {
        ...FETCH_REPORT,
        sources: [
          { name: 'reuters', status: 'ok', entries: 20, kept: 10, new: 3, error: null },
          { name: 'cftc', status: 'error', entries: 0, kept: 0, new: 0, error: '连接超时' },
        ],
      },
    })

    const { root } = await renderMessages()

    const lastFetch = byTestId(root, 'field-digest.last_fetch')!
    expect(lastFetch.tagName).toBe('DETAILS')
    expect(lastFetch.querySelector('summary')?.textContent).toContain('上次抓取报告')
    expect(lastFetch.textContent).toContain('reuters')
    expect(lastFetch.textContent).toContain('连接超时')
    // 折叠不嵌套
    expect(lastFetch.querySelectorAll('details').length).toBe(0)
  })
})
