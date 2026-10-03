<script setup lang="ts">
import InstitutionTable from '@/components/InstitutionTable.vue'
import MetadataBlock from '@/components/MetadataBlock.vue'
import PlaceholderNotice from '@/components/PlaceholderNotice.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SignOff from '@/components/SignOff.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useAsyncBlock } from '@/composables/useAsyncBlock'
import { useFreshnessBlock } from '@/composables/useFreshnessBlock'
import { displayStamp } from '@/lib/format'
import { isPlaceholder, type ApiMetadata } from '@/lib/placeholder'
import { institutionApi, type InstitutionPrediction } from '@/services/api'
import { TESTIDS } from '@/testids'
import { computed } from 'vue'

/**
 * 机构观点：一行结论 + 评级计数，全部字段进表格。
 *
 * 机构目标价是最不能编的东西 —— 取不到就明说不可用，绝不用内置名单或
 * 模型印象补一个数字（见 docs/00-产品方向.md 第四节）。
 */
interface InstitutionsData {
  institutions: InstitutionPrediction[]
  summary: string
  updatedAt: string
  generatedAt: string
  placeholder: boolean
  metadata: ApiMetadata | null
}

const { data, loading, refreshing, error, load } = useAsyncBlock<InstitutionsData>(
  async (refresh) => {
    const response = await institutionApi.getInstitutionPredictions(refresh)
    return {
      institutions: response.institutions ?? [],
      summary: response.analysis_summary ?? '',
      updatedAt: response.last_updated ?? '',
      generatedAt: response.metadata?.generated_at ?? '',
      placeholder: isPlaceholder(response.metadata),
      metadata: response.metadata ?? null,
    }
  },
  // 超时单独给文案：分析接口要跑一次 LLM，超时的处置（稍后重试）与
  // 「取不到结果」不同，笼统写「获取失败」用户不知道该做什么。
  { fallback: '获取最新分析失败。', timeout: '分析耗时较长，请稍后重试刷新。' },
)

void load()

const placeholder = computed(() => Boolean(data.value?.placeholder))
const institutions = computed(() => data.value?.institutions ?? [])
const hasContent = computed(() => institutions.value.length > 0)

const counts = computed(() => ({
  bullish: institutions.value.filter((item) => item.rating === 'bullish').length,
  neutral: institutions.value.filter((item) => item.rating === 'neutral').length,
  bearish: institutions.value.filter((item) => item.rating === 'bearish').length,
}))

useFreshnessBlock(
  'institutions',
  '机构观点',
  computed(() =>
    placeholder.value ? 'analyzing' : error.value || !data.value ? 'unavailable' : 'fresh',
  ),
  computed(() => data.value?.generatedAt || data.value?.updatedAt || null),
)
</script>

<template>
  <section class="panel" id="institutions" :data-testid="TESTIDS.driversInstitutions" aria-label="机构观点">
    <div class="panel__head">
      <h3 class="panel__title">机构观点</h3>
      <RefreshButton :busy="refreshing" label="重新抓取" @click="load(true)" />
    </div>

    <!--
      占位提示条挂在三态之外：后端在「正在分析」时给的是空列表 + 占位标记，
      这条提示必须在**两种**分支里都出现 —— 只放在内容分支里会让
      「正在分析中」这一屏丢掉「这不是本次分析结果」的说明。
    -->
    <PlaceholderNotice :show="placeholder" test-id="institutions-placeholder" />

    <StateBlock v-if="loading" title="正在读取机构观点…" test-id="institutions-loading" />
    <StateBlock
      v-else-if="placeholder"
      kind="analyzing"
      test-id="institutions-analyzing"
      title="机构观点正在分析中"
      detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置名单 —— 编造的目标价与真实分析长得一样，用户分不出来。"
    >
      <template #actions>
        <RefreshButton :busy="refreshing" label="重新抓取" @click="load(true)" />
      </template>
    </StateBlock>
    <StateBlock
      v-else-if="!hasContent"
      kind="unavailable"
      test-id="institutions-unavailable"
      title="机构观点暂不可用"
      :detail="error ?? '没能取到机构观点。这里不显示任何目标价 —— 编造机构目标价比留空更糟。'"
    >
      <template #actions>
        <RefreshButton :busy="refreshing" label="重新抓取" @click="load(true)" />
      </template>
    </StateBlock>

    <div v-else>
      <p class="section__conclusion">
        共 {{ institutions.length }} 家机构：看涨 {{ counts.bullish }} · 中性 {{ counts.neutral }} ·
        看跌 {{ counts.bearish }}；最近更新 {{ displayStamp(data?.updatedAt) ?? '时间未知' }}。
      </p>

      <p class="panel__meta">
        <span>共 {{ institutions.length }} 家机构</span>
        <span>看涨 {{ counts.bullish }} · 中性 {{ counts.neutral }} · 看跌 {{ counts.bearish }}</span>
        <span v-if="data?.updatedAt">数据时间 {{ data.updatedAt }}</span>
        <span v-if="error" class="panel__error">刷新失败：{{ error }}</span>
      </p>

      <InstitutionTable :institutions="institutions" :test-id="TESTIDS.institutionsTable" />

      <p class="provenance">
        机构观点取每家机构最近一次可核实的预测，可能滞后 —— 表内标注预测日期，超过 30
        天会注明滞后天数；目标价是机构给出的点位，不是本页的价格预测。线索来源 web_search =
        联网搜索、news_scan = 新闻扫描、legacy = 历史库记录。
      </p>

      <div v-if="data?.summary" class="column__summary">
        <h4>机构观点总结</h4>
        <p :data-testid="TESTIDS.institutionsSummary">{{ data.summary }}</p>
      </div>

      <MetadataBlock :metadata="data?.metadata" />

      <SignOff :generated-at="data?.generatedAt || data?.updatedAt" />
    </div>
  </section>
</template>
