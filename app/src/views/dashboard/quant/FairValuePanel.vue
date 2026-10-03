<script setup lang="ts">
import type { Column } from '@/components/dataTable'
import DataTable from '@/components/DataTable.vue'
import GoldPriceAsOf from '@/components/GoldPriceAsOf.vue'
import StateBlock from '@/components/StateBlock.vue'
import { displayStamp, formatPercent, formatShare, formatUsd } from '@/lib/format'
import type { QuantDecomposition, QuantDecompositionBlock } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

import { num } from './shared'

/**
 * 公允价分解：把市场价拆成宏观锚、需求溢价、风险溢价与情绪残差。
 *
 * 一行结论 + 关键数字在最上；四块构成与驱动因子进表格，数字都由后端给出 ——
 * 回归样本或回归量不足时只给原因，不摆一个编出来的公允价。
 */
defineProps<{ decomposition: QuantDecomposition }>()

const field = (path: string) => fieldTestId(path)

/** 单元格结构写在模板的同名插槽里（驱动列是一个小列表），这里只给列定义。 */
const COLUMNS: ReadonlyArray<Column<QuantDecompositionBlock>> = [
  { key: 'name', header: '分块' },
  { key: 'usd', header: '美元', numeric: true },
  { key: 'share', header: '占比', numeric: true },
  { key: 'drivers', header: '驱动' },
]
</script>

<template>
  <StateBlock
    v-if="decomposition.status !== 'ok'"
    kind="unavailable"
    test-id="quant-fair-value-unavailable"
    title="公允价值分解不可用"
    :detail="
      decomposition.reason ??
      '回归样本或回归量不足。这里不显示编出来的公允价 —— 宁可只给市场价。'
    "
  />

  <div v-else class="stack stack--lg" :data-testid="TESTIDS.quantFairValue">
    <p class="section__conclusion">
      市场价 <span class="num">{{ formatUsd(decomposition.market_price) }}</span>
      <!-- 这个市场价就是量化基准（gold_close 最后一点）：它的截至日必须跟着它 -->
      <GoldPriceAsOf
        :as-of="decomposition.as_of"
        :basis-label="decomposition.basis_label"
        as-of-field="fair_value.market_price_as_of"
      />
      ，公允价 <span class="num">{{ formatUsd(decomposition.fair_value) }}</span>，偏离 <span :data-testid="field('fair_value.deviation_pct')">{{ decomposition.deviation_pct === null ? '—' : formatPercent(decomposition.deviation_pct * 100) }}</span>；回归样本 <span :data-testid="field('fair_value.samples')">{{ decomposition.samples }}</span> 个， 拟合 R² <span :data-testid="field('fair_value.r2')">{{ num(decomposition.r2) }}</span>。
    </p>

    <dl class="metrics">
      <div>
        <dt>市场价</dt>
        <dd class="num" :data-testid="field('fair_value.market_price')">
          {{ formatUsd(decomposition.market_price) }}
        </dd>
      </div>
      <div>
        <dt>公允价</dt>
        <dd class="num" :data-testid="field('fair_value.fair_value')">
          {{ formatUsd(decomposition.fair_value) }}
        </dd>
      </div>
      <div>
        <dt>偏离度</dt>
        <dd :data-testid="field('fair_value.deviation_pct')">
          {{ decomposition.deviation_pct === null ? '—' : formatPercent(decomposition.deviation_pct * 100) }}
        </dd>
      </div>
      <div>
        <dt>拟合 R²</dt>
        <dd :data-testid="field('fair_value.r2')">{{ num(decomposition.r2) }}</dd>
      </div>
      <div>
        <dt>口径</dt>
        <dd>
          <span :data-testid="field('fair_value.basis_label')">{{ decomposition.basis_label }}</span><span class="note" :data-testid="field('fair_value.basis')">{{ decomposition.basis }}</span>
        </dd>
      </div>
      <div>
        <dt>数据截至</dt>
        <dd :data-testid="field('fair_value.as_of')">{{ displayStamp(decomposition.as_of) ?? '—' }}</dd>
      </div>
      <div>
        <dt>状态</dt>
        <dd :data-testid="field('fair_value.status')">{{ decomposition.status }}</dd>
      </div>
      <div>
        <dt>回归样本</dt>
        <dd :data-testid="field('fair_value.samples')">{{ decomposition.samples }}</dd>
      </div>
      <div>
        <dt>不可用原因</dt>
        <dd :data-testid="field('fair_value.reason')">{{ decomposition.reason ?? '—' }}</dd>
      </div>
    </dl>

    <DataTable
      :rows="decomposition.blocks"
      :columns="COLUMNS"
      :row-key="(block) => block.key"
      caption="四块之和恒等于市场价：中枢 + 需求溢价 + 风险溢价 + 情绪残差（残差走阔 = 模型外因素在定价）。驱动列给出该块的回归量及其对数贡献。"
    >
      <template #name="{ row }">
        <span :data-testid="field('fair_value.blocks.name')">{{ row.name }}</span><span class="note" :data-testid="field('fair_value.blocks.key')">{{ row.key }}</span>
      </template>
      <template #usd="{ row }">
        <span :data-testid="field('fair_value.blocks.usd')">{{ formatUsd(row.usd) }}</span>
      </template>
      <template #share="{ row }">
        <span :data-testid="field('fair_value.blocks.share_pct')">{{ row.share_pct === null ? '—' : formatShare(row.share_pct, 1) }}</span>
      </template>
      <template #drivers="{ row }">
        <template v-if="row.drivers.length === 0">—</template>
        <ul v-else class="point-list">
          <li v-for="driver in row.drivers" :key="driver.key">
            <span :data-testid="field('fair_value.blocks.drivers.name')">{{ driver.name }}</span><span class="note" :data-testid="field('fair_value.blocks.drivers.key')">{{ driver.key }}</span><span class="num" :data-testid="field('fair_value.blocks.drivers.log_contribution')">{{ num(driver.log_contribution) }}</span>
          </li>
        </ul>
      </template>
    </DataTable>
  </div>
</template>
