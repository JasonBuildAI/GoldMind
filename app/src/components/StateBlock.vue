<script setup lang="ts">
/**
 * 加载 / 正在分析 / 不可用三种状态的统一呈现。
 *
 * 「不可用」必须说清原因与下一步；「正在分析」必须说明当前内容不是本次分析结果。
 * 这里只负责显示，判定逻辑在各区块（依据 `lib/placeholder.ts` 与后端 metadata）。
 */
defineProps<{
  kind?: 'loading' | 'analyzing' | 'unavailable'
  title: string
  detail?: string | null
  testId?: string
}>()
</script>

<template>
  <div
    :class="['state', kind === 'analyzing' ? 'state--analyzing' : '', kind === 'unavailable' ? 'state--unavailable' : '']"
    :data-testid="testId"
    role="status"
  >
    <p class="state__title">{{ title }}</p>
    <p v-if="detail" class="state__detail">{{ detail }}</p>
    <div v-if="$slots.actions" class="state__actions no-print">
      <slot name="actions" />
    </div>
  </div>
</template>
