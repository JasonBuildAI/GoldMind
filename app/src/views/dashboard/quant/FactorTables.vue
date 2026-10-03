<script setup lang="ts">
import type { Column } from '@/components/dataTable'
import DataTable from '@/components/DataTable.vue'
import { displayStamp, formatPercent } from '@/lib/format'
import type {
  QuantFactorCoverage,
  QuantFactorSnapshot,
  QuantFactorsResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

import { statusLabel } from './shared'

/**
 * 四类影响因素面板：面板头先给模型与因子总数，再逐类给出逐因子表。
 *
 * 「发布滞后」是口径说明（统计期末到公开发布通常滞后几天），不是延迟。
 * 覆盖画像把「缺口年」与「积累期」分开报告 —— 新序列允许先入库积累，
 * 不能被当成缺口；逐年观测数收进一层折叠，不占版面。
 */
const props = defineProps<{ factors: QuantFactorsResponse }>()

const field = (path: string) => fieldTestId(path)

/** 逐年观测数：`2016: 249、2017: 1、2026: 188`。 */
function yearEntries(coverage: QuantFactorCoverage): string {
  return coverage.years.map((year) => `${year}: ${coverage.year_counts[String(year)] ?? 0}`).join('、')
}

const FACTOR_COLUMNS: ReadonlyArray<Column<QuantFactorSnapshot>> = [
  { key: 'name', header: '因子' },
  { key: 'category', header: '类别' },
  { key: 'weight', header: '权重 / 方向', numeric: true },
  { key: 'value', header: '最新值', numeric: true },
  { key: 'obs_date', header: '数据截至' },
  { key: 'publication_lag', header: '发布滞后', numeric: true, source: '统计期末 → 公开发布' },
  { key: 'z', header: 'z', numeric: true },
  { key: 'contribution', header: '贡献', numeric: true },
  { key: 'status', header: '状态' },
  { key: 'source', header: '来源' },
]

/** 每一类的因子行；空类也保留表头与空态说明，不隐藏字段。 */
const groups = computed(() =>
  props.factors.categories.map((category) => ({
    category,
    rows: props.factors.factors.filter((factor) => factor.category === category.key),
  })),
)
</script>

<template>
  <div class="stack stack--lg" :data-testid="TESTIDS.quantFactorTable">
    <p class="panel__meta">
      <span :data-testid="field('quant.model_version')">模型 {{ factors.model_version }}</span>
      <span :data-testid="field('quant.as_of')">因子数据截至 {{ displayStamp(factors.as_of) ?? factors.as_of ?? '—' }}</span>
      <span>可用 <span :data-testid="field('quant.available_factors')">{{ factors.available_factors }}</span> / <span :data-testid="field('quant.total_factors')">{{ factors.total_factors }}</span> 个因子</span>
      <span :data-testid="field('quant.unavailable_reason')">不可用原因：{{ factors.unavailable_reason ?? '无' }}</span>
    </p>

    <div v-for="group in groups" :key="group.category.key">
      <h4>{{ group.category.name }}<span class="note" :data-testid="field('quant.category.key')">{{ group.category.key }}</span></h4>
      <p class="note">
        <span :data-testid="field('quant.category.name')">{{ group.category.name }}</span>：<span :data-testid="field('quant.category.available')">{{ group.category.available }}</span> / <span :data-testid="field('quant.category.total')">{{ group.category.total }}</span> 个因子可用。
      </p>
      <DataTable
        :rows="group.rows"
        :columns="FACTOR_COLUMNS"
        :row-key="(factor) => factor.key"
        empty="这一类没有因子。"
      >
        <template #name="{ row }">
          <span :data-testid="field('quant.factors.name')">{{ row.name }}</span><span class="note" :data-testid="field('quant.factors.key')">{{ row.key }}</span><span class="note" :data-testid="field('quant.factors.description')">{{ row.description }}</span>
          <div v-if="row.coverage" class="note" :data-testid="field('quant.factors.coverage')">
            <span>覆盖 <span :data-testid="field('quant.factors.coverage.first_date')">{{ row.coverage.first_date ?? '—' }}</span> — <span :data-testid="field('quant.factors.coverage.last_date')">{{ row.coverage.last_date ?? '—' }}</span> · <span :data-testid="field('quant.factors.coverage.observations')">{{ row.coverage.observations }}</span> 条 · <span :data-testid="field('quant.factors.coverage.years')">{{ row.coverage.years.length }}</span> 年</span>
            <span v-if="row.coverage.accumulating" class="tag" :data-testid="field('quant.factors.coverage.accumulating')">积累期（序列尚短，非缺口）</span>
            <span v-if="row.coverage.sparse_years.length > 0" class="panel__error" :data-testid="field('quant.factors.coverage.sparse_years')">缺口年：{{ row.coverage.sparse_years.join('、') }}</span>
            <details class="row-details">
              <summary>逐年观测数（{{ row.coverage.years.length }} 年）</summary>
              <span :data-testid="field('quant.factors.coverage.year_counts')">{{ yearEntries(row.coverage) }}</span>
            </details>
          </div>
          <span v-else class="note" :data-testid="field('quant.factors.coverage')">覆盖信息未提供（序列为空时后端不下发）</span>
        </template>
        <template #category="{ row }">
          <span :data-testid="field('quant.factors.category_name')">{{ row.category_name }}</span><span class="note" :data-testid="field('quant.factors.category')">{{ row.category }}</span>
        </template>
        <template #weight="{ row }">
          <span :data-testid="field('quant.factors.weight')">{{ row.weight }}</span><span class="note" :data-testid="field('quant.factors.sign')">{{ row.sign > 0 ? '上升利多' : '上升利空' }}</span>
        </template>
        <template #value="{ row }">
          <span :data-testid="field('quant.factors.value')">{{ row.value === null ? '—' : row.value.toFixed(2) }}</span><span class="note" :data-testid="field('quant.factors.unit')">{{ row.unit }}</span>
        </template>
        <template #obs_date="{ row }">
          <span :data-testid="field('quant.factors.obs_date')">{{ row.obs_date ?? '—' }}</span><span class="note" :data-testid="field('quant.factors.age_days')">{{ row.age_days === null ? '滞后未知' : `${row.age_days} 天前` }} / 上限 <span :data-testid="field('quant.factors.max_age_days')">{{ row.max_age_days }}</span> 天</span>
        </template>
        <template #publication_lag="{ row }">
          <span :data-testid="field('quant.factors.publication_lag_days')">{{ row.publication_lag_days }} 天</span>
        </template>
        <template #z="{ row }">
          <span :data-testid="field('quant.factors.z')">{{ row.z === null ? '—' : row.z.toFixed(2) }}</span><span class="note" :data-testid="field('quant.factors.signed_z')">对齐后 {{ row.signed_z === null ? '—' : row.signed_z.toFixed(2) }}</span>
        </template>
        <template #contribution="{ row }">
          <span :data-testid="field('quant.factors.contribution')">{{ row.contribution === null ? '—' : formatPercent(row.contribution * 100, 2) }}</span>
        </template>
        <template #status="{ row }">
          <span :data-testid="field('quant.factors.status')">{{ statusLabel(row.status) }}</span><span v-if="row.status !== 'ok'" class="tag">{{ statusLabel(row.status) }}</span><span class="note" :data-testid="field('quant.factors.reason')">{{ row.reason ?? '—' }}</span>
        </template>
        <template #source="{ row }">
          <span :data-testid="field('quant.factors.source')">{{ row.source }}</span>
        </template>
      </DataTable>
    </div>
  </div>
</template>
