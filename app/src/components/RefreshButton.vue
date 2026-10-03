<script setup lang="ts">
/**
 * 手动触发一次分析 / 抓取。
 *
 * 按钮文案在「进行中」与动作名之间切换，名称就是动作本身
 * （重新分析 / 重新抓取 / 抓取最新消息），不用「提交」这类抽象词。
 * 进行中时按钮禁用但**可见**（禁用态不能靠消失表达）。
 */
defineProps<{
  busy: boolean
  label: string
  busyLabel?: string
  primary?: boolean
}>()

const emit = defineEmits<{ click: [] }>()
</script>

<template>
  <button
    type="button"
    :class="['btn', 'no-print', { 'btn--primary': primary }]"
    :disabled="busy"
    @click="emit('click')"
  >
    {{ busy ? (busyLabel ?? '分析中…') : label }}
  </button>
</template>
