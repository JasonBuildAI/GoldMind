<script setup lang="ts">
import type { HorizonResearch } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

import { pct } from './researchFormat'

/**
 * 校准诊断：预测概率分桶 vs 实际频率，逐尺度一张表。
 *
 * 每个桶都同时给出「平均预测」与「实际频率」——两者差距越小，概率越可信。
 * 没有分桶时写一句「没有可靠性分桶」，不画一张空表。
 */
defineProps<{ horizons: readonly HorizonResearch[] }>()

const field = (path: string) => fieldTestId(path)
</script>

<template>
  <div class="stack stack--lg" :data-testid="TESTIDS.researchDiagnostics">
    <div v-for="horizon in horizons" :key="horizon.horizon_days">
      <p v-if="horizon.reliability_bins.length === 0" class="note">
        {{ horizon.label }}：没有可靠性分桶。
      </p>
      <div v-else class="table-scroll">
        <table class="data-table">
          <caption class="note">
            {{ horizon.label }}：每桶对比「平均预测概率」与「实际频率」，两者差距越小，概率越可信。
          </caption>
          <thead>
            <tr>
              <th scope="col" class="num">区间下界</th>
              <th scope="col" class="num">区间上界</th>
              <th scope="col" class="num">样本数</th>
              <th scope="col" class="num">平均预测</th>
              <th scope="col" class="num">实际频率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(bin, index) in horizon.reliability_bins" :key="`${bin.lo}-${index}`">
              <td class="num" :data-testid="field('research.reliability.lo')">{{ pct(bin.lo) }}</td>
              <td class="num" :data-testid="field('research.reliability.hi')">{{ pct(bin.hi) }}</td>
              <td class="num" :data-testid="field('research.reliability.count')">{{ bin.count }}</td>
              <td class="num" :data-testid="field('research.reliability.mean_predicted')">
                {{ pct(bin.mean_predicted) }}
              </td>
              <td class="num" :data-testid="field('research.reliability.frequency')">
                {{ pct(bin.frequency) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
