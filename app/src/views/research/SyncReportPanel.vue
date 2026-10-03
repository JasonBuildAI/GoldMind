<script setup lang="ts">
import { displayStamp } from '@/lib/format'
import type { SourcesStatusResponse } from '@/services/api'
import { TESTIDS } from '@/testids'
import { computed } from 'vue'

/**
 * 同步报告：研究数字所依赖的量化同步渠道与状态。
 *
 * 状态、完成时间、条目数与错误原文照后端给的值显示；数据源状态取不到时
 * 只写原因，不补数字（见 AGENTS.md 红线一）。
 * 这一块没有字段级选择器 —— 量化同步渠道用的是数据源接口的字段，
 * 它们的字段级选择器归「数据与方法」一节（`sources.rows.*`）。
 */
const props = defineProps<{
  sources: SourcesStatusResponse | null
  error: string | null
}>()

const stamp = computed(() => displayStamp(props.sources?.generated_at))

/** 只取量化同步渠道：研究页的数字全部来自这条链路。 */
const quantSources = computed(
  () => props.sources?.sources.filter((source) => source.channel === 'quant_sync') ?? [],
)
</script>

<template>
  <div class="stack" :data-testid="TESTIDS.researchSync">
    <p v-if="sources" class="section__conclusion">
      数据源状态生成于 {{ stamp ?? '—' }}：共 {{ sources.summary.total }} 个渠道，
      可用 {{ sources.summary.ok }} · 不可用 {{ sources.summary.error }} · 本轮跳过 {{ sources.summary.skipped }} ·
      陈旧 {{ sources.summary.stale }}。
    </p>
    <p v-else class="note">数据源状态不可用：{{ error ?? '接口没有返回。' }}</p>

    <div v-if="quantSources.length > 0" class="table-scroll">
      <table class="data-table">
        <caption class="note">
          量化同步渠道最近一次尝试：状态、完成时间、条目数与错误原文。
        </caption>
        <thead>
          <tr>
            <th scope="col">来源</th>
            <th scope="col">状态</th>
            <th scope="col">完成</th>
            <th scope="col" class="num">条目</th>
            <th scope="col">错误</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="source in quantSources" :key="source.source_key">
            <th scope="row">{{ source.source_key }}</th>
            <td>{{ source.status_label }}<span class="note">（{{ source.status }}）</span></td>
            <td>{{ displayStamp(source.finished_at) ?? '—' }}</td>
            <td class="num">{{ source.items ?? '—' }}</td>
            <td class="note">{{ source.error ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else-if="sources" class="note">没有量化同步渠道的记录 —— 量化接口可能还没跑过同步。</p>

    <p class="provenance">
      评估口径、预注册规则与复现命令见仓库内 docs/specs/2026-10-02-研究台报告.md 与
      docs/specs/2026-10-02-量化策略提升路线图.md；数据不可用时本页只显示原因，不补任何数字。
    </p>
  </div>
</template>
