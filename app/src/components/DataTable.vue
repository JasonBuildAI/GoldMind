<script setup lang="ts" generic="Row">
import { computed } from 'vue'

import { cellText, type Column } from './dataTable'

/**
 * 数字进表格的统一容器：所有数字表格从这里出，避免每个区块各写一套表结构。
 *
 * 数字列由 `numeric` 统一右对齐（tabular-nums）；来源列收在表头小字里。
 * 单元格内容优先取同名具名插槽（可放链接、标签、折叠），否则用 `render`；
 * 两者都没有时按字段名从行对象里取。
 */
const props = defineProps<{
  rows: readonly Row[]
  columns: ReadonlyArray<Column<Row>>
  rowKey: (row: Row, index: number) => string
  caption?: string
  testId?: string
  /** 没有数据时的说明；不传表示不渲染空态行 */
  empty?: string
}>()

const byKey = computed(
  () => new Map(props.columns.map((column) => [column.key, column])) as Map<string, Column<Row>>,
)

/** 插槽优先 → render → 行对象同名字段；空值统一显示「—」。 */
function valueOf(row: Row, key: string, index: number): string {
  const column = byKey.value.get(key)
  if (column?.render) return cellText(column.render(row, index))
  return cellText((row as Record<string, unknown>)[key] as string | number | null | undefined)
}
</script>

<template>
  <div class="table-scroll">
    <table class="data-table" :data-testid="testId">
      <caption v-if="caption" class="note">
        {{ caption }}
      </caption>
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key" scope="col" :class="{ num: column.numeric }">
            {{ column.header }}
            <span v-if="column.source" class="data-table__source">{{ column.source }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="rows.length === 0 && empty !== undefined">
          <td :colspan="columns.length" class="note">{{ empty }}</td>
        </tr>
        <tr v-for="(row, index) in rows" :key="rowKey(row, index)">
          <td v-for="column in columns" :key="column.key" :class="{ num: column.numeric }">
            <slot :name="column.key" :row="row" :index="index">
              {{ valueOf(row, column.key, index) }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.data-table__source {
  display: block;
  margin-top: 2px;
  font-size: var(--text-2xs);
  font-weight: 400;
  color: var(--text-secondary);
  white-space: normal;
}
</style>
