<script setup lang="ts">
import type { HorizonResearch } from '@/services/api'
import { fieldTestId } from '@/testids'
import { computed } from 'vue'

import { interval, num, pct } from './researchFormat'

/**
 * Beta 后验：独立下注口径的成功 / 失败合成后验，与 CRPS 并排。
 *
 * 先验写死 Beta(1,1)，α = 命中数 + 先验，β = 未命中数 + 先验；次数少时后验会很宽
 * —— 宽就是宽，不缩，也不拿别的口径凑一个好看的区间。
 * 后端响应模型尚未透出该字段时（`forward_posterior` 缺失）如实标注，不摆替代数字。
 */
const props = defineProps<{ horizons: readonly HorizonResearch[] }>()

const field = (path: string) => fieldTestId(path)

const anyPosterior = computed(() =>
  props.horizons.some((horizon) => Boolean(horizon.forward_posterior)),
)

interface PosteriorCell {
  path: string
  value: string
  /** 「先验」列是文字（Beta(1, 1)），其余列右对齐等宽 */
  numeric: boolean
}

/** 一个尺度的后验格子；缺字段时每格各自写「—」，不留空也不补零。 */
function cellsOf(horizon: HorizonResearch): PosteriorCell[] {
  const posterior = horizon.forward_posterior ?? null
  return [
    { path: 'prior', value: posterior ? `Beta(${posterior.prior.join(', ')})` : '—', numeric: false },
    { path: 'alpha', value: posterior ? num(posterior.alpha) : '—', numeric: true },
    { path: 'beta', value: posterior ? num(posterior.beta) : '—', numeric: true },
    { path: 'successes', value: posterior ? String(posterior.successes) : '—', numeric: true },
    {
      path: 'independent_bets',
      value: posterior ? String(posterior.independent_bets) : '—',
      numeric: true,
    },
    { path: 'mean', value: posterior ? pct(posterior.mean) : '—', numeric: true },
    { path: 'ci95', value: posterior ? interval(posterior.ci95) : '—', numeric: true },
    { path: 'threshold', value: posterior ? pct(posterior.threshold) : '—', numeric: true },
    {
      path: 'probability_above_threshold',
      value: posterior ? pct(posterior.probability_above_threshold) : '—',
      numeric: true,
    },
    { path: 'mean_crps', value: posterior ? num(posterior.mean_crps) : '—', numeric: true },
    {
      path: 'crps_skill_vs_flat',
      value: posterior ? num(posterior.crps_skill_vs_flat) : '—',
      numeric: true,
    },
  ]
}
</script>

<template>
  <div class="stack">
    <div class="table-scroll">
      <table class="data-table">
        <caption class="note">
          先验 Beta(1,1)；α = 命中数 + 先验，β = 未命中数 + 先验。独立下注口径把重叠样本
          折成互不相干的证据，次数少时后验会很宽 —— 宽就是宽，不缩。
        </caption>
        <thead>
          <tr>
            <th scope="col">尺度</th>
            <th scope="col">先验</th>
            <th scope="col" class="num">α</th>
            <th scope="col" class="num">β</th>
            <th scope="col" class="num">命中数</th>
            <th scope="col" class="num">独立下注</th>
            <th scope="col" class="num">后验均值</th>
            <th scope="col" class="num">95% CI</th>
            <th scope="col" class="num">阈值</th>
            <th scope="col" class="num">高于阈值概率</th>
            <th scope="col" class="num">平均 CRPS</th>
            <th scope="col" class="num">CRPS 技能</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="horizon in horizons" :key="horizon.horizon_days">
            <th scope="row">{{ horizon.label }}</th>
            <td
              v-for="cell in cellsOf(horizon)"
              :key="cell.path"
              :class="{ num: cell.numeric }"
              :data-testid="field(`research.horizons.forward_posterior.${cell.path}`)"
            >
              {{ cell.value }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="!anyPosterior" class="note">
      后端响应未透出 Beta 后验字段（HorizonResearch 响应模型尚未声明）——
      这里是如实标注，不摆替代数字。
    </p>
  </div>
</template>
