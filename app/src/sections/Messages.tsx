import { useCallback, useEffect, useState } from 'react'

import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import StateBlock from '@/components/StateBlock'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { describeApiError } from '@/lib/apiError'
import { displayStamp, formatNumber } from '@/lib/format'
import {
  newsDigestApi,
  type DigestItem,
  type DigestRefreshResponse,
  type DigestResponse,
} from '@/services/api'

/**
 * 消息：高权威来源的黄金相关消息，按重要性与置信度排序。
 *
 * 三件不能妥协的事：
 * 1. 分数与排序全部来自后端确定性评分（来源权威 + 黄金相关 + 同题覆盖 + 时效），
 *    前端不重排、不补算；三个窗口允许重叠（同一事件出现在多个窗口是设计行为）。
 * 2. 抓不到就显示「不可用 + 原因」，不摆任何内置消息文案。
 * 3. 原文链接一律新窗口打开，展开区给出摘要、评分依据与同题报道。
 */

function DigestRow({ item }: { item: DigestItem }) {
  const published = displayStamp(item.published_at)

  return (
    <li className="digest__item" data-testid={`message-${item.id}`}>
      <div className="digest__head">
        <span className="digest__rank num">{item.rank}</span>
        <h3 className="digest__title">{item.title}</h3>
      </div>

      <p className="digest__meta">
        <span>{item.source}</span>
        <span>{item.tier_label}</span>
        {published ? <span>发布 {published}</span> : null}
        <span>重要性 {formatNumber(item.importance, 1)}</span>
        <span>置信度 {formatNumber(item.confidence, 1)}</span>
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer noopener"
          aria-label={`原文：${item.title}（新窗口打开）`}
        >
          原文 ↗
        </a>
      </p>

      <details className="digest__details">
        <summary>展开详情</summary>
        <div className="digest__body">
          {item.summary ? (
            <p data-testid={`message-summary-${item.id}`}>{item.summary}</p>
          ) : (
            <p className="note">这条消息没有摘要，只保留标题与原文链接。</p>
          )}

          {item.signals.length > 0 ? (
            <div className="digest__block">
              <h4>评分依据</h4>
              <ul data-testid={`message-signals-${item.id}`}>
                {item.signals.map((signal) => (
                  <li key={signal}>{signal}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {item.related.length > 0 ? (
            <div className="digest__block">
              <h4>同题报道</h4>
              <ul data-testid={`message-related-${item.id}`}>
                {item.related.map((related) => {
                  const stamp = displayStamp(related.published_at)
                  return (
                    <li key={related.url}>
                      <a href={related.url} target="_blank" rel="noreferrer noopener">
                        {related.title}
                      </a>
                      <span className="digest__related-meta">
                        {' '}
                        — {related.source}
                        {stamp ? ` · ${stamp}` : ''}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          ) : null}
        </div>
      </details>
    </li>
  )
}

function reportLine(report: DigestRefreshResponse): string {
  const bits = [
    `本次抓取：${report.ok_sources}/${report.total_sources} 个来源成功`,
    `新增 ${report.new_items} 条`,
  ]
  if (report.duplicates > 0) bits.push(`重复 ${report.duplicates} 条`)
  if (report.skipped_filtered > 0) bits.push(`不相关跳过 ${report.skipped_filtered} 条`)
  if (report.skipped_unstorable > 0) bits.push(`落库失败跳过 ${report.skipped_unstorable} 条`)
  if (report.failed_sources > 0) bits.push(`失败 ${report.failed_sources} 个来源`)
  return bits.join(' · ')
}

export default function Messages() {
  const [data, setData] = useState<DigestResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<DigestRefreshResponse | null>(null)
  const [activeWindow, setActiveWindow] = useState('24h')

  const fetchDigest = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await newsDigestApi.getDigest())
    } catch (err) {
      setError(describeApiError(err, { fallback: '获取消息失败。' }))
      // 不填充任何内置消息：保持为空，由空状态如实说明。
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchDigest()
  }, [fetchDigest])

  const crawl = useCallback(async () => {
    setRefreshing(true)
    setError(null)
    setReport(null)
    try {
      const result = await newsDigestApi.refresh()
      setReport(result)
      setData(await newsDigestApi.getDigest())
    } catch (err) {
      setError(
        describeApiError(err, {
          fallback: '抓取最新消息失败。',
          timeout: '抓取耗时较长，请稍后重试。',
        }),
      )
    } finally {
      setRefreshing(false)
    }
  }, [])

  const lastFetch = data?.last_fetch ?? null
  const stamp = displayStamp(lastFetch?.fetched_at)

  const refreshButton = (
    <RefreshButton
      onClick={() => void crawl()}
      busy={refreshing}
      label="抓取最新消息"
      busyLabel="抓取中…"
    />
  )

  let body

  if (loading && !data) {
    body = <StateBlock title="正在读取消息…" testId="messages-loading" />
  } else if (!data?.has_data) {
    body = (
      <StateBlock
        kind="unavailable"
        testId="messages-unavailable"
        title="消息暂不可用"
        detail={
          error ??
          data?.unavailable_reason ??
          '没能取到任何真实消息。这里不显示内置内容 —— 编造消息比留空更糟。'
        }
        actions={refreshButton}
      />
    )
  } else {
    body = (
      <div className="panel">
        <p className="panel__meta">
          {stamp ? <span>上次抓取 {stamp}</span> : null}
          <span>来源：央行 / 通讯社 / 行业机构 / 专业财经媒体</span>
          {error ? <span className="panel__error">刷新失败：{error}</span> : null}
        </p>

        {report ? (
          <p className="note" data-testid="messages-report">
            {reportLine(report)}
          </p>
        ) : null}

        <Tabs value={activeWindow} onValueChange={setActiveWindow}>
          <TabsList aria-label="消息时间范围">
            {data.windows.map((window) => (
              <TabsTrigger key={window.key} value={window.key}>
                {window.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {data.windows.map((window) => (
            <TabsContent key={window.key} value={window.key}>
              {window.items.length === 0 ? (
                <p className="note" data-testid={`messages-empty-${window.key}`}>
                  {window.label}内没有符合条件的消息。
                </p>
              ) : (
                <>
                  <p className="panel__meta">
                    <span>共 {window.total_clusters} 组同题报道</span>
                    <span>展示前 {window.items.length} 条，按重要性排序</span>
                  </p>
                  <ol className="digest" data-testid={`messages-${window.key}`}>
                    {window.items.map((item) => (
                      <DigestRow key={item.id} item={item} />
                    ))}
                  </ol>
                </>
              )}
            </TabsContent>
          ))}
        </Tabs>
      </div>
    )
  }

  return (
    <Section
      id="messages"
      title="消息"
      intro="高权威来源（央行 / 通讯社 / 行业机构 / 专业财经媒体）的黄金相关消息，按重要性与置信度排序；24 小时 / 7 天 / 30 天三个窗口各取前 10 条，同一事件可以同时出现在多个窗口。评分由来源权威、黄金相关度、同题覆盖与时效确定性算出，不经过模型生成。"
      actions={refreshButton}
    >
      {body}
    </Section>
  )
}
