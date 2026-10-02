import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Messages from './Messages'
import { newsDigestApi, type DigestItem } from '../services/api'

vi.mock('../services/api', () => ({
  newsDigestApi: {
    getDigest: vi.fn(),
    refresh: vi.fn(),
  },
}))

const mocked = vi.mocked(newsDigestApi, true)

function item(overrides: Partial<DigestItem> = {}): DigestItem {
  return {
    rank: 1,
    id: 1,
    title: '接口返回的消息一',
    summary: '接口返回的摘要一',
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
  sources: [],
}

const ITEM_24H = item({
  id: 1,
  rank: 1,
  title: '金价创下新高',
  summary: '央行持续购金推动金价走高。',
  signals: ['一级信源：官方 / 通讯社 / 行业机构', '2 家来源同题报道'],
  coverage_count: 2,
  related: [
    {
      title: '金价创下新高（同题）',
      source: '美联社',
      url: 'https://example.invalid/digest/ap',
      published_at: '2026-10-02T09:00:00',
    },
  ],
})

const ITEM_7D_ONLY = item({
  id: 2,
  rank: 2,
  title: '只在 7 天窗口出现的消息',
  published_at: '2026-10-01T02:00:00',
})

const DIGEST = {
  generated_at: '2026-10-02 12:00:00',
  has_data: true,
  unavailable_reason: null,
  last_fetch: FETCH_REPORT,
  windows: [
    { key: '24h', label: '24 小时内', hours: 24, total_clusters: 1, items: [ITEM_24H] },
    {
      key: '7d',
      label: '7 天内',
      hours: 168,
      total_clusters: 2,
      items: [ITEM_24H, ITEM_7D_ONLY],
    },
    {
      key: '30d',
      label: '30 天内',
      hours: 720,
      total_clusters: 2,
      items: [ITEM_24H, ITEM_7D_ONLY],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Messages', () => {
  it('三个窗口标签来自接口，默认展示 24 小时内的条目', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    render(<Messages />)

    expect(await screen.findByTestId('messages-24h')).toBeInTheDocument()
    for (const label of ['24 小时内', '7 天内', '30 天内']) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument()
    }
    expect(screen.getByText('金价创下新高')).toBeInTheDocument()
    expect(screen.queryByText('只在 7 天窗口出现的消息')).not.toBeInTheDocument()
  })

  it('切换窗口后显示该窗口独有的条目', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)
    const user = userEvent.setup()

    render(<Messages />)
    await screen.findByTestId('messages-24h')

    await user.click(screen.getByRole('tab', { name: '7 天内' }))

    expect(await screen.findByText('只在 7 天窗口出现的消息')).toBeInTheDocument()
  })

  it('每条给出序号、来源、时间、重要性与置信度，原文链接新窗口打开', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)

    render(<Messages />)

    const row = within(await screen.findByTestId('message-1'))
    expect(row.getByText('1')).toBeInTheDocument()
    expect(row.getByText('路透社')).toBeInTheDocument()
    expect(row.getByText('发布 2026-10-02 10:30')).toBeInTheDocument()
    expect(row.getByText('重要性 92.4')).toBeInTheDocument()
    expect(row.getByText('置信度 88.1')).toBeInTheDocument()

    const link = row.getByRole('link', { name: /原文：金价创下新高/ })
    expect(link).toHaveAttribute('href', 'https://example.invalid/digest/1')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
  })

  it('展开详情后能看到摘要、评分依据与同题报道链接', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)
    const user = userEvent.setup()

    render(<Messages />)
    await screen.findByTestId('message-1')

    await user.click(screen.getByText('展开详情'))

    expect(screen.getByTestId('message-summary-1')).toHaveTextContent('央行持续购金推动金价走高')
    const signals = within(screen.getByTestId('message-signals-1'))
    expect(signals.getByText('2 家来源同题报道')).toBeInTheDocument()
    const related = within(screen.getByTestId('message-related-1'))
    const relatedLink = related.getByRole('link', { name: '金价创下新高（同题）' })
    expect(relatedLink).toHaveAttribute('target', '_blank')
    expect(related.getByText(/美联社/)).toBeInTheDocument()
  })

  it('点击「抓取最新消息」先抓取再重读，并显示本次抓取报告', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)
    mocked.refresh.mockResolvedValue({ success: true, ...FETCH_REPORT, skipped_unstorable: 2 })
    const user = userEvent.setup()

    render(<Messages />)

    const button = await screen.findByRole('button', { name: '抓取最新消息' })
    await user.click(button)

    expect(mocked.refresh).toHaveBeenCalledTimes(1)
    expect(mocked.getDigest).toHaveBeenCalledTimes(2)
    const report = await screen.findByTestId('messages-report')
    expect(report).toHaveTextContent('本次抓取：12/13 个来源成功')
    expect(report).toHaveTextContent('新增 3 条')
    expect(report).toHaveTextContent('落库失败跳过 2 条')
    expect(report).toHaveTextContent('失败 1 个来源')
  })

  it('抓取进行中按钮显示「抓取中…」并禁用', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)
    let resolveRefresh: (value: unknown) => void = () => {}
    mocked.refresh.mockImplementation(
      () => new Promise((resolve) => (resolveRefresh = resolve)) as never,
    )
    const user = userEvent.setup()

    render(<Messages />)
    await user.click(await screen.findByRole('button', { name: '抓取最新消息' }))

    const busy = screen.getAllByRole('button', { name: '抓取中…' })[0]
    expect(busy).toBeDisabled()

    resolveRefresh({ success: true, ...FETCH_REPORT })
    await screen.findByRole('button', { name: '抓取最新消息' })
  })

  it('抓取失败时保留已有消息，并说明失败原因', async () => {
    mocked.getDigest.mockResolvedValue(DIGEST)
    mocked.refresh.mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()

    render(<Messages />)
    await user.click(await screen.findByRole('button', { name: '抓取最新消息' }))

    expect(await screen.findByText(/刷新失败：/)).toBeInTheDocument()
    expect(screen.getByText('金价创下新高')).toBeInTheDocument()
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

    render(<Messages />)

    expect(await screen.findByTestId('messages-unavailable')).toBeInTheDocument()
    expect(screen.getByText(/尚未抓取过消息/)).toBeInTheDocument()
    expect(screen.queryByTestId('messages-24h')).not.toBeInTheDocument()
    expect(screen.queryByText('金价创下新高')).not.toBeInTheDocument()
  })

  it('接口失败时如实说「暂不可用」，不摆任何内置消息', async () => {
    mocked.getDigest.mockRejectedValue(new Error('boom'))

    render(<Messages />)

    expect(await screen.findByTestId('messages-unavailable')).toBeInTheDocument()
    expect(screen.getByText('消息暂不可用')).toBeInTheDocument()
    expect(screen.getByText(/无法连接后端/)).toBeInTheDocument()
    expect(screen.queryByTestId('messages-24h')).not.toBeInTheDocument()
  })
})
