<script setup lang="ts">
import { formatPercent, trendOf } from '@/lib/format'

/**
 * 一条报价：名称、数值、涨跌与来源。
 *
 * 涨跌同时给符号（▲▼）与文字（涨/跌），颜色只是加强 —— 不让颜色单独承载语义。
 * 数值用等宽数字（tabular-nums），避免数字跳动时整行抖动。
 */
const props = defineProps<{
  label: string
  value: string
  change?: number
  changeNote?: string
  meta?: string
  title?: string
  compact?: boolean
}>()

const trend = () => (props.change === undefined ? null : trendOf(props.change))
</script>

<template>
  <div :class="['quote', { 'quote--compact': compact }]" :title="title">
    <div class="quote__label">{{ label }}</div>
    <div class="quote__value">{{ value }}</div>
    <div
      v-if="trend() && change !== undefined"
      :class="[
        'quote__change',
        change > 0 ? 'is-up' : change < 0 ? 'is-down' : '',
      ]"
    >
      <span aria-hidden="true">{{ trend()!.symbol }}</span> {{ formatPercent(change) }}
      <span>（{{ trend()!.label }}{{ changeNote ? `，${changeNote}` : '' }}）</span>
    </div>
    <!--
      `meta` 是字符串，但金价那一路要挂字段级选择器（`GoldPriceAsOf` 组件）——
      所以留一个同名插槽：两条路都走同一个位置，不会出现「有的报价有时间、有的没有」。
    -->
    <div v-if="meta || $slots.meta" class="quote__meta">
      <slot name="meta">{{ meta }}</slot>
    </div>
  </div>
</template>
