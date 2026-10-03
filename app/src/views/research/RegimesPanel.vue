<script setup lang="ts">
import type { ResearchRegimeCandidate } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

/**
 * 分段与 Regime 候选：第四轮预注册的登记表。
 *
 * 状态与说明照后端原文显示，不在前端推断 —— `lab_only` 只进研究台，
 * 过前向窗口闸门之前不应出现别的取值（见 README「七、研究台与预注册」）。
 */
defineProps<{ regimes: readonly ResearchRegimeCandidate[] }>()

const field = (path: string) => fieldTestId(path)
</script>

<template>
  <div class="table-scroll" :data-testid="TESTIDS.researchRegimes">
    <table class="data-table">
      <caption class="note">
        候选 regime 序列的登记信息；状态与说明照后端原文显示，不在前端推断。
      </caption>
      <thead>
        <tr>
          <th scope="col">候选</th>
          <th scope="col">序列</th>
          <th scope="col">说明</th>
          <th scope="col">状态</th>
          <th scope="col">备注</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="regime in regimes" :key="regime.key">
          <th scope="row" :data-testid="field('research.regimes.name')">
            {{ regime.name }}<span class="note" :data-testid="field('research.regimes.key')">{{ regime.key }}</span>
          </th>
          <td :data-testid="field('research.regimes.series_key')">{{ regime.series_key }}</td>
          <td class="note" :data-testid="field('research.regimes.description')">
            {{ regime.description }}
          </td>
          <td :data-testid="field('research.regimes.status')">{{ regime.status }}</td>
          <td class="note" :data-testid="field('research.regimes.note')">{{ regime.note }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
