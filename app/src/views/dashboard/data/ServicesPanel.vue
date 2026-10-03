<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import type { Column } from '@/components/dataTable'
import PanelBlock from '@/components/PanelBlock.vue'
import { displayStamp } from '@/lib/format'
import type { HealthResponse } from '@/services/api'
import { fieldTestId } from '@/testids'

import { serviceValue, text } from './fields'

/**
 * 服务状态：整体状态、版本、时间与各服务的自检结果。
 *
 * 密钥类配置**只显示是否已配置与端点**，不显示值 —— 页面是公开的，
 * 密钥只进 .env 与部署环境（见 docs/10-密钥与隐私.md）。
 */
defineProps<{ health: HealthResponse | null }>()

const field = (path: string) => fieldTestId(path)

interface ServiceRow {
  key: string
  label: string
  /** 状态字段的路径：既是取值路径，也是字段级选择器的后半段 */
  path: string
}

const SERVICE_ROWS: ReadonlyArray<ServiceRow> = [
  { key: 'ai_config', label: '模型服务', path: 'health.services.ai_config.status' },
  { key: 'database', label: '数据库', path: 'health.services.database.status' },
  { key: 'tencent_api', label: '行情接口', path: 'health.services.tencent_api.status' },
  { key: 'cache', label: '缓存', path: 'health.services.cache.status' },
  { key: 'scheduler', label: '定时任务', path: 'health.services.scheduler.status' },
]

const SERVICE_COLUMNS: ReadonlyArray<Column<ServiceRow>> = [
  { key: 'label', header: '服务' },
  { key: 'status', header: '状态' },
  { key: 'note', header: '说明' },
]
</script>

<template>
  <PanelBlock title="服务状态">
    <p class="panel__meta">
      <span :data-testid="field('health.status')">整体 {{ health?.status ?? '—' }}</span>
      <span :data-testid="field('health.version')">版本 {{ health?.version ?? '—' }}</span>
      <span :data-testid="field('health.timestamp')">时间 {{ displayStamp(health?.timestamp) ?? '—' }}</span>
    </p>

    <DataTable
      :rows="SERVICE_ROWS"
      :columns="SERVICE_COLUMNS"
      :row-key="(row) => row.key"
      caption="服务自检：密钥类配置只显示是否已配置与端点信息，不展示密钥本身。"
    >
      <template #status="{ row }">
        <span :data-testid="field(row.path)">{{ text(serviceValue(health, row.key, 'status')) }}</span>
      </template>
      <template #note="{ row }">
        <!-- 模型服务的说明逐字段独占一行：挤成一行读不出哪个值属于哪个字段。 -->
        <div v-if="row.key === 'ai_config'" class="note">
          <div :data-testid="field('health.services.ai_config.provider')">供应商 {{ text(serviceValue(health, 'ai_config', 'provider')) }}</div>
          <div :data-testid="field('health.services.ai_config.model')">模型 {{ text(serviceValue(health, 'ai_config', 'model')) }}</div>
          <div :data-testid="field('health.services.ai_config.base_url')">端点 {{ text(serviceValue(health, 'ai_config', 'base_url')) }}</div>
          <div :data-testid="field('health.services.ai_config.search_model')">联网搜索模型 {{ text(serviceValue(health, 'ai_config', 'search_model')) }}</div>
          <div :data-testid="field('health.services.ai_config.configured')">密钥已配置：{{ text(serviceValue(health, 'ai_config', 'configured')) }}</div>
        </div>
        <div v-else class="note">—</div>
      </template>
    </DataTable>
  </PanelBlock>
</template>
