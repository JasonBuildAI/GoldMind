import { useCallback, useEffect, useState, type ReactNode } from 'react'

import FactorList, { type Factor } from '@/components/FactorList'
import PlaceholderNotice from '@/components/PlaceholderNotice'
import RefreshButton from '@/components/RefreshButton'
import Section from '@/components/Section'
import SignOff from '@/components/SignOff'
import StateBlock from '@/components/StateBlock'
import { describeApiError } from '@/lib/apiError'
import { isPlaceholder } from '@/lib/placeholder'
import { analysisApi } from '@/services/api'

/** 一侧因子取回后的统一形状 —— 看涨与看跌的字段名不同，在这里归一。 */
interface Side {
  factors: Factor[]
  summary: string
  updatedAt: string
  generatedAt: string
  placeholder: boolean
}

function readBullish(refresh: boolean): Promise<Side> {
  return analysisApi.getBullishFactors(refresh).then((response) => ({
    factors: response.bullish_factors ?? [],
    summary: response.analysis_summary ?? '',
    updatedAt: response.last_updated ?? '',
    generatedAt: response.metadata?.generated_at ?? '',
    // 先记占位标记：后端在「正在分析」时返回的是空列表，
    // 放在长度判断里面就永远设不上，页面会把「正在分析」错报成「暂不可用」。
    placeholder: isPlaceholder(response.metadata),
  }))
}

function readBearish(refresh: boolean): Promise<Side> {
  return analysisApi.getBearishFactors(refresh).then((response) => ({
    factors: response.bearish_factors ?? [],
    summary: response.analysis_summary ?? '',
    updatedAt: response.last_updated ?? '',
    generatedAt: response.metadata?.generated_at ?? '',
    placeholder: isPlaceholder(response.metadata),
  }))
}

/**
 * 一侧的因子栏：独立取数、独立刷新、独立的空态与占位标注。
 *
 * 两侧共用一个组件，但谁也不知道对方的存在 —— 看涨接口挂了，
 * 看跌一侧照常显示自己的结果。
 */
function FactorColumn({
  side,
  heading,
  lead,
  load,
}: {
  side: 'bullish' | 'bearish'
  heading: string
  lead: string
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
        // 统一翻译：429 会说清等多久，503 会用后端给的原因，
        // 而不是一律「获取最新分析失败」—— 那对限流既不准也不可操作。
        setError(
          describeApiError(err, {
            fallback: '获取最新分析失败。',
            timeout: '分析耗时较长，请稍后重试刷新。',
          }),
        )
        // 不填充任何编造的内容：保持为空，由下面的空状态如实说明。
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

  // 两侧的锚点（data-testid）必须在任何状态下都存在：
  // 端到端测试与页面内导航都靠它定位这一栏。
  const column = (inner: ReactNode) => <div data-testid={`${side}-factors`}>{inner}</div>

  if (!data || data.factors.length === 0) {
    if (loading) {
      return column(<StateBlock title={`正在读取${heading}…`} testId={`${side}-loading`} />)
    }

    if (data?.placeholder) {
      return column(
        <StateBlock
          kind="analyzing"
          testId={`${side}-analyzing`}
          title={`${heading}正在分析中`}
          detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置内容 —— 编造的结论与真实分析长得一样，用户分不出来。"
          actions={
            <RefreshButton onClick={() => void fetchSide(true)} busy={refreshing} label="重新分析" />
          }
        />
      )
    }

    return column(
      <StateBlock
        kind="unavailable"
        testId={`${side}-unavailable`}
        title={`${heading}暂不可用`}
        detail={error ?? '没能取到分析结果。这里不显示任何内置文案，如实说明取不到。'}
        actions={
          <RefreshButton onClick={() => void fetchSide(true)} busy={refreshing} label="重新分析" />
        }
      />
    )
  }

  return column(
    <div className="panel">
      <div className="panel__head">
        <h3 className="panel__title">{heading}</h3>
        <RefreshButton onClick={() => void fetchSide(true)} busy={refreshing} label="重新分析" />
      </div>

      <p className="panel__meta">
        <span>{lead}</span>
        {data.updatedAt ? <span>数据时间 {data.updatedAt}</span> : null}
        {error ? <span className="panel__error">刷新失败：{error}</span> : null}
      </p>

      {/* 缓存未命中时后端会返回一份内置占位内容，必须明确标注，
          否则用户会把内置常量当成分析结论。 */}
      <PlaceholderNotice show={data.placeholder} testId={`${side}-placeholder`} />

      <FactorList factors={data.factors} testId={`${side}-list`} />

      {data.summary ? (
        <div className="column__summary">
          <h4>{heading}总结</h4>
          <p data-testid={`${side}-summary`}>{data.summary}</p>
        </div>
      ) : null}

      <SignOff generatedAt={data.generatedAt || data.updatedAt} />
    </div>,
  )
}

/**
 * 多空对照：同一批新闻与市场数据，分别从看涨与看跌两个方向整理。
 * 两栏各自取数、各自刷新 —— 一侧不可用不影响另一侧。
 */
export default function Factors() {
  return (
    <Section
      id="factors"
      title="多空对照"
      intro="看涨与看跌两栏来自两次独立分析，各自取数、各自刷新；一侧不可用不影响另一侧。"
    >
      <div className="grid gap-8 lg:grid-cols-2">
        <FactorColumn
          side="bullish"
          heading="看涨因素"
          lead="支持金价上行的论据"
          load={readBullish}
        />
        <FactorColumn
          side="bearish"
          heading="看跌因素"
          lead="压制金价的论据与风险"
          load={readBearish}
        />
      </div>
    </Section>
  )
}
