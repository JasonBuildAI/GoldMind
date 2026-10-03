<script setup lang="ts">
import type { HorizonResearch } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

import { num, pct } from './researchFormat'

/**
 * 逐因子拆解：命中率、IC 与 HAC 对齐检验全给，逐尺度一张表。
 *
 * 低命中率不是丢脸的指标，是下一轮候选的线索；「对齐度」是因子方向与
 * 「永远看多」的同向程度，HAC t / p 是对齐度的显著性检验（只进研究台，
 * 不改变生产口径）。先验方向只给文字（正向 / 反向），不靠颜色。
 */
defineProps<{ horizons: readonly HorizonResearch[] }>()

const field = (path: string) => fieldTestId(path)

/** 先验方向：0 记「—」，不猜一个方向。 */
function signLabel(sign: number): string {
  if (sign > 0) return '正向'
  if (sign < 0) return '反向'
  return '—'
}
</script>

<template>
  <div class="stack stack--lg" :data-testid="TESTIDS.researchFactors">
    <div v-for="horizon in horizons" :key="horizon.horizon_days">
      <h4>{{ horizon.label }}</h4>
      <div class="table-scroll">
        <table class="data-table">
          <caption class="note">
            逐因子全样本口径；「对齐度」是因子方向与「永远看多」的同向程度，
            HAC t / p 是对齐度的显著性检验（只进研究台，不改变生产口径）。
          </caption>
          <thead>
            <tr>
              <th scope="col">因子</th>
              <th scope="col">类别</th>
              <th scope="col" class="num">权重</th>
              <th scope="col">先验方向</th>
              <th scope="col" class="num">样本</th>
              <th scope="col" class="num">命中率</th>
              <th scope="col" class="num">IC</th>
              <th scope="col" class="num">Rank IC</th>
              <th scope="col" class="num">对齐度</th>
              <th scope="col" class="num">HAC t</th>
              <th scope="col" class="num">p 值</th>
              <th scope="col" class="num">朴素 t</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="factor in horizon.factors" :key="factor.key">
              <th scope="row">
                <span :data-testid="field('research.factors.name')">{{ factor.name }}</span>
                <span class="note" :data-testid="field('research.factors.key')">{{ factor.key }}</span>
              </th>
              <td>
                <span :data-testid="field('research.factors.category_name')">
                  {{ factor.category_name }}
                </span>
                <span class="note" :data-testid="field('research.factors.category')">
                  {{ factor.category }}
                </span>
              </td>
              <td class="num" :data-testid="field('research.factors.weight')">
                {{ factor.weight.toFixed(2) }}
              </td>
              <td :data-testid="field('research.factors.sign')">{{ signLabel(factor.sign) }}</td>
              <td class="num" :data-testid="field('research.factors.samples')">{{ factor.samples }}</td>
              <td class="num" :data-testid="field('research.factors.hit_rate')">
                {{ pct(factor.hit_rate) }}
              </td>
              <td class="num" :data-testid="field('research.factors.ic')">{{ num(factor.ic) }}</td>
              <td class="num" :data-testid="field('research.factors.rank_ic')">
                {{ num(factor.rank_ic) }}
              </td>
              <td class="num" :data-testid="field('research.factors.alignment')">
                {{ num(factor.alignment) }}
              </td>
              <td class="num" :data-testid="field('research.factors.alignment_t')">
                {{ num(factor.alignment_t) }}
              </td>
              <td class="num" :data-testid="field('research.factors.alignment_p_value')">
                {{ num(factor.alignment_p_value) }}
              </td>
              <td class="num" :data-testid="field('research.factors.alignment_naive_t')">
                {{ num(factor.alignment_naive_t) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
