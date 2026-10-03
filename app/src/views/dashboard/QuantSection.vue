<script setup lang="ts">
import PanelBlock from '@/components/PanelBlock.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SectionBlock from '@/components/SectionBlock.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useAsyncBlock } from '@/composables/useAsyncBlock'
import { useFreshnessBlock } from '@/composables/useFreshnessBlock'
import { displayStamp, formatShare, formatUsd } from '@/lib/format'
import {
  quantApi,
  type QuantAccuracyResponse,
  type QuantFactorsResponse,
  type QuantMonitorResponse,
  type QuantPredictionsResponse,
  type QuantResearchResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed, ref } from 'vue'

import AccuracyPanel from './quant/AccuracyPanel.vue'
import FactorTables from './quant/FactorTables.vue'
import FairValuePanel from './quant/FairValuePanel.vue'
import MonitorTable from './quant/MonitorTable.vue'
import ScaleTab from './quant/ScaleTab.vue'
import SourcesStatus from './quant/SourcesStatus.vue'

/**
 * 量化预测：决策尺度 tab、公允价值、监测信号、回测评估、四类因素表。
 *
 * 所有数字都由后端给出；任一环节算不出来都如实标注，不摆内置数字。
 * 研究接口只用于回测面板里的前向裁决证据（Beta 后验），取不到不影响其余面板。
 *
 * 五个尺度共用一份 `horizon` 状态：预测与回测两组 tab 联动，切换只改视图、不重新取数。
 */
interface QuantData {
  factors: QuantFactorsResponse
  predictions: QuantPredictionsResponse
  accuracy: QuantAccuracyResponse
  monitor: QuantMonitorResponse
  research: QuantResearchResponse | null
}

const field = (path: string) => fieldTestId(path)

/** 一年尺度的一句话结论（没有就退回最短尺度）。 */
function headlineOf(predictions: QuantPredictionsResponse): string {
  const items = [...predictions.predictions].sort(
    (left, right) => right.horizon_days - left.horizon_days,
  )
  const item = items.find((prediction) => prediction.headline) ?? items[0]
  if (!item) return '接口没有返回任何尺度的预测。'
  if (item.headline) return item.headline
  const direction =
    item.direction === 'up'
      ? '▲ 看涨'
      : item.direction === 'down'
        ? '▼ 看跌'
        : item.direction === 'flat'
          ? '＝ 持平'
          : '方向未发布'
  return `${item.horizon_days} 日尺度：${direction}，目标价 ${formatUsd(item.target_price)}`
}

/** 手动「重新抓取」的报告；与刷新失败是两件事，不互相顶替。 */
const refreshInfo = ref<{ success: boolean; message: string } | null>(null)
const horizon = ref('5')

const { data, loading, refreshing, error, load } = useAsyncBlock<QuantData>(
  async (refresh) => {
    if (refresh) {
      const result = await quantApi.refresh()
      refreshInfo.value = { success: result.success, message: result.message }
    }
    const [factors, predictions, accuracy, monitor] = await Promise.all([
      quantApi.getFactors(),
      quantApi.getPredictions(),
      quantApi.getAccuracy(),
      quantApi.getMonitor(),
    ])
    // 研究结果只喂前向裁决；它挂了不影响其余面板
    let research: QuantResearchResponse | null = null
    try {
      research = await quantApi.getResearch()
    } catch {
      research = null
    }
    return { factors, predictions, accuracy, monitor, research }
  },
  { fallback: '获取量化数据失败。', timeout: '抓取数据源耗时较长，请稍后重试。' },
)

void load()

useFreshnessBlock(
  'quant',
  '量化预测',
  computed(() => (loading.value ? 'pending' : error.value || !data.value ? 'unavailable' : 'fresh')),
  computed(() => data.value?.factors.as_of ?? data.value?.predictions.as_of ?? null),
)

const failedSources = computed(
  () => data.value?.factors.sources.filter((source) => source.status === 'error') ?? [],
)

/** 最长尺度的那条预测：结论行里的上行概率取自它。 */
const latest = computed(
  () =>
    [...(data.value?.predictions.predictions ?? [])].sort(
      (left, right) => right.horizon_days - left.horizon_days,
    )[0] ?? null,
)

const headline = computed(() => (data.value ? headlineOf(data.value.predictions) : ''))
</script>

<template>
  <SectionBlock
    id="quant"
    title="量化预测"
    intro="按 1 日 / 1 周 / 1 月 / 1 季 / 1 年五个尺度，用「货币政策与利率 / 避险与信用 / 供需结构 / 市场与技术面」四类因素合成校准后的方向、目标价与三情景；另给公允价分解、周更监测信号，以及走查式回测的命中率、CRPS 与前向裁决证据。"
  >
    <template #actions>
      <RefreshButton :busy="refreshing" label="重新抓取" @click="load(true)" />
    </template>

    <StateBlock v-if="loading" title="正在读取量化因子与预测…" test-id="quant-loading" />
    <StateBlock
      v-else-if="!data"
      kind="unavailable"
      :test-id="TESTIDS.quantUnavailable"
      title="量化数据不可用"
      :detail="error ?? '没能取到因子与预测。这里不显示任何内置数字。'"
    />

    <div v-else class="stack stack--lg">
      <p class="section__conclusion">
        <span :data-testid="field('predictions.model_version')">模型 {{ data.predictions.model_version }}</span> · 因子 <span :data-testid="field('quant.available_factors')">{{ data.factors.available_factors }}</span>/<span :data-testid="field('quant.total_factors')">{{ data.factors.total_factors }}</span> 可用（截至 <span :data-testid="field('predictions.as_of')">{{ displayStamp(data.predictions.as_of) ?? data.predictions.as_of ?? '—' }}</span>）· {{ headline }}<template v-if="latest && latest.probability_up !== null">（上行概率 {{ formatShare(latest.probability_up * 100, 0) }}）</template>
      </p>

      <p v-if="failedSources.length > 0" class="panel__error">
        数据源不可用：{{ failedSources.map((source) => `${source.label ?? source.name}（${source.error ?? '原因未知'}）`).join('；') }}
      </p>

      <p v-if="refreshInfo" :class="refreshInfo.success ? 'note' : 'panel__error'">
        <span :data-testid="field('quant.refresh.success')">重新抓取{{ refreshInfo.success ? '成功' : '失败' }}</span><span :data-testid="field('quant.refresh.message')">{{ refreshInfo.message }}</span>
      </p>

      <!-- 逐源状态收进一层折叠，不占主版面 -->
      <SourcesStatus :factors="data.factors" />

      <PanelBlock title="决策尺度">
        <ScaleTab
          v-model:horizon="horizon"
          panel-id-prefix="quant-scale"
          :predictions="data.predictions"
        />
      </PanelBlock>

      <PanelBlock title="公允价值分解">
        <FairValuePanel :decomposition="data.predictions.fair_value" />
      </PanelBlock>

      <PanelBlock title="监测信号（周更表）">
        <MonitorTable :monitor="data.monitor" />
      </PanelBlock>

      <PanelBlock title="回测评估">
        <AccuracyPanel
          v-model:horizon="horizon"
          panel-id-prefix="quant-accuracy"
          :accuracy="data.accuracy"
          :research="data.research"
        />
      </PanelBlock>

      <PanelBlock title="四类影响因素">
        <FactorTables :factors="data.factors" />
      </PanelBlock>

      <p v-if="error" class="panel__error">刷新失败：{{ error }}</p>
    </div>
  </SectionBlock>
</template>
