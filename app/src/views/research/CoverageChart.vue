<script setup lang="ts">
import { token } from '@/lib/tokens'
import type { HorizonResearch } from '@/services/api'
import { computed } from 'vue'

/**
 * 留出期 80% 区间覆盖率：自绘 SVG 柱状图，不引图表库（沿用 AreaChart 的做法）。
 *
 * 名义覆盖率 80% 用金色虚线标出；每根柱子是一个尺度。没有数字的尺度画成
 * 空柱并显示「—」，不补 0 —— 0% 和「没算出来」是两回事。
 *
 * SVG 的 stroke / fill 属性不认 CSS 变量，颜色经 `token()` 取计算值
 * （见 lib/tokens.ts 的说明），因此这里出现的是令牌名而不是十六进制色值。
 */
const props = defineProps<{ horizons: readonly HorizonResearch[] }>()

const WIDTH = 640
const HEIGHT = 210
const PAD_X = 52
const PAD_TOP = 26
const PAD_BOTTOM = 38
/** 名义覆盖率：80% 区间的目标线。 */
const TARGET = 0.8
const TICKS = [0, 0.4, 1] as const

const plotWidth = WIDTH - PAD_X * 2
const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM

const rule = token('--separator')
const gold = token('--gold')
const ink = token('--text')
const muted = token('--text-secondary')

/** 每个尺度一格；没有尺度时退化成整幅宽度，避免除零。 */
const slotWidth = computed(() =>
  props.horizons.length > 0 ? plotWidth / props.horizons.length : plotWidth,
)
const barWidth = computed(() => Math.min(56, slotWidth.value * 0.5))

/** 值 → 画布 y（0 在底部，1 在顶部）。 */
function y(value: number): number {
  return PAD_TOP + (1 - value) * plotHeight
}

const bars = computed(() =>
  props.horizons.map((horizon, index) => {
    const value = horizon.periods.holdout?.interval_coverage_80 ?? null
    const x = PAD_X + slotWidth.value * index + (slotWidth.value - barWidth.value) / 2
    const barTop = value === null ? y(0) : y(Math.max(0, Math.min(1, value)))
    return {
      key: horizon.horizon_days,
      label: horizon.label,
      x,
      barTop,
      height: value === null ? 2 : Math.max(1, y(0) - barTop),
      value: value === null ? '—' : `${(value * 100).toFixed(1)}%`,
      center: x + barWidth.value / 2,
      empty: value === null,
    }
  }),
)
</script>

<template>
  <figure class="panel coverage-chart">
    <figcaption class="panel__title">留出期 80% 区间覆盖率</figcaption>
    <svg
      class="coverage-chart__svg"
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      role="img"
      aria-label="历史留出期各尺度 80% 区间覆盖率与 80% 名义线的对比"
    >
      <!-- 网格与纵轴刻度 -->
      <g v-for="tick in TICKS" :key="tick">
        <line
          :x1="PAD_X"
          :x2="WIDTH - PAD_X"
          :y1="y(tick)"
          :y2="y(tick)"
          :stroke="rule"
          stroke-width="1"
        />
        <text :x="PAD_X - 8" :y="y(tick) + 4" text-anchor="end" font-size="11" :fill="muted">
          {{ Math.round(tick * 100) }}%
        </text>
      </g>

      <!-- 名义 80% 线：金价与关键数字的唯一强调色 -->
      <line
        :x1="PAD_X"
        :x2="WIDTH - PAD_X"
        :y1="y(TARGET)"
        :y2="y(TARGET)"
        :stroke="gold"
        stroke-width="1.5"
        stroke-dasharray="6 4"
      />
      <text
        :x="WIDTH - PAD_X"
        :y="y(TARGET) - 6"
        text-anchor="end"
        font-size="11"
        :fill="gold"
      >
        名义 80%
      </text>

      <!-- 每根柱子 = 一个尺度的历史留出期覆盖率 -->
      <g v-for="bar in bars" :key="bar.key">
        <rect
          :x="bar.x"
          :y="bar.barTop"
          :width="barWidth"
          :height="bar.height"
          :fill="bar.empty ? 'none' : ink"
          :stroke="bar.empty ? rule : 'none'"
        />
        <text
          :x="bar.center"
          :y="bar.barTop - 6"
          text-anchor="middle"
          font-size="11"
          :fill="ink"
        >
          {{ bar.value }}
        </text>
        <text
          :x="bar.center"
          :y="HEIGHT - PAD_BOTTOM + 18"
          text-anchor="middle"
          font-size="12"
          :fill="muted"
        >
          {{ bar.label }}
        </text>
      </g>
    </svg>
    <p class="note coverage-chart__note">
      柱值 = **历史**留出期（已被前两轮裁决看过）的实际覆盖率，只作记录；
      样本不足时显示「—」，不补数字。裁决窗口的覆盖率见「前向留出期」一节。
    </p>
  </figure>
</template>

<style scoped>
/* 面板自身不带外边距：间距由所在的节决定（与 React 版的 margin: 0 一致） */
.coverage-chart {
  margin: 0;
}

.coverage-chart__svg {
  width: 100%;
  height: auto;
}

.coverage-chart__note {
  margin-top: 10px;
}
</style>
