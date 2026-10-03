<script setup lang="ts">
import type { Column } from '@/components/dataTable'
import DataTable from '@/components/DataTable.vue'
import StateBlock from '@/components/StateBlock.vue'
import type { QuantMonitorResponse, QuantMonitorRow } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

import {
  MONITOR_INFO_KEYS,
  SIGNAL_TEXT,
  formatChange,
  formatMonitorValue,
  statusLabel,
} from './shared'

/**
 * 监测仪表盘：方法论第七节的周更表。
 *
 * 按后端口径拆成两张表：参与信号（有确定性多空规则）与只看不评（信息型指标，
 * 只给数值不给方向）。每行给频率、来源、最新值与数据截至，取不到就说原因。
 *
 * 多空只能来自后端 monitor.py 的确定性规则 —— 界面不自己下判断，
 * 所以「只看不评」那一组哪怕数值再极端也只给数值与规则说明。
 */
const props = defineProps<{ monitor: QuantMonitorResponse }>()

const field = (path: string) => fieldTestId(path)

/** 参与信号的方向文字：signal 为 null 时退回后端给的 signal_label。 */
function signalText(signal: QuantMonitorRow['signal']): string | null {
  return signal === null ? null : SIGNAL_TEXT[signal]
}

const COLUMNS: ReadonlyArray<Column<QuantMonitorRow>> = [
  { key: 'name', header: '指标' },
  { key: 'frequency', header: '频率' },
  { key: 'source', header: '来源' },
  { key: 'value', header: '最新值', numeric: true },
  { key: 'change', header: '变化', numeric: true },
  { key: 'obs_date', header: '数据截至' },
  { key: 'signal', header: '信号' },
  { key: 'note', header: '说明' },
]

const participating = computed(() => props.monitor.rows.filter((row) => !MONITOR_INFO_KEYS.has(row.key)))
const infoOnly = computed(() => props.monitor.rows.filter((row) => MONITOR_INFO_KEYS.has(row.key)))

const bullish = computed(() => participating.value.filter((row) => row.signal === 'bull').length)
const bearish = computed(() => participating.value.filter((row) => row.signal === 'bear').length)
const neutral = computed(() => participating.value.length - bullish.value - bearish.value)

/** 两张表只差标题与文案，合成一组渲染，避免同一套列插槽写两遍。 */
const groups = computed(() => [
  {
    key: 'participating',
    heading: '参与信号（有确定性多空规则）',
    testId: TESTIDS.quantMonitorParticipating,
    intro:
      '信号只来自后端 monitor.py 的确定性规则；数据截至一列是每个指标的观测日 —— 值越旧，越要打折看。看涨 / 看跌同时给 ▲▼ 与文字，颜色只是加强。',
    rows: participating.value,
    empty: '没有参与信号的指标。',
  },
  {
    key: 'info-only',
    heading: '只看不评（信息型指标）',
    testId: TESTIDS.quantMonitorInfoOnly,
    intro:
      '这些指标只给数值与观测日，不给多空判断 —— 它们在历史样本上没有通过筛选闸门，给方向就是编造。',
    rows: infoOnly.value,
    empty: '没有信息型指标。',
  },
])

/** 取不到值的行在两张表下面逐条说明原因，不让读者回头猜。 */
const unavailableNotes = computed(() =>
  props.monitor.rows.filter((row) => row.status !== 'ok' && row.reason),
)
</script>

<template>
  <StateBlock
    v-if="monitor.rows.length === 0"
    kind="unavailable"
    test-id="quant-monitor-unavailable"
    title="监测仪表盘不可用"
    detail="接口没有返回任何监测行。"
  />

  <div v-else class="stack stack--lg" :data-testid="TESTIDS.quantMonitorTable">
    <p class="section__conclusion">
      参与信号 {{ participating.length }} 项（看涨 {{ bullish }} · 看跌 {{ bearish }} · 中性 / 样本不足 {{ neutral }}）； 只看不评 {{ infoOnly.length }} 项（信息型指标不给方向）。 <span class="note" :data-testid="field('monitor.as_of')">全部指标中最新观测日：{{ monitor.as_of ?? '—' }}。</span>
    </p>

    <div v-for="group in groups" :key="group.key">
      <h4 :data-testid="group.testId">{{ group.heading }}</h4>
      <p class="note">{{ group.intro }}</p>
      <DataTable
        :rows="group.rows"
        :columns="COLUMNS"
        :row-key="(row) => row.key"
        :test-id="`${group.testId}-table`"
        :empty="group.empty"
      >
        <template #name="{ row }">
          <span :data-testid="field('monitor.name')">{{ row.name }}</span><span class="note" :data-testid="field('monitor.key')">{{ row.key }}</span>
        </template>
        <template #frequency="{ row }">
          <span :data-testid="field('monitor.frequency')">{{ row.frequency }}</span>
        </template>
        <template #source="{ row }">
          <span :data-testid="field('monitor.source')">{{ row.source }}</span>
        </template>
        <template #value="{ row }">
          <span :data-testid="field('monitor.value')">{{ row.value === null ? '—' : formatMonitorValue(row.value) }}<span class="note" :data-testid="field('monitor.unit')">{{ row.unit }}</span></span>
        </template>
        <template #change="{ row }">
          <span :data-testid="field('monitor.change')">{{ row.change === null ? '—' : formatChange(row.change) }}</span>
        </template>
        <template #obs_date="{ row }">
          <span :data-testid="field('monitor.obs_date')">{{ row.obs_date ?? '—' }}</span>
        </template>
        <template #signal="{ row }">
          <span v-if="row.status !== 'ok'" class="tag" :data-testid="field('monitor.status')">{{ statusLabel(row.status) }}</span>
          <span v-else-if="signalText(row.signal) === null" class="note" :data-testid="field('monitor.signal_label')">{{ row.signal_label }}</span>
          <span v-else :class="row.signal === 'bull' ? 'is-up' : row.signal === 'bear' ? 'is-down' : ''" :data-testid="field('monitor.signal')">{{ signalText(row.signal) }}</span>
        </template>
        <template #note="{ row }">
          <span class="note" :data-testid="field('monitor.note')">{{ row.note }}</span><span v-if="row.reason" class="note" :data-testid="`quant-monitor-reason-${row.key}`">（<span :data-testid="field('monitor.reason')">{{ row.reason }}</span>）</span>
        </template>
      </DataTable>
    </div>

    <p v-for="row in unavailableNotes" :key="`${row.key}-unavailable`" class="note">
      {{ row.name }}：{{ row.reason }}
    </p>
  </div>
</template>
