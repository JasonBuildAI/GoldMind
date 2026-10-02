import { useCallback, useEffect, useState } from 'react'

import RefreshButton from '@/components/RefreshButton'
import StateBlock from '@/components/StateBlock'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useFreshnessBlock } from '@/contexts/FreshnessContext'
import { describeApiError } from '@/lib/apiError'
import { displayStamp, formatNumber } from '@/lib/format'
import {
  newsDigestApi,
  type DigestItem,
  type DigestRefreshResponse,
  type DigestResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

/**
 * 消息：高权威来源的黄金相关消息，按重要性与置信度排序。
 *
 * 三件不能妥协的事：
 * 1. 分数与排序全部来自后端确定性评分（来源权威 + 黄金相关 + 同题覆盖 + 时效），
 *    前端不重排、不补算；三个窗口允许重叠（同一事件出现在多个窗口是设计行为）。
 * 2. 抓不到就显示「不可用 + 原因」，不摆任何内置消息。
 * 3. 原文链接一律新窗口打开，展开区给出摘要、评分依据、事件标注与同题报道。
 */

function field(path: string) {
  return fieldTestId(path)
}

function DigestRow({ item }: { item: DigestItem }) {
  const published = displayStamp(item.published_at)

  return (
    <li className="digest__item" data-testid={`message-${item.id}`}>
      <div className="digest__head">
        <span className="digest__rank num" data-testid={field('digest.items.rank')}>
          {item.rank}
        </span>
        <h3 className="digest__title" data-testid={field('digest.items.title')}>
          {item.title}
        </h3>
      </div>

      <p className="digest__meta">
        <span data-testid={field('digest.items.source')}>{item.source}</span>
        <span data-testid={field('digest.items.tier_label')}>{item.tier_label}</span>
        <span data-testid={field('digest.items.tier')}>
          {item.tier_label}（T{item.tier}）
        </span>
        {published ? (
          <span data-testid={field('digest.items.published_at')}>发布 {published}</span>
        ) : null}
        <span data-testid={field('digest.items.age_hours')}>
          {formatNumber(item.age_hours, 1)} 小时前
        </span>
        <span data-testid={field('digest.items.importance')}>
          重要性 {formatNumber(item.importance, 1)}
        </span>
        <span data-testid={field('digest.items.confidence')}>
          置信度 {formatNumber(item.confidence, 1)}
        </span>
        {item.event_labels.length > 0 ? (
          <span data-testid={field('digest.items.event_labels')}>
            事件 {item.event_labels.join(' / ')}
          </span>
        ) : null}
        {item.via_aggregator ? (
          <span data-testid={field('digest.items.via_aggregator')}>经聚合入口</span>
        ) : null}
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer noopener"
          aria-label={`原文：${item.title}（新窗口打开）`}
          data-testid={field('digest.items.url')}
        >
          原文 ↗
        </a>
      </p>

      <details className="digest__details">
        <summary>展开详情</summary>
        <div className="digest__body">
          {item.summary ? (
            <p data-testid={`message-summary-${item.id}`}>
              <span data-testid={field('digest.items.summary')}>{item.summary}</span>
            </p>
          ) : (
            <p className="note">这条消息没有摘要，只保留标题与原文链接。</p>
          )}

          <dl className="metrics">
            <div>
              <dt>编号 / 排名</dt>
              <dd className="num" data-testid={field('digest.items.id')}>
                {item.id} / {item.rank}
              </dd>
            </div>
            <div>
              <dt>同题报道数</dt>
              <dd className="num" data-testid={field('digest.items.coverage_count')}>
                {item.coverage_count}
              </dd>
            </div>
            <div>
              <dt>事件标注</dt>
              <dd data-testid={field('digest.items.event_tags')}>
                {item.event_tags.length > 0 ? item.event_tags.join('、') : '—'}
              </dd>
            </div>
          </dl>

          {item.signals.length > 0 ? (
            <div className="digest__block" data-testid={field('digest.items.signals')}>
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
              <h4>同题报道（{item.coverage_count} 家来源）</h4>
              <ul data-testid={`message-related-${item.id}`}>
                {item.related.map((related) => {
                  const stamp = displayStamp(related.published_at)
                  return (
                    <li key={related.url}>
                      <a
                        href={related.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        data-testid={field('digest.related.title')}
                      >
                        {related.title}
                      </a>
                      <span className="digest__related-meta" data-testid={field('digest.related.source')}>
                        {' '}
                        — {related.source}
                        {stamp ? <span data-testid={field('digest.related.published_at')}> · {stamp}</span> : null}
                      </span>
                      <span className="note" data-testid={field('digest.related.url')}>
                        {' '}
                        {related.url}
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

/** 抓取报告：所有计数进表格；来源明细各占一行。 */
function FetchReport({ report, testId }: { report: DigestRefreshResponse | NonNullable<DigestResponse['last_fetch']>; testId?: string }) {
  return (
    <div className="panel" data-testid={testId}>
      <h4 className="panel__title">抓取报告</h4>
      <div className="table-scroll">
        <table className="data-table">
          <tbody>
            {(
              [
                ['抓取时间', displayStamp(report.fetched_at) ?? report.fetched_at, field('digest.fetch.fetched_at')],
                ['来源总数', String(report.total_sources), field('digest.fetch.total_sources')],
                ['成功来源', String(report.ok_sources), field('digest.fetch.ok_sources')],
                ['失败来源', String(report.failed_sources), field('digest.fetch.failed_sources')],
                ['抓到条目', String(report.entries), field('digest.fetch.entries')],
                ['保留条目', String(report.kept), field('digest.fetch.kept')],
                ['新增条目', String(report.new_items), field('digest.fetch.new_items')],
                ['重复条目', String(report.duplicates), field('digest.fetch.duplicates')],
                ['无标题跳过', String(report.skipped_no_title), field('digest.fetch.skipped_no_title')],
                ['无链接跳过', String(report.skipped_no_url), field('digest.fetch.skipped_no_url')],
                ['无时间跳过', String(report.skipped_no_time), field('digest.fetch.skipped_no_time')],
                ['相关性过滤', String(report.skipped_filtered), field('digest.fetch.skipped_filtered')],
                ['落库失败跳过', String(report.skipped_unstorable), field('digest.fetch.skipped_unstorable')],
              ] as const
            ).map(([label, value, id]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td className="num" data-testid={id}>
                  {value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.sources.length > 0 ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">来源</th>
                <th scope="col">状态</th>
                <th scope="col" className="num">抓到</th>
                <th scope="col" className="num">保留</th>
                <th scope="col" className="num">新增</th>
                <th scope="col">错误</th>
              </tr>
            </thead>
            <tbody>
              {report.sources.map((source) => (
                <tr key={source.name}>
                  <th scope="row" data-testid={field('digest.fetch.sources.name')}>{source.name}</th>
                  <td data-testid={field('digest.fetch.sources.status')}>{source.status}</td>
                  <td className="num" data-testid={field('digest.fetch.sources.entries')}>{source.entries}</td>
                  <td className="num" data-testid={field('digest.fetch.sources.kept')}>{source.kept}</td>
                  <td className="num" data-testid={field('digest.fetch.sources.new')}>{source.new}</td>
                  <td className="note" data-testid={field('digest.fetch.sources.error')}>{source.error ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {'success' in report ? (
        <p className="note" data-testid={field('digest.refresh.success')}>
          本次抓取结果：{report.success ? '至少一个来源成功' : '所有来源都失败'}
        </p>
      ) : null}
    </div>
  )
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
  const hasData = Boolean(data?.has_data)
  const stamp = displayStamp(lastFetch?.fetched_at)

  useFreshnessBlock(
    'messages',
    '消息',
    hasData ? 'fresh' : loading ? 'pending' : 'unavailable',
    data?.generated_at || lastFetch?.fetched_at || null,
  )

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
  } else if (!hasData) {
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
      <div>
        <p className="panel__meta">
          <span data-testid={field('digest.has_data')}>
            {data?.has_data ? '有可用消息' : '无可用消息'}
          </span>
          {stamp ? (
            <span data-testid={field('digest.generated_at')}>生成时间 {stamp}</span>
          ) : null}
          {data?.unavailable_reason ? (
            <span className="panel__error" data-testid={field('digest.unavailable_reason')}>
              {data.unavailable_reason}
            </span>
          ) : null}
          {error ? <span className="panel__error">刷新失败：{error}</span> : null}
        </p>

        {report ? (
          <p className="note" data-testid={TESTIDS.messageReport}>
            {reportLine(report)}
            <span data-testid={field('digest.refresh.success')}>
              {' '}
              本次抓取结果：{report.success ? '至少一个来源成功' : '所有来源都失败'}
            </span>
          </p>
        ) : null}

        <div data-testid={TESTIDS.messagesWindows}>
          <Tabs value={activeWindow} onValueChange={setActiveWindow}>
            <TabsList aria-label="消息时间范围">
              {data?.windows.map((window) => (
                <TabsTrigger key={window.key} value={window.key}>
                  {window.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {data?.windows.map((window) => (
              <TabsContent key={window.key} value={window.key}>
                <p className="panel__meta">
                  <span data-testid={field('digest.windows.key')}>窗口 {window.key}</span>
                  <span data-testid={field('digest.windows.label')}>{window.label}</span>
                  <span data-testid={field('digest.windows.hours')}>{window.hours} 小时</span>
                  <span data-testid={field('digest.windows.total_clusters')}>
                    共 {window.total_clusters} 组同题报道
                  </span>
                  <span>展示前 {window.items.length} 条，按重要性排序</span>
                </p>
                {window.items.length === 0 ? (
                  <p className="note" data-testid={`messages-empty-${window.key}`}>
                    {window.label}内没有符合条件的消息。
                  </p>
                ) : (
                  <ol className="digest" data-testid={`messages-${window.key}`}>
                    {window.items.map((item) => (
                      <DigestRow key={item.id} item={item} />
                    ))}
                  </ol>
                )}
              </TabsContent>
            ))}
          </Tabs>
        </div>

        {lastFetch ? (
          <details className="row-details" data-testid={field('digest.last_fetch')}>
            <summary>上次抓取报告（{displayStamp(lastFetch.fetched_at) ?? '时间未知'}）</summary>
            <FetchReport report={lastFetch} />
          </details>
        ) : null}
      </div>
    )
  }

  return (
    <section
      className="panel"
      id="messages"
      data-testid={TESTIDS.driversMessages}
      aria-label="消息"
    >
      <div className="panel__head">
        <h3 className="panel__title">消息</h3>
        {refreshButton}
      </div>
      {body}
    </section>
  )
}