<script setup lang="ts">
import SectionBlock from '@/components/SectionBlock.vue'
import { TESTIDS } from '@/testids'

import InstitutionsPanel from './InstitutionsPanel.vue'
import FactorColumns from './FactorColumns.vue'

/**
 * 驱动：看涨 / 看跌因素与机构观点 —— 模型对当天事实的解读集中在这一节。
 *
 * 消息（当天的原始事实）2026-10-03 起独立成「消息」一节，侧边栏有独立入口；
 * 这里不再重复放一份（同一内容两个入口会让「去哪找消息」反而变模糊）。
 */
</script>

<template>
  <SectionBlock
    id="drivers"
    title="驱动"
    intro="看涨与看跌因素的逐条论据，以及四家机构最近一次可核实的目标价 —— 每条证据都带来源与数据截至；取不到的一路只影响自己。"
  >
    <div class="stack stack--lg" :data-testid="TESTIDS.sectionDrivers">
      <FactorColumns />
      <InstitutionsPanel />
    </div>
  </SectionBlock>
</template>
