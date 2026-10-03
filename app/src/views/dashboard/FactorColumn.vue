<script setup lang="ts">
import FactorList, { type FactorItem } from '@/components/FactorList.vue'
import Disclosure from '@/components/Disclosure.vue'
import MetadataBlock from '@/components/MetadataBlock.vue'
import PlaceholderNotice from '@/components/PlaceholderNotice.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SignOff from '@/components/SignOff.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useAsyncBlock } from '@/composables/useAsyncBlock'
import { useFreshnessBlock } from '@/composables/useFreshnessBlock'
import { displayStamp } from '@/lib/format'
import { isPlaceholder, type ApiMetadata } from '@/lib/placeholder'
import { analysisApi } from '@/services/api'
import { fieldTestId } from '@/testids'
import { computed } from 'vue'

/**
 * 一侧因子栏（看涨或看跌）：一行结论 + 关键数字在最上，逐条因子收进一层折叠。
 *
 * 两侧各自独立取数、独立刷新 —— 一侧接口挂了，另一侧照常显示自己的结果。
 * 任何状态都不摆内置内容：宁可显示「暂不可用」。
 */
const props = defineProps<{
  side: 'bullish' | 'bearish'
  heading: string
  testId: string
}>()

interface Side {
  factors: FactorItem[]
  summary: string
  updatedAt: string
  generatedAt: string
  placeholder: boolean
  metadata: ApiMetadata | null
}

/** 两侧的响应字段名不同，在这里归一成同一种形状。 */
function sideFrom(
  factors: FactorItem[] | undefined,
  summary: string | undefined,
  updatedAt: string | undefined,
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

const { data, loading, refreshing, error, load } = useAsyncBlock<Side>(
  async (refresh) => {
    if (props.side === 'bullish') {
      const response = await analysisApi.getBullishFactors(refresh)
      return sideFrom(
        response.bullish_factors,
        response.analysis_summary,
        response.last_updated,
        response.metadata,
      )
    }
    const response = await analysisApi.getBearishFactors(refresh)
    return sideFrom(
      response.bearish_factors,
      response.analysis_summary,
      response.last_updated,
      response.metadata,
    )
  },
  { fallback: '获取最新分析失败。', timeout: '分析耗时较长，请稍后重试刷新。' },
)

void load()

const placeholder = computed(() => Boolean(data.value?.placeholder))
const factors = computed(() => data.value?.factors ?? [])
/** 有内容 = 至少一条因子；只有总结没有因子也算取不到内容。 */
const hasContent = computed(() => factors.value.length > 0)

/**
 * 「正在分析中」只在**没有内容**时才是整块状态；有内容时占位标记降级成
 * 内容顶部的一条提示条（后端缓存未命中时会先返回一份结构与真实分析完全
 * 一样的内置内容，不看 metadata 就分辨不出来）。
 */
const analyzingEmpty = computed(() => placeholder.value && !hasContent.value)

const highImpact = computed(() => factors.value.filter((factor) => factor.impact === 'high').length)

useFreshnessBlock(
  props.side,
  computed(() => props.heading),
  computed(() =>
    placeholder.value ? 'analyzing' : error.value || !data.value ? 'unavailable' : 'fresh',
  ),
  computed(() => data.value?.generatedAt || data.value?.updatedAt || null),
)
</script>

<template>
  <section class="panel" :data-testid="testId" :aria-label="heading">
    <div class="panel__head">
      <h3 class="panel__title">{{ heading }}</h3>
      <RefreshButton :busy="refreshing" label="重新分析" @click="load(true)" />
    </div>

    <StateBlock v-if="loading" :title="`正在读取${heading}…`" :test-id="`${side}-loading`" />
    <StateBlock
      v-else-if="analyzingEmpty"
      kind="analyzing"
      :test-id="`${side}-analyzing`"
      :title="`${heading}正在分析中`"
      detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置内容 —— 编造的结论与真实分析长得一样，用户分不出来。"
    />
    <StateBlock
      v-else-if="!hasContent"
      kind="unavailable"
      :test-id="`${side}-unavailable`"
      :title="`${heading}暂不可用`"
      :detail="error ?? '没能取到分析结果。这里不显示任何内置文案，如实说明取不到。'"
    />

    <div v-else class="stack">
      <PlaceholderNotice :show="placeholder" :test-id="`${side}-placeholder`" />

      <p class="section__conclusion" :data-testid="fieldTestId(`${side}.analysis_summary`)">
        {{ data?.summary || `${heading}暂无总结。` }}
      </p>

      <dl class="metrics">
        <div>
          <dt>条数</dt>
          <dd class="num">{{ factors.length }}</dd>
        </div>
        <div>
          <dt>高影响</dt>
          <dd class="num">{{ highImpact }}</dd>
        </div>
        <div>
          <dt>分析时间</dt>
          <dd :data-testid="fieldTestId(`${side}.last_updated`)">
            {{ displayStamp(data?.updatedAt) ?? '—' }}
          </dd>
        </div>
      </dl>

      <!--
        逐条因子本身每条就是一个折叠 —— 不能再套一层「展开逐条因子」的
        外层折叠：可读性规范要求折叠最多一层，嵌套两层会让键盘用户
        必须按两次才看得到一条要点。
      -->
      <FactorList :factors="factors" :field-prefix="side" />

      <Disclosure title="生成信息（缓存、来源与方法）">
        <MetadataBlock :metadata="data?.metadata" />
      </Disclosure>

      <p v-if="error" class="panel__error">刷新失败：{{ error }}</p>

      <SignOff :generated-at="data?.generatedAt || data?.updatedAt" />
    </div>
  </section>
</template>
