<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import type { Column } from '@/components/dataTable'
import PanelBlock from '@/components/PanelBlock.vue'
import StateBlock from '@/components/StateBlock.vue'
import { displayStamp } from '@/lib/format'
import type { FetchSourceStatus, SourcesStatusResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

import { text } from './fields'

/**
 * 数据源可用性：每个渠道最近一次抓取尝试的状态、时间与条目数。
 *
 * 失败行给出错误原文，不吞掉；缺值显示「—」，不用 0 顶替。
 */
const props = defineProps<{
  sources: SourcesStatusResponse | null
  error: string | null
}>()

const field = (path: string) => fieldTestId(path)

/** 数字列交给 DataTable 统一右对齐（tabular-nums），这里只声明列。 */
const COLUMNS: ReadonlyArray<Column<FetchSourceStatus>> = [
  { key: 'channel', header: '渠道' },
  { key: 'source_key', header: '来源代号' },
  { key: 'status', header: '状态' },
  { key: 'stale', header: '陈旧', numeric: true },
  { key: 'age_hours', header: '数据年龄（小时）', numeric: true },
  { key: 'started_at', header: '开始' },
  { key: 'finished_at', header: '完成' },
  { key: 'items', header: '条目', numeric: true },
  { key: 'error', header: '错误' },
]

const rows = computed(() => props.sources?.sources ?? [])
const rowKey = (row: FetchSourceStatus) => `${row.channel}-${row.source_key}`
</script>

<template>
  <PanelBlock title="数据源可用性" :test-id="TESTIDS.dataSourcesStatus">
    <StateBlock
      v-if="!sources"
      kind="unavailable"
      title="数据源状态不可用"
      test-id="data-sources-unavailable"
      :detail="error ?? '接口没有返回数据源状态。'"
    />

    <div v-else class="stack">
      <p class="section__conclusion">
        共 {{ sources.summary.total }} 个渠道：可用 {{ sources.summary.ok }} · 无数据 {{ sources.summary.empty }} · 不可用 {{ sources.summary.error }} · 本轮跳过 {{ sources.summary.skipped }} · 陈旧 {{ sources.summary.stale }}；状态生成于
        <span :data-testid="field('sources.generated_at')">{{ displayStamp(sources.generated_at) ?? '—' }}</span>。
      </p>

      <p class="panel__meta">
        <span :data-testid="field('sources.summary.total')">总数 {{ sources.summary.total }}</span>
        <span :data-testid="field('sources.summary.ok')">可用 {{ sources.summary.ok }}</span>
        <span :data-testid="field('sources.summary.empty')">无数据 {{ sources.summary.empty }}</span>
        <span :data-testid="field('sources.summary.error')">不可用 {{ sources.summary.error }}</span>
        <span :data-testid="field('sources.summary.skipped')">跳过 {{ sources.summary.skipped }}</span>
        <span :data-testid="field('sources.summary.stale')">陈旧 {{ sources.summary.stale }}</span>
      </p>

      <DataTable
        :rows="rows"
        :columns="COLUMNS"
        :row-key="rowKey"
        caption="每行是一个渠道最近一次抓取尝试：来源代号、状态、是否陈旧、数据年龄与条目数；failed 行给出错误原文，不吞掉。"
      >
        <template #channel="{ row }">
          <span :data-testid="field('sources.rows.channel_label')">{{ row.channel_label }}</span><span class="note" :data-testid="field('sources.rows.channel')">{{ row.channel }}</span>
        </template>
        <template #source_key="{ row }">
          <span class="note" :data-testid="field('sources.rows.source_key')">{{ row.source_key }}</span>
        </template>
        <template #status="{ row }">
          <span :data-testid="field('sources.rows.status_label')">{{ row.status_label }}</span><span class="note" :data-testid="field('sources.rows.status')">{{ row.status }}</span>
        </template>
        <template #stale="{ row }">
          <span :data-testid="field('sources.rows.stale')">{{ row.stale ? '是' : '否' }}</span>
        </template>
        <template #age_hours="{ row }">
          <span :data-testid="field('sources.rows.age_hours')">{{ text(row.age_hours) }}</span>
        </template>
        <template #started_at="{ row }">
          <span :data-testid="field('sources.rows.started_at')">{{ displayStamp(row.started_at) ?? '—' }}</span>
        </template>
        <template #finished_at="{ row }">
          <span :data-testid="field('sources.rows.finished_at')">{{ displayStamp(row.finished_at) ?? '—' }}</span>
        </template>
        <template #items="{ row }">
          <span :data-testid="field('sources.rows.items')">{{ text(row.items) }}</span>
        </template>
        <template #error="{ row }">
          <span class="note" :data-testid="field('sources.rows.error')">{{ row.error ?? '—' }}</span>
        </template>
      </DataTable>
    </div>
  </PanelBlock>
</template>
