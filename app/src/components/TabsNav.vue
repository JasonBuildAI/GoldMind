<script setup lang="ts">
import { computed, ref } from 'vue'

/**
 * 分段控件（macOS segmented control）+ WAI-ARIA tablist 语义。
 *
 * 之前用的是 Radix Tabs；换成自研是为了去掉 React 依赖，键盘行为按
 * ARIA 规范实现：← → 在标签间移动（自动激活），Home / End 跳到首尾，
 * 只有当前标签在 Tab 序列里（roving tabindex），Tab 键直接进面板。
 *
 * **面板 id 由调用方给**（`panelId`）：同一页面上有多组标签（消息窗口、
 * 五个决策尺度、回测尺度……），id 只用 key 拼会撞车，而重复 id 会让
 * `aria-controls` 指向错误的元素（锚点也会跳错）。调用方用一个稳定前缀
 * 即可，例如 `panel-id="quant-scale"` → `quant-scale-20`。
 */
export interface TabItem {
  key: string
  label: string
}

const props = defineProps<{
  items: readonly TabItem[]
  modelValue: string
  /** 无障碍标签：说明这组标签在切换什么 */
  label: string
  /** 面板 id 前缀；面板元素用 `${panelId}-${key}` 作为 id */
  panelId: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const tabRefs = ref<HTMLButtonElement[]>([])

const tabId = (key: string) => `${props.panelId}-tab-${key}`

const activeIndex = computed(() => {
  const index = props.items.findIndex((item) => item.key === props.modelValue)
  return index < 0 ? 0 : index
})

function select(index: number): void {
  const item = props.items[index]
  if (!item) return
  emit('update:modelValue', item.key)
  // 焦点跟着选中项走：自动激活模式下这是 ARIA 的期望行为
  tabRefs.value[index]?.focus()
}

function onKeydown(event: KeyboardEvent): void {
  const last = props.items.length - 1
  switch (event.key) {
    case 'ArrowRight':
      event.preventDefault()
      select(activeIndex.value === last ? 0 : activeIndex.value + 1)
      break
    case 'ArrowLeft':
      event.preventDefault()
      select(activeIndex.value === 0 ? last : activeIndex.value - 1)
      break
    case 'Home':
      event.preventDefault()
      select(0)
      break
    case 'End':
      event.preventDefault()
      select(last)
      break
    default:
      break
  }
}
</script>

<template>
  <div class="tabs" role="tablist" :aria-label="label" @keydown="onKeydown">
    <button
      v-for="(item, index) in items"
      :key="item.key"
      ref="tabRefs"
      type="button"
      role="tab"
      class="tab"
      :id="tabId(item.key)"
      :aria-selected="item.key === modelValue"
      :aria-controls="`${panelId}-${item.key}`"
      :tabindex="item.key === modelValue ? 0 : -1"
      @click="select(index)"
    >
      {{ item.label }}
    </button>
  </div>
</template>
