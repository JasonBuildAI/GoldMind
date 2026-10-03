<script setup lang="ts">
import { token } from '@/lib/tokens'
import { computed, ref } from 'vue'

import { areaPath, evenIndices, linePath, niceTicks, paddedDomain } from './geometry'

/**
 * 单序列面积图（金价走势）。
 *
 * 自绘 SVG 而不是引入图表库：这里只需要一条线 + 一层填充 + 一个悬停提示，
 * 换掉 recharts 省下的是整棵 React 依赖树。
 *
 * 刻意不做的事：末点不闪烁、不做入场动画、不加渐变 —— 图表是读数的工具，
 * 不是装饰。悬停提示只在鼠标进入时出现，属于「回应人的操作」。
 */
const props = withDefaults(
  defineProps<{
    points: readonly { date: string; value: number }[]
    label: string
    /** 纵轴与提示卡的数值格式 */
    formatValue: (value: number) => string
    height?: number
    /** 折线与填充色；不给时用设计令牌里的金价色（唯一强调色） */
    color?: string
  }>(),
  { height: 280, color: undefined },
)

const WIDTH = 960
const MARGIN = { top: 12, right: 16, bottom: 26, left: 68 }

const hoverIndex = ref<number | null>(null)

const values = computed(() => props.points.map((point) => point.value))
const domain = computed(() => paddedDomain(values.value))
const ticks = computed(() => niceTicks(domain.value, 4))

const innerWidth = computed(() => WIDTH - MARGIN.left - MARGIN.right)
const innerHeight = computed(() => props.height - MARGIN.top - MARGIN.bottom)
const baselineY = computed(() => MARGIN.top + innerHeight.value)

const xs = computed(() =>
  props.points.map((_, index) =>
    props.points.length === 1
      ? MARGIN.left + innerWidth.value / 2
      : MARGIN.left + (index / (props.points.length - 1)) * innerWidth.value,
  ),
)

function scaleY(value: number): number {
  const [min, max] = domain.value
  const span = max - min
  const ratio = span === 0 ? 0.5 : (value - min) / span
  return MARGIN.top + (1 - ratio) * innerHeight.value
}

const line = computed(() => linePath(values.value, scaleY, xs.value))
const area = computed(() => areaPath(values.value, scaleY, xs.value, baselineY.value))

/** 横轴标签：均匀取 6 个位置，标签只留 MM-DD。 */
const xLabels = computed(() =>
  evenIndices(props.points.length, 6).map((index) => ({
    index,
    x: xs.value[index],
    text: props.points[index]?.date.slice(5) ?? '',
  })),
)

const stroke = computed(() => props.color ?? token('--gold'))
const hovered = computed(() => (hoverIndex.value === null ? null : props.points[hoverIndex.value]))
const hoverX = computed(() =>
  hoverIndex.value === null ? 0 : (xs.value[hoverIndex.value] / WIDTH) * 100,
)

/** 鼠标位置 → 最近的数据点（按 x 距离，不要求落在点上）。 */
function onMove(event: MouseEvent): void {
  const target = event.currentTarget as SVGSVGElement
  const rect = target.getBoundingClientRect()
  if (rect.width === 0 || props.points.length === 0) return
  const svgX = ((event.clientX - rect.left) / rect.width) * WIDTH
  let best = 0
  let bestDistance = Number.POSITIVE_INFINITY
  xs.value.forEach((x, index) => {
    const distance = Math.abs(x - svgX)
    if (distance < bestDistance) {
      bestDistance = distance
      best = index
    }
  })
  hoverIndex.value = best
}
</script>

<template>
  <figure class="chart">
    <svg
      :viewBox="`0 0 ${WIDTH} ${height}`"
      role="img"
      :aria-label="`${label}走势图，共 ${points.length} 个数据点`"
      @mousemove="onMove"
      @mouseleave="hoverIndex = null"
    >
      <!-- 横向网格 + 纵轴刻度 -->
      <g>
        <template v-for="tick in ticks" :key="tick">
          <line
            class="chart__grid"
            :x1="MARGIN.left"
            :x2="WIDTH - MARGIN.right"
            :y1="scaleY(tick)"
            :y2="scaleY(tick)"
          />
          <text class="chart__axis" :x="MARGIN.left - 10" :y="scaleY(tick) + 4" text-anchor="end">
            {{ formatValue(tick) }}
          </text>
        </template>
      </g>

      <!-- 面积 + 折线 -->
      <path :d="area" :fill="stroke" fill-opacity="0.08" />
      <path class="chart__line" :d="line" :stroke="stroke" />

      <!-- 悬停：一条竖线 + 一个实心点，不做发光 -->
      <template v-if="hoverIndex !== null">
        <line
          class="chart__grid"
          :x1="xs[hoverIndex]"
          :x2="xs[hoverIndex]"
          :y1="MARGIN.top"
          :y2="baselineY"
        />
        <circle
          :cx="xs[hoverIndex]"
          :cy="scaleY(values[hoverIndex])"
          r="3.5"
          :fill="stroke"
          :stroke="token('--surface')"
          stroke-width="1.5"
        />
      </template>

      <!-- 横轴标签 -->
      <text
        v-for="item in xLabels"
        :key="item.index"
        class="chart__axis"
        :x="item.x"
        :y="height - 8"
        text-anchor="middle"
      >
        {{ item.text }}
      </text>
    </svg>

    <div v-if="hovered" class="chart-tip" :style="{ left: `${hoverX}%` }">
      <div class="chart-tip__row">
        <span>{{ label }}</span>
        <strong>{{ formatValue(hovered.value) }}</strong>
      </div>
      <div class="chart-tip__row">
        <span>{{ hovered.date }}</span>
      </div>
    </div>

    <figcaption v-if="$slots.caption" class="provenance">
      <slot name="caption" />
    </figcaption>
  </figure>
</template>
