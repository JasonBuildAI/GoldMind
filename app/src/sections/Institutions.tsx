import { useCallback, useEffect, useState } from 'react'

import InstitutionTable from '@/components/InstitutionTable'
import MetadataBlock from '@/components/MetadataBlock'
import PlaceholderNotice from '@/components/PlaceholderNotice'
import RefreshButton from '@/components/RefreshButton'
import SignOff from '@/components/SignOff'
import StateBlock from '@/components/StateBlock'
import { useFreshnessBlock } from '@/contexts/FreshnessContext'
import { describeApiError } from '@/lib/apiError'
import { displayStamp } from '@/lib/format'
import { isPlaceholder, type ApiMetadata } from '@/lib/placeholder'
import { institutionApi, type InstitutionPrediction } from '@/services/api'
import { TESTIDS } from '@/testids'

interface InstitutionsData {
  institutions: InstitutionPrediction[]
  summary: string
  updatedAt: string
  generatedAt: string
  placeholder: boolean
  metadata: ApiMetadata | null
}

/**
 * 机构观点：一行结论 + 评级计数，全部字段进表格。
 *
 * 机构目标价是最不能编的东西 —— 取不到就明说不可用，绝不用内置名单或
 * 模型印象补一个数字（见 docs/00-产品方向.md 第四节）。
 */
export default function Institutions() {
  const [data, setData] = useState<InstitutionsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchInstitutions = useCallback(async (refresh = false) => {
    if (refresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const response = await institutionApi.getInstitutionPredictions(refresh)
      setData({
        institutions: response.institutions ?? [],
        summary: response.analysis_summary ?? '',
        updatedAt: response.last_updated ?? '',
        generatedAt: response.metadata?.generated_at ?? '',
        placeholder: isPlaceholder(response.metadata),
        metadata: response.metadata ?? null,
      })
    } catch (err) {
      setError(
        describeApiError(err, {
          fallback: '获取最新分析失败。',
          timeout: '分析耗时较长，请稍后重试刷新。',
        }),
      )
      setData(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void fetchInstitutions()
  }, [fetchInstitutions])

  const placeholder = Boolean(data?.placeholder)
  useFreshnessBlock(
    'institutions',
    '机构观点',
    placeholder ? 'analyzing' : error || !data ? 'unavailable' : 'fresh',
    data?.generatedAt || data?.updatedAt || null,
  )

  const refreshButton = (
    <RefreshButton onClick={() => void fetchInstitutions(true)} busy={refreshing} label="重新抓取" />
  )

  let body
  if (!data || data.institutions.length === 0) {
    if (loading) {
      body = <StateBlock title="正在读取机构观点…" testId="institutions-loading" />
    } else if (data?.placeholder) {
      body = (
        <StateBlock
          kind="analyzing"
          testId="institutions-analyzing"
          title="机构观点正在分析中"
          detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置名单 —— 编造的目标价与真实分析长得一样，用户分不出来。"
          actions={refreshButton}
        />
      )
    } else {
      body = (
        <StateBlock
          kind="unavailable"
          testId="institutions-unavailable"
          title="机构观点暂不可用"
          detail={error ?? '没能取到机构观点。这里不显示任何目标价 —— 编造机构目标价比留空更糟。'}
          actions={refreshButton}
        />
      )
    }
  } else {
    const counts = {
      bullish: data.institutions.filter((item) => item.rating === 'bullish').length,
      neutral: data.institutions.filter((item) => item.rating === 'neutral').length,
      bearish: data.institutions.filter((item) => item.rating === 'bearish').length,
    }

    body = (
      <div>
        <PlaceholderNotice show={data.placeholder} testId="institutions-placeholder" />

        <p className="section__conclusion">
          共 {data.institutions.length} 家机构：看涨 {counts.bullish} · 中性 {counts.neutral} · 看跌{' '}
          {counts.bearish}；最近更新 {displayStamp(data.updatedAt) ?? '时间未知'}。
        </p>

        <p className="panel__meta">
          <span>共 {data.institutions.length} 家机构</span>
          <span>
            看涨 {counts.bullish} · 中性 {counts.neutral} · 看跌 {counts.bearish}
          </span>
          {data.updatedAt ? <span>数据时间 {data.updatedAt}</span> : null}
          {error ? <span className="panel__error">刷新失败：{error}</span> : null}
        </p>

        <InstitutionTable institutions={data.institutions} testId={TESTIDS.institutionsTable} />

        <p className="provenance">
          机构观点取每家机构最近一次可核实的预测，可能滞后 —— 表内标注预测日期，超过 30
          天会注明滞后天数；目标价是机构给出的点位，不是本页的价格预测。线索来源 web_search
          = 联网搜索、news_scan = 新闻扫描、legacy = 历史库记录。
        </p>

        {data.summary ? (
          <div className="column__summary">
            <h4>机构观点总结</h4>
            <p data-testid={TESTIDS.institutionsSummary}>{data.summary}</p>
          </div>
        ) : null}

        <MetadataBlock metadata={data.metadata} />

        <SignOff generatedAt={data.generatedAt || data.updatedAt} />
      </div>
    )
  }

  return (
    <section
      className="panel"
      id="institutions"
      data-testid={TESTIDS.driversInstitutions}
      aria-label="机构观点"
    >
      <div className="panel__head">
        <h3 className="panel__title">机构观点</h3>
        {refreshButton}
      </div>
      {body}
    </section>
  )
}