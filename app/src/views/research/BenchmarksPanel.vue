<script setup lang="ts">
import type { ResearchBenchmark } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

/**
 * 基准候选：研究基准的口径（含不含展期）+ 对照候选。
 *
 * 口径提示必须让读者知道收益里有没有换月价差 —— 换基准只换评估目标，
 * 因子与信号一字不动。可用性由后端判定；不可用的候选给出原因，
 * 不替它编一个数字（见 README「七、研究台与预注册」第四轮）。
 */
defineProps<{ benchmark: ResearchBenchmark }>()

const field = (path: string) => fieldTestId(path)
</script>

<template>
  <div class="stack" :data-testid="TESTIDS.researchBenchmarks">
    <p class="section__conclusion">研究基准：<span :data-testid="field('research.benchmark.name')">{{ benchmark.name }}</span><span class="note" :data-testid="field('research.benchmark.key')">{{ benchmark.key }}</span>——<span :data-testid="field('research.benchmark.note')">{{ benchmark.note }}</span></p>

    <div class="table-scroll">
      <table class="data-table">
        <caption class="note">
          对照候选：可用性由后端判定；不可用的候选给出原因，不替它编一个数字。
        </caption>
        <thead>
          <tr>
            <th scope="col">候选</th>
            <th scope="col">口径说明</th>
            <th scope="col">可用</th>
            <th scope="col">原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="alternative in benchmark.alternatives" :key="alternative.key">
            <th scope="row">
              <span :data-testid="field('research.benchmark.alternatives.name')">
                {{ alternative.name }}
              </span>
              <span class="note" :data-testid="field('research.benchmark.alternatives.key')">
                {{ alternative.key }}
              </span>
            </th>
            <td class="note" :data-testid="field('research.benchmark.alternatives.note')">
              {{ alternative.note }}
            </td>
            <td :data-testid="field('research.benchmark.alternatives.available')">
              {{ alternative.available ? '可用' : '不可用' }}
            </td>
            <td class="note" :data-testid="field('research.benchmark.alternatives.reason')">
              {{ alternative.reason }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
