<script setup lang="ts">
/**
 * 卡片 / 面板：一块有边界的内容。
 *
 * macOS 的层次靠圆角 + 发丝线 + 极轻阴影建立，同级只用一种阴影；
 * `plain` 用于「嵌在卡片里的次级块」，去掉阴影避免阴影叠阴影。
 */
defineProps<{
  title?: string
  /** 面板右上角的状态、口径或时间 */
  meta?: string
  plain?: boolean
  testId?: string
}>()
</script>

<template>
  <div :class="['panel', { 'panel--plain': plain }]" :data-testid="testId">
    <div v-if="title || meta || $slots.head" class="panel__head">
      <h3 v-if="title" class="panel__title">{{ title }}</h3>
      <slot name="head" />
      <span v-if="meta" class="panel__meta">{{ meta }}</span>
    </div>
    <slot />
  </div>
</template>
