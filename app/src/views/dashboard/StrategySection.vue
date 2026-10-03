<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import GoldPriceAsOf from '@/components/GoldPriceAsOf.vue'
import type { Column } from '@/components/dataTable'
import MetadataBlock from '@/components/MetadataBlock.vue'
import PlaceholderNotice from '@/components/PlaceholderNotice.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SectionBlock from '@/components/SectionBlock.vue'
import SignOff from '@/components/SignOff.vue'
import StateBlock from '@/components/StateBlock.vue'
import StrategyColumns from '@/components/StrategyColumns.vue'
import { useAsyncBlock } from '@/composables/useAsyncBlock'
import { useFreshnessBlock } from '@/composables/useFreshnessBlock'
import { formatPercent, formatUsd } from '@/lib/format'
import { isPlaceholder, type ApiMetadata } from '@/lib/placeholder'
import {
  investmentAdviceApi,
  type AdvicePriceSnapshot,
  type CorePrinciple,
  type InvestmentStrategy,
  type MarketAssessment,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

/**
 * 投资策略：市场评估 + 保守 / 均衡 / 机会三档横向对照 + 执行原则。
 *
 * 三档策略来自同一次分析，字段一样，读的时候可以横向比；取不到就整段留白，
 * 不摆内置策略。数据不足时后端会降级返回一份**确定性**行情统计（不是模型输出），
 * 那时页面明说「数据不足」，并把统计全字段摆出来。
 */
const RISK_LABEL: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

interface AdviceData {
  assessment: MarketAssessment | null
  strategies: InvestmentStrategy[]
  principles: CorePrinciple[]
  riskWarning: string
  disclaimer: string
  analysisStatus: string
  generatedAt: string
  placeholder: boolean
  degraded: boolean
  priceSnapshot: AdvicePriceSnapshot | null
  metadata: ApiMetadata | null
}

const PRINCIPLE_COLUMNS: ReadonlyArray<Column<CorePrinciple>> = [
  { key: 'title', header: '原则' },
  { key: 'description', header: '说明' },
]

const { data, loading, refreshing, error, load } = useAsyncBlock<AdviceData>(
  async (refresh) => {
    const response = await investmentAdviceApi.getInvestmentAdvice(refresh)
    return {
      assessment: response.market_assessment ?? null,
      strategies: response.strategies ?? [],
      principles: response.core_principles ?? [],
      riskWarning: response.risk_warning ?? '',
      disclaimer: response.disclaimer ?? '',
      analysisStatus: response.analysis_status ?? response.metadata?.status ?? '',
      generatedAt: response.metadata?.generated_at ?? '',
      placeholder: isPlaceholder(response.metadata),
      degraded:
        response.metadata?.status === 'insufficient_data' ||
        response.analysis_status === 'insufficient_data',
      priceSnapshot: response.price_snapshot ?? null,
      metadata: response.metadata ?? null,
    }
  },
  { fallback: '获取最新分析失败。', timeout: '分析耗时较长，请稍后重试刷新。' },
)

void load()

const assessment = computed(() =>
  data.value?.assessment && Object.keys(data.value.assessment).length > 0
    ? data.value.assessment
    : null,
)
const hasContent = computed(
  () =>
    Boolean(data.value) &&
    ((data.value?.strategies.length ?? 0) > 0 ||
      (data.value?.principles.length ?? 0) > 0 ||
      Boolean(assessment.value)),
)
const degraded = computed(() => Boolean(data.value?.degraded))
const placeholder = computed(() => Boolean(data.value?.placeholder))

/** 数据不足时的行情快照：确定性统计，逐行给字段名与值。 */
const SNAPSHOT_ROWS = computed(() => {
  const snapshot = data.value?.priceSnapshot
  if (!snapshot) return []
  return [
    { label: '标签', path: 'advice.snapshot.label', value: snapshot.label },
    { label: '窗口起', path: 'advice.snapshot.window_start', value: snapshot.window_start },
    { label: '窗口末', path: 'advice.snapshot.window_end', value: snapshot.window_end },
    { label: '最新价', path: 'advice.snapshot.latest_price', value: formatUsd(snapshot.latest_price) },
    { label: '区间涨跌', path: 'advice.snapshot.change_pct', value: formatPercent(snapshot.change_pct) },
    { label: '期间最高', path: 'advice.snapshot.high', value: formatUsd(snapshot.high) },
    { label: '期间最低', path: 'advice.snapshot.low', value: formatUsd(snapshot.low) },
    {
      label: '高低振幅',
      path: 'advice.snapshot.amplitude_pct',
      value: formatPercent(snapshot.amplitude_pct),
    },
    {
      label: '完整窗口',
      path: 'advice.snapshot.full_window',
      value: snapshot.full_window ? '是（窗口数据齐全）' : '否（窗口不完整）',
    },
  ]
})

useFreshnessBlock(
  'strategy',
  '投资策略',
  computed(() =>
    degraded.value
      ? 'stale'
      : placeholder.value
        ? 'analyzing'
        : error.value || !hasContent.value
          ? 'unavailable'
          : 'fresh',
  ),
  computed(() => data.value?.generatedAt || null),
)
</script>

<template>
  <SectionBlock
    id="strategy"
    title="投资策略"
    intro="三档策略来自同一次分析：保守、均衡、机会，字段一致，可以横向对照。仓位与区间是模型的建议，不是收益承诺。"
  >
    <template #actions>
      <RefreshButton :busy="refreshing" label="重新分析" @click="load(true)" />
    </template>

    <!-- 数据不足：后端没调模型，只给确定性行情统计 -->
    <div v-if="degraded" class="stack stack--lg">
      <StateBlock
        kind="unavailable"
        test-id="strategy-insufficient"
        title="数据不足，暂不生成策略"
        :detail="data?.riskWarning || '缺少可分析的数据输入，未调用模型。'"
      />
      <div v-if="SNAPSHOT_ROWS.length > 0" class="panel">
        <h3 class="panel__title">行情统计（仅供参考，全部字段）</h3>
        <div class="table-scroll">
          <table class="data-table">
            <tbody>
              <tr v-for="row in SNAPSHOT_ROWS" :key="row.path">
                <th scope="row">{{ row.label }}</th>
                <td class="num" :data-testid="fieldTestId(row.path)">{{ row.value }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- 快照价是金价（日收盘），它自己的交易日 / 口径 / 来源一起给 -->
        <GoldPriceAsOf
          label="快照价"
          :as-of="data?.priceSnapshot?.as_of"
          :basis-label="data?.priceSnapshot?.basis_label"
          :source="data?.priceSnapshot?.source"
          as-of-field="advice.snapshot.as_of"
          basis-field="advice.snapshot.basis_label"
          source-field="advice.snapshot.source"
        />
      </div>
      <MetadataBlock :metadata="data?.metadata" />
      <SignOff :generated-at="data?.generatedAt" />
    </div>

    <!-- 三态：加载 / 正在分析 / 不可用 -->
    <template v-else-if="!data || !hasContent">
      <StateBlock v-if="loading" title="正在读取投资策略…" test-id="strategy-loading" />
      <StateBlock
        v-else-if="placeholder"
        kind="analyzing"
        test-id="strategy-analyzing"
        title="投资策略正在分析中"
        detail="后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一套内置策略 —— 编造的建议与真实分析长得一样，用户分不出来。"
      >
        <template #actions>
          <RefreshButton :busy="refreshing" label="重新分析" @click="load(true)" />
        </template>
      </StateBlock>
      <StateBlock
        v-else
        kind="unavailable"
        test-id="strategy-unavailable"
        title="投资策略暂不可用"
        :detail="error ?? '没能取到分析结果。这里不显示任何内置策略 —— 与其摆一套编造的建议，不如如实说明取不到。'"
      >
        <template #actions>
          <RefreshButton :busy="refreshing" label="重新分析" @click="load(true)" />
        </template>
      </StateBlock>
    </template>

    <div v-else class="stack stack--lg">
      <PlaceholderNotice :show="placeholder" test-id="strategy-placeholder" />

      <template v-if="assessment">
        <p class="section__conclusion">
          {{ assessment.current_position || '市场评估见下表。' }}
        </p>
        <dl class="metrics">
          <div>
            <dt>当前位置</dt>
            <dd :data-testid="fieldTestId('advice.assessment.current_position')">
              {{ assessment.current_position || '—' }}
            </dd>
          </div>
          <div>
            <dt>风险等级</dt>
            <dd :data-testid="fieldTestId('advice.assessment.risk_level')">
              {{ RISK_LABEL[assessment.risk_level] ?? '未知' }}（{{ assessment.risk_level }}）
            </dd>
          </div>
          <div>
            <dt>建议策略</dt>
            <dd :data-testid="fieldTestId('advice.assessment.recommended_approach')">
              {{ assessment.recommended_approach || '—' }}
            </dd>
          </div>
          <div>
            <dt>关键考量</dt>
            <dd class="metrics__note" :data-testid="fieldTestId('advice.assessment.key_considerations')">
              {{ assessment.key_considerations.join('；') || '—' }}
            </dd>
          </div>
        </dl>
      </template>

      <template v-if="(data?.strategies.length ?? 0) > 0">
        <StrategyColumns :strategies="data!.strategies" :test-id="TESTIDS.strategyColumns" />
        <p class="provenance">
          仓位、区间与止盈止损是模型的建议，不是收益承诺；三档字段同名同序，可横向对照。
        </p>
      </template>

      <div v-if="(data?.principles.length ?? 0) > 0" class="panel">
        <h3 class="panel__title">执行原则</h3>
        <DataTable
          :rows="data!.principles"
          :columns="PRINCIPLE_COLUMNS"
          :row-key="(row) => row.title"
        >
          <template #title="{ row }">
            <span :data-testid="fieldTestId('advice.principles.title')">{{ row.title }}</span>
          </template>
          <template #description="{ row }">
            <span :data-testid="fieldTestId('advice.principles.description')">{{ row.description }}</span>
          </template>
        </DataTable>
      </div>

      <div class="panel">
        <h3 class="panel__title">风险提示与免责声明</h3>
        <p class="strategy__lead" :data-testid="fieldTestId('advice.risk_warning')">
          {{ data?.riskWarning || '—' }}
        </p>
        <p class="strategy__lead" :data-testid="fieldTestId('advice.disclaimer')">
          {{ data?.disclaimer || '—' }}
        </p>
        <p class="note" :data-testid="fieldTestId('advice.analysis_status')">
          分析状态：{{ data?.analysisStatus || '—' }}
        </p>
      </div>

      <p v-if="error" class="panel__error">刷新失败：{{ error }}</p>

      <MetadataBlock :metadata="data?.metadata" />
      <SignOff :generated-at="data?.generatedAt" />
    </div>
  </SectionBlock>
</template>
