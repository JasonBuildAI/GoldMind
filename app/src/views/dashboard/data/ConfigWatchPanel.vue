<script setup lang="ts">
import PanelBlock from '@/components/PanelBlock.vue'
import { displayStamp } from '@/lib/format'
import type { HealthResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

/**
 * 配置与热加载（.env config_watch）：状态、监测文件、间隔与重载过的键。
 *
 * 只展示**文件名与键名**，不展示任何值 —— 密钥只进 .env 与部署环境，
 * 永不进日志、进页面（见 docs/10-密钥与隐私.md）。
 */
const props = defineProps<{ health: HealthResponse | null }>()

const field = (path: string) => fieldTestId(path)

const configWatch = computed(() => props.health?.config_watch ?? null)
</script>

<template>
  <PanelBlock title="配置与热加载">
    <p v-if="!configWatch" class="note" :data-testid="TESTIDS.dataConfigWatch">
      /health 未返回 config_watch 字段。
    </p>

    <div v-else class="stack" :data-testid="TESTIDS.dataConfigWatch">
      <p class="section__conclusion">
        <span>配置热加载 <span :data-testid="field('health.config_watch.status')">{{ configWatch.status }}</span></span>
        <span>（<span :data-testid="field('health.config_watch.enabled')">{{ configWatch.enabled ? '已启用' : '未启用' }}</span>）· 监测文件 <span :data-testid="field('health.config_watch.env_file')">{{ configWatch.env_file }}</span> · 间隔 <span :data-testid="field('health.config_watch.interval_seconds')">{{ configWatch.interval_seconds }}</span> 秒</span>
      </p>

      <p class="panel__meta">
        <span :data-testid="field('health.config_watch.last_check_at')">上次检查 {{ displayStamp(configWatch.last_check_at) ?? '—' }}</span>
        <span :data-testid="field('health.config_watch.last_reload_at')">上次重载 {{ displayStamp(configWatch.last_reload_at) ?? '—' }}</span>
        <span :data-testid="field('health.config_watch.reloaded_keys')">重载过的键：{{ configWatch.reloaded_keys.length > 0 ? configWatch.reloaded_keys.join('、') : '无' }}</span>
        <span :data-testid="field('health.config_watch.note')">{{ configWatch.note ?? '—' }}</span>
      </p>
    </div>
  </PanelBlock>
</template>
