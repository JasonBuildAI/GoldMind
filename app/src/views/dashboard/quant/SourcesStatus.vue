<script setup lang="ts">
import { displayStamp } from '@/lib/format'
import type { QuantFactorsResponse } from '@/services/api'
import { fieldTestId } from '@/testids'
import { computed } from 'vue'

import { statusLabel } from './shared'

/**
 * 量化数据源状态与同步报告：收进一层折叠，不占主版面。
 *
 * 「未到期」表示本轮按各源的最小间隔跳过，不是失败 —— 状态词照后端显示，
 * 未知状态原样透出，不翻译成好听的话。逐源的同步报告在「数据与方法」里，
 * 这里只给最近一次同步完成时间与失败原因。
 */
const props = defineProps<{ factors: QuantFactorsResponse }>()

const field = (path: string) => fieldTestId(path)

const okSources = computed(() => props.factors.sources.filter((source) => source.status === 'ok').length)
const failed = computed(() => props.factors.sources.filter((source) => source.status === 'error'))
</script>

<template>
  <details class="row-details" data-testid="quant-sources-details">
    <summary>数据源状态（{{ okSources }}/{{ factors.sources.length }} 正常，展开看逐个源与同步报告）</summary>

    <p v-if="failed.length > 0" class="panel__error">
      数据源不可用：{{ failed.map((source) => `${source.label ?? source.name}（${source.error ?? '原因未知'}）`).join('；') }}
    </p>

    <p class="panel__meta">
      <span>同步完成 {{ displayStamp(factors.sync.finished_at) ?? '—' }}</span>
      <span class="note">「未到期」表示本轮按各源的最小间隔跳过，不是失败；同步报告见「数据与方法」。</span>
    </p>

    <div v-if="factors.sources.length > 0" class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th scope="col">数据源</th>
            <th scope="col">状态</th>
            <th scope="col">说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="source in factors.sources" :key="source.name">
            <th scope="row">
              <span :data-testid="field('quant.source.label')">{{ source.label ?? source.name }}</span><span class="note" :data-testid="field('quant.source.name')">{{ source.name }}</span>
            </th>
            <td>
              <span :data-testid="field('quant.source.status')">{{ statusLabel(source.status) }}</span><span v-if="source.status !== 'ok'" class="tag">{{ statusLabel(source.status) }}</span>
            </td>
            <td class="note">
              <span :data-testid="field('quant.source.error')">{{ source.error ?? '—' }}</span><span class="note" :data-testid="field('quant.source.reason')">{{ source.reason ?? '—' }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="note">还没有同步记录 —— 点右上角「重新抓取」跑一轮。</p>
  </details>
</template>
