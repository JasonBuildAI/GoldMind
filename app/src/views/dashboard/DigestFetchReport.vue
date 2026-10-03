<script setup lang="ts">
import { displayStamp } from '@/lib/format'
import type { DigestFetchReport, DigestRefreshResponse } from '@/services/api'
import { fieldTestId } from '@/testids'
import { computed } from 'vue'

/**
 * 抓取报告：所有计数进表格；来源明细各占一行。
 *
 * 「本次抓取」的成败结论只在**手动抓取后**出现（`success` 字段只有刷新响应才有）——
 * 上次抓取报告里的历史记录不该冒充「本次结果」。
 */
const props = defineProps<{
  report: DigestRefreshResponse | DigestFetchReport
  testId?: string
}>()

const field = (path: string) => fieldTestId(path)

const hasSuccess = computed(() => 'success' in props.report)
const success = computed(() =>
  hasSuccess.value ? (props.report as DigestRefreshResponse).success : false,
)

const rows = computed(() => {
  const report = props.report
  return [
    ['抓取时间', displayStamp(report.fetched_at) ?? report.fetched_at, field('digest.fetch.fetched_at')],
    ['来源总数', String(report.total_sources), field('digest.fetch.total_sources')],
    ['成功来源', String(report.ok_sources), field('digest.fetch.ok_sources')],
    ['失败来源', String(report.failed_sources), field('digest.fetch.failed_sources')],
    ['抓到条目', String(report.entries), field('digest.fetch.entries')],
    ['保留条目', String(report.kept), field('digest.fetch.kept')],
    ['新增条目', String(report.new_items), field('digest.fetch.new_items')],
    ['重复条目', String(report.duplicates), field('digest.fetch.duplicates')],
    ['无标题跳过', String(report.skipped_no_title), field('digest.fetch.skipped_no_title')],
    ['无链接跳过', String(report.skipped_no_url), field('digest.fetch.skipped_no_url')],
    ['无时间跳过', String(report.skipped_no_time), field('digest.fetch.skipped_no_time')],
    ['相关性过滤', String(report.skipped_filtered), field('digest.fetch.skipped_filtered')],
    ['落库失败跳过', String(report.skipped_unstorable), field('digest.fetch.skipped_unstorable')],
  ] as const
})
</script>

<template>
  <div class="panel" :data-testid="testId">
    <h4 class="panel__title">抓取报告</h4>

    <div class="table-scroll">
      <table class="data-table">
        <tbody>
          <tr v-for="[label, value, id] in rows" :key="label">
            <th scope="row">{{ label }}</th>
            <td class="num" :data-testid="id">{{ value }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="report.sources.length > 0" class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th scope="col">来源</th>
            <th scope="col">状态</th>
            <th scope="col" class="num">抓到</th>
            <th scope="col" class="num">保留</th>
            <th scope="col" class="num">新增</th>
            <th scope="col">错误</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="source in report.sources" :key="source.name">
            <th scope="row" :data-testid="field('digest.fetch.sources.name')">{{ source.name }}</th>
            <td :data-testid="field('digest.fetch.sources.status')">{{ source.status }}</td>
            <td class="num" :data-testid="field('digest.fetch.sources.entries')">{{ source.entries }}</td>
            <td class="num" :data-testid="field('digest.fetch.sources.kept')">{{ source.kept }}</td>
            <td class="num" :data-testid="field('digest.fetch.sources.new')">{{ source.new }}</td>
            <td class="note" :data-testid="field('digest.fetch.sources.error')">
              {{ source.error ?? '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="hasSuccess" class="note" :data-testid="field('digest.refresh.success')">
      本次抓取结果：{{ success ? '至少一个来源成功' : '所有来源都失败' }}
    </p>
  </div>
</template>
