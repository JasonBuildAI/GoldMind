<script setup lang="ts">
import { displayStamp, formatNumber } from '@/lib/format'
import type { DigestItem } from '@/services/api'
import { fieldTestId } from '@/testids'

/**
 * 一条消息：中文标题 + 中文导语在最上面，英文原题紧随其后；
 * 展开看来源摘要原文、评分依据、事件标注与同题报道。
 *
 * 三件不能妥协的事：
 * 1. 分数与排序全部来自后端确定性评分，这里只展示，不重排、不补算。
 * 2. 中文是**叠加**不是替换：`title_zh` 为空就显示英文标题 + 「中文翻译暂不可用（原因）」，
 *    绝不拼一段中文顶上（`AGENTS.md` 红线 1）。
 * 3. 原文链接一律新窗口打开，并带上可访问名（读屏时知道会跳出去）。
 */
const props = defineProps<{ item: DigestItem; translationReason?: string | null }>()

const field = (path: string) => fieldTestId(path)

/** 这条没有中文时给读者的解释：优先用本条自己的状态，其次用整块翻译状态里的原因。 */
function missingReason(): string {
  if (props.translationReason) return props.translationReason
  return '这来源没有提供摘要，或翻译还没轮到这一条'
}
</script>

<template>
  <li class="digest__item" :data-testid="`message-${item.id}`">
    <div class="digest__head">
      <span class="digest__rank num" :data-testid="field('digest.items.rank')">{{ item.rank }}</span>

      <div class="digest__titles">
        <!-- 有中文：中文当标题，英文原题紧随其后（读者能对上原文，也能核对译文） -->
        <template v-if="item.title_zh">
          <h3 class="digest__title" :data-testid="field('digest.items.title_zh')">
            {{ item.title_zh }}
          </h3>
          <p class="digest__original" :data-testid="field('digest.items.title')">{{ item.title }}</p>
        </template>
        <!-- 没有中文：英文原题就是标题，下面给一句为什么没有中文 -->
        <h3 v-else class="digest__title" :data-testid="field('digest.items.title')">
          {{ item.title }}
        </h3>
      </div>

      <span
        v-if="item.translated"
        class="digest__ai-tag"
        :data-testid="field('digest.items.translated')"
        title="中文标题与导语由模型依据来源标题与摘要生成，原文与摘要在展开区原样保留"
      >
        AI 译
      </span>
    </div>

    <p v-if="item.brief_zh" class="digest__brief" :data-testid="field('digest.items.brief_zh')">
      {{ item.brief_zh }}
    </p>
    <p v-else-if="!item.translated" class="digest__brief note">
      中文翻译暂不可用（{{ missingReason() }}）
    </p>

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
        <p v-if="item.title_zh" class="digest__original-block">
          <span class="digest__label">英文原题</span>
          <span :data-testid="`message-original-title-${item.id}`">{{ item.title }}</span>
        </p>

        <p v-if="item.summary" :data-testid="`message-summary-${item.id}`">
          <span class="digest__label">来源摘要原文</span>
          <span :data-testid="field('digest.items.summary')">{{ item.summary }}</span>
        </p>
        <p v-else class="note">这条消息没有摘要，只保留标题与原文链接。</p>

        <p v-if="item.translated" class="note" :data-testid="`message-translation-${item.id}`">
          中文标题与导语由
          <span :data-testid="field('digest.items.translation_model')">
            {{ item.translation_model || '未知模型' }}
          </span>
          依据上面的英文标题与摘要生成（
          <span :data-testid="field('digest.items.translated_at')">
            {{ displayStamp(item.translated_at) ?? '生成时间未知' }}
          </span>
          ），只压缩原文已有的事实、不添加原文没有的内容；英文标题与摘要原样保留，可逐条核对。
        </p>

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

.digest__titles {
  min-width: 0;
}

/* 英文原题：弱化但始终可见 —— 中文是叠加，不是替换 */
.digest__original {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.digest__brief {
  margin: 4px 0 2px;
  max-width: var(--measure);
}

.digest__ai-tag {
  align-self: flex-start;
  padding: 0 6px;
  background: var(--surface-sunken);
  border-radius: var(--radius-pill);
  color: var(--text-secondary);
  font-size: var(--text-2xs);
  white-space: nowrap;
}

.digest__label {
  display: block;
  color: var(--text-secondary);
  font-size: var(--text-2xs);
}
</style>
