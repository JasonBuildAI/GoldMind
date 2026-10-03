<script setup lang="ts">
import SectionBlock from '@/components/SectionBlock.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useAsyncBlock } from '@/composables/useAsyncBlock'
import {
  healthApi,
  quantApi,
  sourcesApi,
  type HealthResponse,
  type QuantFactorsResponse,
  type SourcesStatusResponse,
} from '@/services/api'
import { computed } from 'vue'

import BootstrapPanel from './data/BootstrapPanel.vue'
import ConfigWatchPanel from './data/ConfigWatchPanel.vue'
import LegendPanel from './data/LegendPanel.vue'
import ServicesPanel from './data/ServicesPanel.vue'
import SourcesStatusPanel from './data/SourcesStatusPanel.vue'
import SyncReportPanel from './data/SyncReportPanel.vue'

/**
 * 数据与方法：同步报告、数据源可用性、初始化进度、配置与热加载、服务状态与口径说明。
 *
 * 三路取数各自独立 —— 数据源状态、因子接口的 sync 字段与 /health，谁挂了只影响
 * 自己那一块。这一节只陈述事实与口径，不产生任何新数字；密钥只以「是否配置」
 * 出现，不展示值。
 */
const {
  data: sources,
  loading: sourcesLoading,
  error: sourcesError,
  load: loadSources,
} = useAsyncBlock<SourcesStatusResponse>(() => sourcesApi.getStatus(), {
  fallback: '获取数据源状态失败。',
})

/**
 * 因子接口只用来读 sync：逐源明细在「量化预测 → 数据源状态」，这里不重复整张表。
 * 接口挂了就没有报告可看，错误文案不进页面 —— 面板自己会说「因子接口没有返回」。
 */
const { data: factors, loading: factorsLoading, load: loadFactors } =
  useAsyncBlock<QuantFactorsResponse>(() => quantApi.getFactors(), {
    fallback: '获取量化因子失败。',
  })

const {
  data: health,
  loading: healthLoading,
  error: healthError,
  load: loadHealth,
} = useAsyncBlock<HealthResponse>(() => healthApi.getHealth(), { fallback: '获取 /health 失败。' })

void loadSources()
void loadFactors()
void loadHealth()

/** 三路都落定才算读完：任何一路还在读时先给「正在读取」，不半截显示。 */
const loading = computed(() => sourcesLoading.value || factorsLoading.value || healthLoading.value)

/** 读取中与读取完的说明不同：前者说会看到什么，后者说这一节的口径。 */
const intro = computed(() =>
  loading.value
    ? '数据源可用性、初始化进度、同步报告与口径说明。'
    : '这一节陈述数据从哪里来、什么时候更新、哪些渠道不可用，以及页面上各种口径标签的含义；它不产生新数字。',
)
</script>

<template>
  <SectionBlock id="data-methods" title="数据与方法" :intro="intro">
    <StateBlock v-if="loading" title="正在读取数据源与方法说明…" test-id="data-methods-loading" />

    <div v-else class="stack stack--lg">
      <SyncReportPanel :factors="factors" />
      <SourcesStatusPanel :sources="sources" :error="sourcesError" />
      <BootstrapPanel :health="health" :error="healthError" />
      <ConfigWatchPanel :health="health" />
      <ServicesPanel :health="health" />
      <LegendPanel />
    </div>
  </SectionBlock>
</template>
