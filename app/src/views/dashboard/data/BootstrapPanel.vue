<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import type { Column } from '@/components/dataTable'
import PanelBlock from '@/components/PanelBlock.vue'
import { displayStamp } from '@/lib/format'
import type { BootstrapPhase, HealthResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

import { text } from './fields'

/**
 * 初始化进度：启动引导的状态、步骤、时间与逐阶段结果，外加数据空档表。
 *
 * status 的每种取值都有对应的说法（含 disabled / skipped）—— 后端怎么说，
 * 页面就怎么写，不把「未启用」美化成像在运行。
 */
const props = defineProps<{
  health: HealthResponse | null
  error: string | null
}>()

const field = (path: string) => fieldTestId(path)

/** status 的固定说法：读不懂的状态显示「状态未知」，不替后端编一个解释。 */
const BOOTSTRAP_STATUS_NOTE: Record<string, string> = {
  pending: '等待启动',
  running: '正在运行',
  done: '已完成',
  failed: '失败',
  disabled: '未启用（后端关闭了启动引导）',
  skipped: '本轮跳过（后端未启用自动引导，例如测试环境）',
}

const bootstrap = computed(() => props.health?.bootstrap ?? null)
const phases = computed(() => bootstrap.value?.phases ?? [])
/** 还在跑：这两种状态下页面数据可能陆续补齐，如实说明，别让人以为已经定格。 */
const running = computed(
  () => bootstrap.value?.status === 'running' || bootstrap.value?.status === 'pending',
)
const statusNote = computed(() =>
  bootstrap.value ? (BOOTSTRAP_STATUS_NOTE[bootstrap.value.status] ?? '状态未知') : '',
)

const PHASE_COLUMNS: ReadonlyArray<Column<BootstrapPhase>> = [
  { key: 'label', header: '阶段' },
  { key: 'key', header: '代号' },
  { key: 'status', header: '状态' },
  { key: 'note', header: '说明' },
  { key: 'at', header: '时间' },
]

/** 数据空档表的一行：通道 / 行数 / 最后一期 / 缺口明细。 */
interface GapRow {
  key: string
  label: string
  count: string
  countTestId: string
  last: string
  lastTestId: string
  detail: string
  detailTestId?: string
}

const GAP_COLUMNS: ReadonlyArray<Column<GapRow>> = [
  { key: 'label', header: '通道' },
  { key: 'count', header: '行数', numeric: true },
  { key: 'last', header: '最后一期' },
  { key: 'detail', header: '缺口明细' },
]

/**
 * 缺键显示「—」：空档表宁可说「不知道」，也不猜一个数字。
 * 量化那一行没有「最后一期」，给的是稀疏年份 / 覆盖窗口 / 无数据序列。
 */
const gapRows = computed<GapRow[]>(() => {
  const gaps = bootstrap.value?.gaps ?? {}
  return [
    {
      key: 'gold_prices',
      label: '金价日线',
      count: text(gaps.gold_prices?.rows),
      countTestId: field('health.bootstrap.gaps.gold_prices.rows'),
      last: text(gaps.gold_prices?.last_date),
      lastTestId: field('health.bootstrap.gaps.gold_prices.last_date'),
      detail: '—',
    },
    {
      key: 'dollar_index',
      label: '美元指数',
      count: text(gaps.dollar_index?.rows),
      countTestId: field('health.bootstrap.gaps.dollar_index.rows'),
      last: text(gaps.dollar_index?.last_date),
      lastTestId: field('health.bootstrap.gaps.dollar_index.last_date'),
      detail: '—',
    },
    {
      key: 'gold_news',
      label: '黄金新闻',
      count: text(gaps.gold_news?.rows),
      countTestId: field('health.bootstrap.gaps.gold_news.rows'),
      last: text(gaps.gold_news?.last_published_at),
      lastTestId: field('health.bootstrap.gaps.gold_news.last_published_at'),
      detail: '—',
    },
    {
      key: 'news_digest',
      label: '消息摘要',
      count: text(gaps.news_digest?.rows),
      countTestId: field('health.bootstrap.gaps.news_digest.rows'),
      last: text(gaps.news_digest?.last_published_at),
      lastTestId: field('health.bootstrap.gaps.news_digest.last_published_at'),
      detail: '—',
    },
    {
      key: 'quant',
      label: '量化因子',
      count: `稀疏年份 ${text(gaps.quant?.sparse_year_count)} 个`,
      countTestId: field('health.bootstrap.gaps.quant.sparse_year_count'),
      last: `覆盖窗口 ${text(gaps.quant?.window_years)} 年`,
      lastTestId: field('health.bootstrap.gaps.quant.window_years'),
      detail: `无数据序列：${text(gaps.quant?.series_without_data)}`,
      detailTestId: field('health.bootstrap.gaps.quant.series_without_data'),
    },
  ]
})
</script>

<template>
  <PanelBlock title="初始化进度">
    <p v-if="!bootstrap" class="note" :data-testid="TESTIDS.dataBootstrap">
      /health 未返回 bootstrap 字段（后端版本较旧或接口被裁剪）。
    </p>

    <div v-else class="stack" :data-testid="TESTIDS.dataBootstrap">
      <!-- 括号与分隔符紧贴 span 写：模板里的换行会被折叠成一个空格，
           中文句子里会凭空多出空格（如「（ 已启用」）。 -->
      <p class="section__conclusion">
        <span :data-testid="field('health.bootstrap.status')">{{ bootstrap.status }}</span>
        <span>（<span :data-testid="field('health.bootstrap.enabled')">{{ bootstrap.enabled ? '已启用' : '未启用' }}</span> · <span :data-testid="field('health.bootstrap.ready')">{{ bootstrap.ready ? '数据就绪' : '尚未就绪' }}</span>）· {{ statusNote }} · 步骤 <span :data-testid="field('health.bootstrap.step.index')">{{ bootstrap.step.index }}</span>/<span :data-testid="field('health.bootstrap.step.total')">{{ bootstrap.step.total }}</span></span>
      </p>

      <p class="panel__meta">
        <span :data-testid="field('health.bootstrap.started_at')">开始 {{ displayStamp(bootstrap.started_at) ?? '—' }}</span>
        <span :data-testid="field('health.bootstrap.finished_at')">完成 {{ displayStamp(bootstrap.finished_at) ?? '—' }}</span>
        <span :data-testid="field('health.bootstrap.error')">错误：{{ bootstrap.error ?? '无' }}</span>
        <span :data-testid="field('health.bootstrap.migrations')">迁移注册表：{{ text(bootstrap.migrations) }}</span>
      </p>

      <p v-if="running" class="note">
        引导仍在进行 —— 页面上的数据可能陆续补齐，完成后本行会变成「已完成」。
      </p>

      <DataTable
        v-if="phases.length > 0"
        :rows="phases"
        :columns="PHASE_COLUMNS"
        :row-key="(row) => row.key"
        caption="启动阶段：每一步的状态与说明都由后端给出；失败步骤会在这里留下原因。"
      >
        <template #label="{ row }">
          <span :data-testid="field('health.bootstrap.phases.label')">{{ row.label }}</span>
        </template>
        <template #key="{ row }">
          <span class="note" :data-testid="field('health.bootstrap.phases.key')">{{ row.key }}</span>
        </template>
        <template #status="{ row }">
          <span :data-testid="field('health.bootstrap.phases.status')">{{ row.status }}</span>
        </template>
        <template #note="{ row }">
          <span class="note" :data-testid="field('health.bootstrap.phases.note')">{{ row.note ?? '—' }}</span>
        </template>
        <template #at="{ row }">
          <span :data-testid="field('health.bootstrap.phases.at')">{{ displayStamp(row.at) ?? '—' }}</span>
        </template>
      </DataTable>

      <DataTable
        :rows="gapRows"
        :columns="GAP_COLUMNS"
        :row-key="(row) => row.key"
        caption="数据空档：每个通道的最后一期与是否需要补数；缺键显示「—」，不猜数字。"
      >
        <template #count="{ row }">
          <span :data-testid="row.countTestId">{{ row.count }}</span>
        </template>
        <template #last="{ row }">
          <span :data-testid="row.lastTestId">{{ row.last }}</span>
        </template>
        <template #detail="{ row }">
          <span class="note" :data-testid="row.detailTestId">{{ row.detail }}</span>
        </template>
      </DataTable>
    </div>

    <p v-if="error" class="panel__error">/health 读取失败：{{ error }}</p>
  </PanelBlock>
</template>
