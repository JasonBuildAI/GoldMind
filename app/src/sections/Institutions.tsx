import { useCallback, useEffect, useState } from 'react'

import InstitutionTable from '@/components/InstitutionTable'
import PlaceholderNotice from '@/components/PlaceholderNotice'
import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import SignOff from '@/components/SignOff'
import StateBlock from '@/components/StateBlock'
import { describeApiError } from '@/lib/apiError'
import { isPlaceholder } from '@/lib/placeholder'
import { institutionApi, type InstitutionPrediction } from '@/services/api'

interface InstitutionsData {
  institutions: InstitutionPrediction[]
  summary: string
  updatedAt: string
  generatedAt: string
  placeholder: boolean
}

/**
 * 机构观点：机构 / 评级 / 目标价 / 时间框架 / 理由。
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
        // 先记占位标记：后端在「正在分析」时返回的是空列表，
        // 放在长度判断里面就永远设不上，页面会把「正在分析」错报成「暂不可用」。
        placeholder: isPlaceholder(response.metadata),
      })
    } catch (err) {
      setError(
        describeApiError(err, {
          fallback: '获取最新分析失败。',
          timeout: '分析耗时较长，请稍后重试刷新。',
        }),
      )
      // 不填充任何编造的机构目标价：保持为空，由下面的空状态如实说明。
      setData(null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void fetchInstitutions()
  }, [fetchInstitutions])

  const refreshButton = (
    <RefreshButton
      onClick={() => void fetchInstitutions(true)}
      busy={refreshing}
      label="重新抓取"
    />
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
        />
      )
    } else {
      body = (
        <StateBlock
          kind="unavailable"
          testId="institutions-unavailable"
          title="机构观点暂不可用"
          detail={error ?? '没能取到机构观点。这里不显示任何目标价 —— 编造机构目标价比留空更糟。'}
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
      <div className="panel">
        {/* 缓存未命中时后端会返回一份内置占位内容，必须明确标注，
            否则用户会把内置常量当成分析结论。 */}
        <PlaceholderNotice show={data.placeholder} testId="institutions-placeholder" />

        <p className="panel__meta">
          <span>共 {data.institutions.length} 家机构</span>
          <span>
            看涨 {counts.bullish} · 中性 {counts.neutral} · 看跌 {counts.bearish}
          </span>
          {data.updatedAt ? <span>数据时间 {data.updatedAt}</span> : null}
          {error ? <span className="panel__error">刷新失败：{error}</span> : null}
        </p>

        <InstitutionTable institutions={data.institutions} testId="institutions-table" />

        {data.summary ? (
          <div className="column__summary">
            <h4>机构观点总结</h4>
            <p data-testid="institutions-summary">{data.summary}</p>
          </div>
        ) : null}

        <SignOff generatedAt={data.generatedAt || data.updatedAt} />
      </div>
    )
  }

  return (
    <Section
      id="institutions"
      title="机构观点"
      intro="机构评级、目标价与时间框架由模型基于公开新闻整理，可能滞后或不准确；目标价是机构给出的点位，不是本页的价格预测。"
      actions={refreshButton}
    >
      {body}
    </Section>
  )
}
