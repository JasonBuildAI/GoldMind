<script setup lang="ts">
import { PLACEHOLDER_NOTICE } from '@/lib/placeholder'

/**
 * 占位内容提示条。
 *
 * 只在接口明确表示「还在分析、这是占位内容」时渲染 —— 后端缓存未命中时会先返回
 * 一份结构与真实分析完全一样的内置内容，不看 metadata 就分辨不出来。
 */
defineProps<{ show: boolean; testId?: string }>()
</script>

<template>
  <span v-if="show" :data-testid="testId" role="status" class="note">
    {{ PLACEHOLDER_NOTICE }}
  </span>
</template>
