<script setup lang="ts">
import { token } from '@/lib/tokens'
import { computed, ref } from 'vue'

import { evenIndices, linePath, niceTicks, paddedDomain } from './geometry'

/**
 * 双轴折线图：金价（左轴）与美元指数（右轴）对照。
 *
 * 两条序列量纲差一个数量级，共用一根轴会让其中一条压成直线 —— 所以左右各一根，
 * 并在图例与说明里写明哪条在哪根轴上。美元指数用虚线，避免只靠颜色区分
 * （色觉障碍读者也要能分清）。
 */
const props = withDefaults(
  defineProps<{
    points: readonly { date: string; left: number; right: number }[]
    leftLabel: string
    rightLabel: string
    formatLeft: (value: number) => string
    formatRight: (value: number) => string
    height?: number
  }>(),
  { height: 280 },
)

const WIDTH = 960
const MARGIN = { top: 12, right: 60, bottom: 26, left: 68 }

const hoverIndex = ref<number | null>(null)

const leftValues = computed(() => props.points.map((point) => point.left))
const rightValues = computed(() => props.points.map((point) => point.right))
const leftDomain = computed(() => paddedDomain(leftValues.value))
const rightDomain = computed(() => paddedDomain(rightValues.value))
const leftTicks = computed(() => niceTicks(leftDomain.value, 4))
const rightTicks = computed(() => niceTicks(rightDomain.value, 4))

const innerWidth = computed(() => WIDTH - MARGIN.left - MARGIN.right)
const innerHeight = computed(() => props.height - MARGIN.top - MARGIN.bottom)
const rightAxisX = computed(() => WIDTH - MARGIN.right)

const xs = computed(() =>
  props.points.map((_, index) =>
    props.points.length === 1
      ? MARGIN.left + innerWidth.value / 2
      : MARGIN.left + (index / (props.points.length - 1)) * innerWidth.value,
  ),
)

function scaleWith(domain: readonly [number, number]) {
  return (value: number): number => {
    const span = domain[1] - domain[0]
    const ratio = span === 0 ? 0.5 : (value - domain[0]) / span
    return MARGIN.top + (1 - ratio) * innerHeight.value
  }
}

const leftScale = computed(() => scaleWith(leftDomain.value))
const rightScale = computed(() => scaleWith(rightDomain.value))

const leftPath = computed(() => linePath(leftValues.value, leftScale.value, xs.value))
const rightPath = computed(() => linePath(rightValues.value, rightScale.value, xs.value))

const xLabels = computed(() =>
  evenIndices(props.points.length, 6).map((index) => ({
    index,
    x: xs.value[index],
    text: props.points[index]?.date.slice(5) ?? '',
  })),
)

const goldStroke = token('--gold')
const dollarStroke = token('--text')

const hovered = computed(() => (hoverIndex.value === null ? null : props.points[hoverIndex.value]))
const hoverX = computed(() =>
  hoverIndex.value === null ? 0 : (xs.value[hoverIndex.value] / WIDTH) * 100,
)

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
    <div class="chart__legend">
      <span><i class="chart__swatch" :style="{ background: goldStroke }" />{{ leftLabel }}（左轴）</span>
      <span>
        <i class="chart__swatch chart__swatch--dashed" :style="{ background: dollarStroke }" />{{
          rightLabel
        }}（右轴，虚线）
      </span>
    </div>

    <svg
      :viewBox="`0 0 ${WIDTH} ${height}`"
      role="img"
      :aria-label="`${leftLabel}与${rightLabel}对照图，共 ${points.length} 个数据点`"
      @mousemove="onMove"
      @mouseleave="hoverIndex = null"
    >
      <g>
        <template v-for="tick in leftTicks" :key="`l-${tick}`">
          <line
            class="chart__grid"
            :x1="MARGIN.left"
            :x2="rightAxisX"
            :y1="leftScale(tick)"
            :y2="leftScale(tick)"
          />
          <text class="chart__axis" :x="MARGIN.left - 10" :y="leftScale(tick) + 4" text-anchor="end">
            {{ formatLeft(tick) }}
          </text>
        </template>
        <template v-for="tick in rightTicks" :key="`r-${tick}`">
          <text class="chart__axis" :x="rightAxisX + 10" :y="rightScale(tick) + 4" text-anchor="start">
            {{ formatRight(tick) }}
          </text>
        </template>
      </g>

      <path class="chart__line" :d="leftPath" :stroke="goldStroke" />
      <path
        class="chart__line"
        :d="rightPath"
        :stroke="dollarStroke"
        stroke-dasharray="4 3"
      />

      <template v-if="hoverIndex !== null">
        <line
          class="chart__grid"
          :x1="xs[hoverIndex]"
          :x2="xs[hoverIndex]"
          :y1="MARGIN.top"
          :y2="MARGIN.top + innerHeight"
        />
        <circle
          :cx="xs[hoverIndex]"
          :cy="leftScale(leftValues[hoverIndex])"
          r="3.5"
          :fill="goldStroke"
          :stroke="token('--surface')"
          stroke-width="1.5"
        />
        <circle
          :cx="xs[hoverIndex]"
          :cy="rightScale(rightValues[hoverIndex])"
          r="3.5"
          :fill="dollarStroke"
          :stroke="token('--surface')"
          stroke-width="1.5"
        />
      </template>

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
        <span>{{ leftLabel }}</span>
        <strong>{{ formatLeft(hovered.left) }}</strong>
      </div>
      <div class="chart-tip__row">
        <span>{{ rightLabel }}</span>
        <strong>{{ formatRight(hovered.right) }}</strong>
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

<style scoped>
.chart__swatch--dashed {
  background: none !important;
  border-top: 2px dashed var(--text);
  height: 0;
}
</style>
