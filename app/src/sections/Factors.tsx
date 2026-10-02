import { useCallback, useEffect, useState, type ReactNode } from 'react'

import FactorList, { type Factor } from '@/components/FactorList'
import MetadataBlock from '@/components/MetadataBlock'
import PlaceholderNotice from '@/components/PlaceholderNotice'
import RefreshButton from '@/components/RefreshButton'
import SignOff from '@/components/SignOff'
import StateBlock from '@/components/StateBlock'
import { useFreshnessBlock } from '@/contexts/FreshnessContext'
import { describeApiError } from '@/lib/apiError'
import { displayStamp } from '@/lib/format'
import { isPlaceholder, type ApiMetadata } from '@/lib/placeholder'
import { analysisApi } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

/** 一侧因子取回后的统一形状 —— 看涨与看跌的字段名不同，在这里归一。 */
interface Side {
  factors: Factor[]
  summary: string
  updatedAt: string
  generatedAt: string
  placeholder: boolean
  metadata: ApiMetadata | null
}

function sideFrom(
  factors: Factor[],
  summary: string,
  updatedAt: string,
  metadata: ApiMetadata | null | undefined,
): Side {
  return {
    factors: factors ?? [],
    summary: summary ?? '',
    updatedAt: updatedAt ?? '',
    generatedAt: metadata?.generated_at ?? '',
    // 先记占位标记：后端在「正在分析」时返回的是空列表，
    // 放在长度判断里面就永远设不上，页面会把「正在分析」错报成「暂不可用」。
    placeholder: isPlaceholder(metadata),
    metadata: metadata ?? null,
  }
}

function readBullish(refresh: boolean): Promise<Side> {
  return analysisApi
    .getBullishFactors(refresh)
    .then((response) =>
      sideFrom(
        response.bullish_factors ?? [],
        response.analysis_summary ?? '',
        response.last_updated ?? '',
        response.metadata,
      ),
    )
}

function readBearish(refresh: boolean): Promise<Side> {
  return analysisApi
    .getBearishFactors(refresh)
    .then((response) =>
      sideFrom(
        response.bearish_factors ?? [],
        response.analysis_summary ?? '',
        response.last_updated ?? '',
        response.metadata,
      ),
    )
}

/**
 * 一侧的因子栏：一行结论 + 关键数字在最上，逐条因子收进一层折叠。
 *
 * 两侧共用一个组件，但谁也不知道对方的存在 —— 看涨接口挂了，
 * 看跌一侧照常显示自己的结果。任何状态都不摆内置内容。
 */
function FactorColumn({
  side,
  id,
  heading,
  load,
}: {
  side: 'bullish' | 'bearish'
  id: string
  heading: string
  load: (refresh: boolean) => Promise<Side>
}) {
  const [data, setData] = useState<Side | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSide = useCallback(
    async (refresh = false) => {
      if (refresh) {
        setRefreshing(true)
      } else {
        setLoading(true)
      }
      setError(null)

      try {
        setData(await load(refresh))
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
    },
    [load],
  )

  useEffect(() => {
    void fetchSide()
  }, [fetchSide])

  const placeholder = Boolean(data?.placeholder)
  useFreshnessBlock(
    side,
    heading,
    placeholder ? 'analyzing' : error || !data ? 'unavailable' : 'fresh',
    data?.generatedAt || data?.updatedAt || null,
  )

  const refreshButton = (
    <RefreshButton onClick={() => void fetchSide(true)} busy={refreshing} label="重新分析" />
  )

  const wrapper = (inner: ReactNode) => (
    <section
      className="panel"
      id={id}
      data-testid={side === 'bullish' ? TESTIDS.bullishFactors : TESTIDS.bearishFactors}
      aria-label={heading}
    >
      <div className="panel__head">
        <h3 className="panel__title">{heading}</h3>
        {refreshButton}
      </div>
      {inner}
    </section>
  )

  if (!data || data.factors.length === 0) {
    if (loading) {
      return wrapper(<StateBlock title={`正在读取${heading}…`} testId={`${side}-loading`} />)
    }
    if (data?.placeholder) {
      return wrapper(
        <StateBlock
          kind="analyzing"
          testId={`${side}-analyzing`}
          title={`${heading}正在分析中`}
          detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置内容 —— 编造的结论与真实分析长得一样，用户分不出来。"
        />,
      )
    }
    return wrapper(
      <StateBlock
        kind="unavailable"
        testId={`${side}-unavailable`}
        title={`${heading}暂不可用`}
        detail={error ?? '没能取到分析结果。这里不显示任何内置文案，如实说明取不到。'}
      />,
    )
  }

  const highImpact = data.factors.filter((factor) => factor.impact === 'high').length

  return wrapper(
    <div className="space-y-6">
      <PlaceholderNotice show={data.placeholder} testId={`${side}-placeholder`} />
      <p className="section__conclusion" data-testid={fieldTestId(`${side}.analysis_summary`)}>
        {data.summary || `${heading}暂无总结。`}
      </p>
      <dl className="metrics">
        <div>
          <dt>条数</dt>
          <dd className="num">{data.factors.length}</dd>
        </div>
        <div>
          <dt>高影响</dt>
          <dd className="num">{highImpact}</dd>
        </div>
        <div>
          <dt>分析时间</dt>
          <dd data-testid={fieldTestId(`${side}.last_updated`)}>
            {displayStamp(data.updatedAt) ?? '—'}
          </dd>
        </div>
      </dl>

      <details className="row-details">
        <summary>展开逐条因子（{data.factors.length} 条）</summary>
        <FactorList factors={data.factors} fieldPrefix={side} />
        <MetadataBlock metadata={data.metadata} />
      </details>

      {error ? <p className="panel__error">刷新失败：{error}</p> : null}
      <SignOff generatedAt={data.generatedAt || data.updatedAt} />
    </div>,
  )
}

/** 驱动一侧（看涨 / 看跌）的并列展示：由驱动区块包住，不各自成节。 */
export default function Factors() {
  return (
    <div className="space-y-8">
      <FactorColumn side="bullish" id="drivers-bullish" heading="看涨因素" load={readBullish} />
      <FactorColumn side="bearish" id="drivers-bearish" heading="看跌因素" load={readBearish} />
    </div>
  )
}