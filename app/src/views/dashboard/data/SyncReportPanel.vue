<script setup lang="ts">
import PanelBlock from '@/components/PanelBlock.vue'
import { displayStamp } from '@/lib/format'
import type { QuantFactorsResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

/**
 * 同步报告：本轮量化同步的起止时间、正常源数与因子的可用情况。
 *
 * 逐源明细（含「未到期」等逐源状态）在「量化预测 → 数据源状态」，这里只给一行
 * 结论，不重复整张表；因子接口没返回时如实说不可用，不摆一个空的进度条。
 */
defineProps<{ factors: QuantFactorsResponse | null }>()

const field = (path: string) => fieldTestId(path)
</script>

<template>
  <PanelBlock title="同步报告" :test-id="TESTIDS.dataSync">
    <p v-if="factors" class="section__conclusion">
      同步完成
      <span :data-testid="field('quant.sync.finished_at')">{{ displayStamp(factors.sync.finished_at) ?? '—' }}</span>；本轮开始
      <span :data-testid="field('quant.sync.started_at')">{{ displayStamp(factors.sync.started_at) ?? '—' }}</span>；正常源
      <span :data-testid="field('quant.sync.sources_ok')">{{ factors.sync.sources_ok ?? '—' }}</span>/<span :data-testid="field('quant.sync.sources_total')">{{ factors.sync.sources_total ?? '—' }}</span>；因子数据截至 {{ factors.as_of ?? '—' }}，可用 {{ factors.available_factors }}/{{ factors.total_factors }}。逐源明细在「量化预测 → 数据源状态」。
    </p>

    <p v-else class="note">量化同步报告不可用（因子接口没有返回）。</p>
  </PanelBlock>
</template>
