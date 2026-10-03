<script setup lang="ts">
import RefreshButton from '@/components/RefreshButton.vue'
import StateBlock from '@/components/StateBlock.vue'
import TabsNav from '@/components/TabsNav.vue'
import { useFreshnessBlock } from '@/composables/useFreshnessBlock'
import { describeApiError } from '@/lib/apiError'
import { displayStamp } from '@/lib/format'
import {
  newsDigestApi,
  type DigestRefreshResponse,
  type DigestResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed, onMounted, ref } from 'vue'

import DigestFetchReport from './DigestFetchReport.vue'
import DigestRow from './DigestRow.vue'

/**
 * 消息：高权威来源的黄金相关消息，按重要性与置信度排序。
 *
 * 三件不能妥协的事：
 * 1. 分数与排序全部来自后端确定性评分（来源权威 + 黄金相关 + 同题覆盖 + 时效），
 *    前端不重排、不补算；三个窗口允许重叠（同一事件出现在多个窗口是设计行为）。
 * 2. 抓不到就显示「不可用 + 原因」，不摆任何内置消息。
 * 3. 原文链接一律新窗口打开，展开区给出摘要、评分依据、事件标注与同题报道。
 */
const field = (path: string) => fieldTestId(path)

const data = ref<DigestResponse | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const error = ref<string | null>(null)
/** 手动抓取后的本次报告；与「上次抓取报告」是两件事，不互相顶替。 */
const report = ref<DigestRefreshResponse | null>(null)
const activeWindow = ref('24h')

async function fetchDigest(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    data.value = await newsDigestApi.getDigest()
    // 默认停在第一个窗口（后端按 24 小时 / 7 天 / 30 天顺序下发）
    if (data.value?.windows.length && !data.value.windows.some((w) => w.key === activeWindow.value)) {
      activeWindow.value = data.value.windows[0].key
    }
  } catch (err) {
    error.value = describeApiError(err, { fallback: '获取消息失败。' })
    data.value = null
  } finally {
    loading.value = false
  }
}

async function crawl(): Promise<void> {
  refreshing.value = true
  error.value = null
  report.value = null
  try {
    report.value = await newsDigestApi.refresh()
    data.value = await newsDigestApi.getDigest()
  } catch (err) {
    error.value = describeApiError(err, {
      fallback: '抓取最新消息失败。',
      timeout: '抓取耗时较长，请稍后重试。',
    })
  } finally {
    refreshing.value = false
  }
}

onMounted(() => void fetchDigest())

const lastFetch = computed(() => data.value?.last_fetch ?? null)
const hasData = computed(() => Boolean(data.value?.has_data))
const stamp = computed(() => displayStamp(lastFetch.value?.fetched_at))
const windows = computed(() => data.value?.windows ?? [])
const activeWindowData = computed(
  () => windows.value.find((window) => window.key === activeWindow.value) ?? windows.value[0] ?? null,
)

/**
 * 翻译状态：没有它，未翻译的条目只能说一句「暂不可用」，读者不知道是关了、
 * 没配 LLM、还是还没轮到。原因由后端给，前端不编。
 */
const translation = computed(() => data.value?.translation ?? null)
const translationReason = computed(
  () =>
    translation.value?.reason ??
    '中文翻译还没轮到这一条（每轮抓取只翻一批，最新优先）',
)

/** 本次抓取的一句话摘要（只在手动抓取后显示）。 */
const reportLine = computed(() => {
  const value = report.value
  if (!value) return ''
  const bits = [
    `本次抓取：${value.ok_sources}/${value.total_sources} 个来源成功`,
    `新增 ${value.new_items} 条`,
  ]
  if (value.duplicates > 0) bits.push(`重复 ${value.duplicates} 条`)
  if (value.skipped_filtered > 0) bits.push(`不相关跳过 ${value.skipped_filtered} 条`)
  if (value.skipped_unstorable > 0) bits.push(`落库失败跳过 ${value.skipped_unstorable} 条`)
  if (value.failed_sources > 0) bits.push(`失败 ${value.failed_sources} 个来源`)
  bits.push(`本轮译出 ${value.translated} 条中文`)
  if (value.translation_reason) bits.push(`翻译：${value.translation_reason}`)
  return bits.join(' · ')
})

useFreshnessBlock(
  'messages',
  '消息',
  computed(() => (hasData.value ? 'fresh' : loading.value ? 'pending' : 'unavailable')),
  computed(() => data.value?.generated_at || lastFetch.value?.fetched_at || null),
)
</script>

<template>
  <!--
    注意：这个面板**不带 id** —— `#messages` 是外层 MessagesSection 那一节的锚点。
    两处都写 id="messages" 会让锚点跳到错误的元素（页面结构守卫盯着重复 id）。
  -->
  <section class="panel" :data-testid="TESTIDS.driversMessages" aria-label="消息">
    <div class="panel__head">
      <h3 class="panel__title">消息</h3>
      <RefreshButton
        :busy="refreshing"
        label="抓取最新消息"
        busy-label="抓取中…"
        @click="crawl"
      />
    </div>

    <StateBlock v-if="loading && !data" title="正在读取消息…" test-id="messages-loading" />
    <StateBlock
      v-else-if="!hasData"
      kind="unavailable"
      test-id="messages-unavailable"
      title="消息暂不可用"
      :detail="
        error ??
        data?.unavailable_reason ??
        '没能取到任何真实消息。这里不显示内置内容 —— 编造消息比留空更糟。'
      "
    >
      <template #actions>
        <RefreshButton
          :busy="refreshing"
          label="抓取最新消息"
          busy-label="抓取中…"
          @click="crawl"
        />
      </template>
    </StateBlock>

    <div v-else>
      <p class="panel__meta">
        <span :data-testid="field('digest.has_data')">
          {{ data?.has_data ? '有可用消息' : '无可用消息' }}
        </span>
        <span v-if="stamp" :data-testid="field('digest.generated_at')">生成时间 {{ stamp }}</span>
        <span v-if="data?.unavailable_reason" class="panel__error" :data-testid="field('digest.unavailable_reason')">
          {{ data.unavailable_reason }}
        </span>
        <span v-if="error" class="panel__error">刷新失败：{{ error }}</span>
      </p>

      <p v-if="report" class="note" :data-testid="TESTIDS.messageReport">
        {{ reportLine }}
        <span :data-testid="field('digest.refresh.success')">
          本次抓取结果：{{ report.success ? '至少一个来源成功' : '所有来源都失败' }}
        </span>
      </p>

      <!--
        翻译状态一行：让「哪几条没有中文、为什么」可回答。
        `reason` 只在确实还有待翻译条目且当前翻不了时才有值，所以这里分两种说法 ——
        全都翻好了就不该摆一句「暂不可用」吓人。
      -->
      <p v-if="translation" class="panel__meta" :data-testid="field('digest.translation.enabled')">
        中文翻译：{{ translation.enabled ? '已开启' : '已关闭' }}
        <span v-if="translation.model" :data-testid="field('digest.translation.model')">
          · 模型 {{ translation.model }}
        </span>
        <span :data-testid="field('digest.translation.pending')">
          · 待翻译 {{ translation.pending }} 条
        </span>
        <span v-if="translation.reason" class="panel__error" :data-testid="field('digest.translation.reason')">
          （{{ translation.reason }}）
        </span>
      </p>

      <div :data-testid="TESTIDS.messagesWindows">
        <TabsNav
          v-if="windows.length > 0"
          v-model="activeWindow"
          :items="windows.map((w) => ({ key: w.key, label: w.label }))"
          label="消息时间范围"
          panel-id="messages-window"
        />

        <div
          v-if="activeWindowData"
          :id="`messages-window-${activeWindowData.key}`"
          role="tabpanel"
          :aria-labelledby="`messages-window-tab-${activeWindowData.key}`"
          class="messages__panel"
        >
          <p class="panel__meta">
            <span :data-testid="field('digest.windows.key')">窗口 {{ activeWindowData.key }}</span>
            <span :data-testid="field('digest.windows.label')">{{ activeWindowData.label }}</span>
            <span :data-testid="field('digest.windows.hours')">{{ activeWindowData.hours }} 小时</span>
            <span :data-testid="field('digest.windows.total_clusters')">
              共 {{ activeWindowData.total_clusters }} 组同题报道
            </span>
            <span>展示前 {{ activeWindowData.items.length }} 条，按重要性排序</span>
          </p>

          <p v-if="activeWindowData.items.length === 0" class="note" :data-testid="`messages-empty-${activeWindowData.key}`">
            {{ activeWindowData.label }}内没有符合条件的消息。
          </p>
          <ol v-else class="digest" :data-testid="`messages-${activeWindowData.key}`">
            <DigestRow
              v-for="item in activeWindowData.items"
              :key="item.id"
              :item="item"
              :translation-reason="translationReason"
            />
          </ol>
        </div>
      </div>

      <details v-if="lastFetch" class="row-details" :data-testid="field('digest.last_fetch')">
        <summary>上次抓取报告（{{ displayStamp(lastFetch.fetched_at) ?? '时间未知' }}）</summary>
        <DigestFetchReport :report="lastFetch" />
      </details>
    </div>
  </section>
</template>

<style scoped>
.messages__panel {
  margin-top: 12px;
}
</style>
