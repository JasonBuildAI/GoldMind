<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import type { Column } from '@/components/dataTable'
import MetadataBlock from '@/components/MetadataBlock.vue'
import PlaceholderNotice from '@/components/PlaceholderNotice.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SectionBlock from '@/components/SectionBlock.vue'
import SignOff from '@/components/SignOff.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useAsyncBlock } from '@/composables/useAsyncBlock'
import { useFreshnessBlock } from '@/composables/useFreshnessBlock'
import { formatUsd } from '@/lib/format'
import { isPlaceholder } from '@/lib/placeholder'
import { marketSummaryApi, type MarketSummaryResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

/**
 * 今日结论：全页第一屏的收束 —— 一行核心观点 + 关键数字，论据收进一层折叠。
 * 数字进表格；取不到就整段如实说明，不用写死的文案补位。
 */
interface SummaryData {
  raw: MarketSummaryResponse
  generatedAt: string
  placeholder: boolean
}

interface TargetRow {
  institution: string
  target: number
  probability: string
  timeframe: string
}

const TARGET_COLUMNS: ReadonlyArray<Column<TargetRow>> = [
  { key: 'institution', header: '机构' },
  { key: 'target', header: '目标价', numeric: true, source: '机构公开观点（模型整理）' },
  { key: 'probability', header: '置信度' },
  { key: 'timeframe', header: '时间框架' },
]

const { data, loading, refreshing, error, load } = useAsyncBlock<SummaryData>(
  async (refresh) => {
    const response = await marketSummaryApi.getMarketSummary(refresh)
    return {
      raw: response,
      generatedAt: response.metadata?.generated_at ?? '',
      placeholder: isPlaceholder(response.metadata),
    }
  },
  // 超时单独给文案：分析接口要跑一次 LLM，超时的处置（稍后重试）与
  // 「取不到结果」不同，笼统写「获取失败」用户不知道该做什么。
  { fallback: '获取最新分析失败。', timeout: '分析耗时较长，请稍后重试刷新。' },
)

void load()

const summary = computed(() => data.value?.raw ?? null)
const judgment = computed(() => summary.value?.comprehensive_judgment ?? null)
const targets = computed<TargetRow[]>(() => (summary.value?.institution_targets ?? []) as TargetRow[])
const placeholder = computed(() => Boolean(data.value?.placeholder))

/** 内容判定：任一字段有值就算「有结论」，否则按三态处理。 */
const hasContent = computed(() => {
  const value = summary.value
  if (!value) return false
  return Boolean(
    value.core_bullish_logic?.length ||
      value.main_risks?.length ||
      value.market_consensus?.length ||
      value.institution_targets?.length ||
      value.core_view ||
      value.investment_recommendation ||
      value.confidence_level ||
      value.time_horizon ||
      (judgment.value && Object.values(judgment.value).some(Boolean)),
  )
})

useFreshnessBlock(
  'conclusion',
  '今日结论',
  computed(() =>
    placeholder.value ? 'analyzing' : error.value ? 'unavailable' : hasContent.value ? 'fresh' : 'pending',
  ),
  computed(() => data.value?.generatedAt || null),
)

const judgmentGroups = computed(() => {
  const value = judgment.value
  if (!value) return []
  return [
    { key: 'bullish_summary', title: '看多理由', text: value.bullish_summary },
    { key: 'bearish_summary', title: '看空理由', text: value.bearish_summary },
    { key: 'neutral_summary', title: '中性观点', text: value.neutral_summary },
  ].filter((group) => Boolean(group.text))
})

const pointGroups = computed(() => {
  const value = summary.value
  if (!value) return []
  return [
    { key: 'core_bullish_logic', title: '核心看涨逻辑', points: value.core_bullish_logic ?? [] },
    { key: 'main_risks', title: '主要风险', points: value.main_risks ?? [] },
    { key: 'market_consensus', title: '市场共识', points: value.market_consensus ?? [] },
  ].filter((group) => group.points.length > 0)
})
</script>

<template>
  <SectionBlock
    id="conclusion"
    title="今日结论"
    intro="先读这一节：一行核心观点与关键数字；多空要点、综合判断与生成信息收在展开层里。"
  >
    <template #actions>
      <RefreshButton :busy="refreshing" label="重新分析" @click="load(true)" />
    </template>

    <!-- 没有内容：按「加载 / 正在分析 / 不可用」三态如实说明 -->
    <template v-if="!hasContent || !summary">
      <StateBlock v-if="loading" title="正在读取今日结论…" test-id="conclusion-loading" />
      <StateBlock
        v-else-if="placeholder"
        kind="analyzing"
        test-id="conclusion-analyzing"
        title="今日结论正在分析中"
        detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置结论 —— 编造的判断与真实分析长得一样，用户分不出来。"
      >
        <template #actions>
          <RefreshButton :busy="refreshing" label="重新分析" @click="load(true)" />
        </template>
      </StateBlock>
      <StateBlock
        v-else
        kind="unavailable"
        test-id="conclusion-unavailable"
        title="今日结论暂不可用"
        :detail="error ?? '没能取到分析结果。这里不显示任何内置结论 —— 与其摆一段编造的判断，不如如实说明取不到。'"
      >
        <template #actions>
          <RefreshButton :busy="refreshing" label="重新分析" @click="load(true)" />
        </template>
      </StateBlock>
    </template>

    <div v-else class="stack stack--lg" :data-testid="TESTIDS.conclusionSummary">
      <PlaceholderNotice :show="placeholder" test-id="conclusion-placeholder" />

      <p class="section__conclusion" :data-testid="fieldTestId('summary.core_view')">
        {{ summary.core_view || '—' }}
      </p>

      <dl class="metrics">
        <div>
          <dt>当前价格</dt>
          <dd class="num" :data-testid="fieldTestId('summary.current_price')">
            {{ summary.current_price ? formatUsd(summary.current_price) : '—' }}
          </dd>
        </div>
        <div>
          <dt>置信度</dt>
          <dd :data-testid="fieldTestId('summary.confidence_level')">
            {{ summary.confidence_level || '—' }}
          </dd>
        </div>
        <div>
          <dt>时间框架</dt>
          <dd :data-testid="fieldTestId('summary.time_horizon')">
            {{ summary.time_horizon || '—' }}
          </dd>
        </div>
        <div>
          <dt>投资建议</dt>
          <dd class="metrics__note" :data-testid="fieldTestId('summary.investment_recommendation')">
            {{ summary.investment_recommendation || '—' }}
          </dd>
        </div>
      </dl>

      <details class="row-details" :data-testid="TESTIDS.conclusionDetails">
        <summary>展开论据：多空要点与综合判断</summary>

        <div class="conclusion__details">
          <div class="grid-3">
            <div v-for="group in pointGroups" :key="group.key">
              <h3 class="panel__title">{{ group.title }}</h3>
              <ul class="point-list" :data-testid="fieldTestId(`summary.${group.key}`)">
                <li v-for="(point, index) in group.points" :key="`${index}-${point}`">{{ point }}</li>
              </ul>
            </div>
          </div>

          <div v-if="judgmentGroups.length > 0" class="doc-block">
            <h3 class="panel__title">综合判断</h3>
            <div v-for="group in judgmentGroups" :key="group.key" class="doc-block">
              <h4>{{ group.title }}</h4>
              <p :data-testid="fieldTestId(`summary.comprehensive_judgment.${group.key}`)">
                {{ group.text }}
              </p>
            </div>
          </div>

          <div v-if="summary.metadata" class="conclusion__metadata">
            <h3 class="panel__title">生成信息</h3>
            <MetadataBlock :metadata="summary.metadata" />
          </div>
        </div>
      </details>

      <div v-if="targets.length > 0" class="panel">
        <h3 class="panel__title">目标价参考</h3>
        <div :data-testid="TESTIDS.conclusionTargets">
          <DataTable
            :rows="targets"
            :columns="TARGET_COLUMNS"
            :row-key="(row) => row.institution"
            caption="目标价来自机构公开观点（由模型整理），不是本页的价格预测；当前价格为行情数据。"
          >
            <template #institution="{ row }">
              <span :data-testid="fieldTestId('summary.institution_targets.institution')">
                {{ row.institution }}
              </span>
            </template>
            <template #target="{ row }">
              <span :data-testid="fieldTestId('summary.institution_targets.target')">
                {{ row.target ? formatUsd(row.target) : '—' }}
              </span>
            </template>
            <template #probability="{ row }">
              <span :data-testid="fieldTestId('summary.institution_targets.probability')">
                {{ row.probability || '—' }}
              </span>
            </template>
            <template #timeframe="{ row }">
              <span :data-testid="fieldTestId('summary.institution_targets.timeframe')">
                {{ row.timeframe || '—' }}
              </span>
            </template>
          </DataTable>
        </div>
      </div>

      <p v-if="error" class="panel__error">刷新失败：{{ error }}</p>

      <SignOff :generated-at="data?.generatedAt" />
    </div>
  </SectionBlock>
</template>

<style scoped>
.conclusion__details {
  display: grid;
  gap: 20px;
  margin-top: 12px;
}

.conclusion__metadata {
  margin-top: 4px;
}
</style>
