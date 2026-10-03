<script setup lang="ts">
import { displayStamp, formatNumber } from '@/lib/format'
import type { DigestItem } from '@/services/api'
import { fieldTestId } from '@/testids'

/**
 * 一条消息：标题、元信息一行、展开看摘要 / 评分依据 / 事件标注 / 同题报道。
 *
 * 分数与排序全部来自后端确定性评分，这里只展示，不重排、不补算。
 * 原文链接一律新窗口打开，并带上可访问名（读屏时知道会跳出去）。
 */
defineProps<{ item: DigestItem }>()

const field = (path: string) => fieldTestId(path)
</script>

<template>
  <li class="digest__item" :data-testid="`message-${item.id}`">
    <div class="digest__head">
      <span class="digest__rank num" :data-testid="field('digest.items.rank')">{{ item.rank }}</span>
      <h3 class="digest__title" :data-testid="field('digest.items.title')">{{ item.title }}</h3>
    </div>

    <p class="digest__meta">
      <span :data-testid="field('digest.items.source')">{{ item.source }}</span>
      <span :data-testid="field('digest.items.tier_label')">{{ item.tier_label }}</span>
      <span :data-testid="field('digest.items.tier')">
        {{ item.tier_label }}（T{{ item.tier }}）
      </span>
      <span v-if="displayStamp(item.published_at)" :data-testid="field('digest.items.published_at')">
        发布 {{ displayStamp(item.published_at) }}
      </span>
      <span :data-testid="field('digest.items.age_hours')">
        {{ formatNumber(item.age_hours, 1) }} 小时前
      </span>
      <span :data-testid="field('digest.items.importance')">
        重要性 {{ formatNumber(item.importance, 1) }}
      </span>
      <span :data-testid="field('digest.items.confidence')">
        置信度 {{ formatNumber(item.confidence, 1) }}
      </span>
      <span v-if="item.event_labels.length > 0" :data-testid="field('digest.items.event_labels')">
        事件 {{ item.event_labels.join(' / ') }}
      </span>
      <span v-if="item.via_aggregator" :data-testid="field('digest.items.via_aggregator')">
        经聚合入口
      </span>
      <a
        :href="item.url"
        target="_blank"
        rel="noreferrer noopener"
        :aria-label="`原文：${item.title}（新窗口打开）`"
        :data-testid="field('digest.items.url')"
      >
        原文 ↗
      </a>
    </p>

    <details class="digest__details">
      <summary>展开详情</summary>
      <div class="digest__body">
        <p v-if="item.summary" :data-testid="`message-summary-${item.id}`">
          <span :data-testid="field('digest.items.summary')">{{ item.summary }}</span>
        </p>
        <p v-else class="note">这条消息没有摘要，只保留标题与原文链接。</p>

        <dl class="metrics">
          <div>
            <dt>编号 / 排名</dt>
            <dd class="num" :data-testid="field('digest.items.id')">{{ item.id }} / {{ item.rank }}</dd>
          </div>
          <div>
            <dt>同题报道数</dt>
            <dd class="num" :data-testid="field('digest.items.coverage_count')">
              {{ item.coverage_count }}
            </dd>
          </div>
          <div>
            <dt>事件标注</dt>
            <dd :data-testid="field('digest.items.event_tags')">
              {{ item.event_tags.length > 0 ? item.event_tags.join('、') : '—' }}
            </dd>
          </div>
        </dl>

        <div v-if="item.signals.length > 0" class="digest__block">
          <h4 :data-testid="field('digest.items.signals')">评分依据</h4>
          <ul :data-testid="`message-signals-${item.id}`">
            <li v-for="signal in item.signals" :key="signal">{{ signal }}</li>
          </ul>
        </div>

        <div v-if="item.related.length > 0" class="digest__block">
          <h4>同题报道（{{ item.coverage_count }} 家来源）</h4>
          <ul :data-testid="`message-related-${item.id}`">
            <li v-for="related in item.related" :key="related.url">
              <a
                :href="related.url"
                target="_blank"
                rel="noreferrer noopener"
                :data-testid="field('digest.related.title')"
              >
                {{ related.title }}
              </a>
              <span class="digest__related-meta" :data-testid="field('digest.related.source')">
                — {{ related.source }}
                <span v-if="displayStamp(related.published_at)" :data-testid="field('digest.related.published_at')">
                  · {{ displayStamp(related.published_at) }}
                </span>
              </span>
              <span class="note" :data-testid="field('digest.related.url')">{{ related.url }}</span>
            </li>
          </ul>
        </div>
      </div>
    </details>
  </li>
</template>

<style scoped>
.digest__block h4 {
  margin: 10px 0 4px;
  font-size: var(--text-sm);
}
</style>
