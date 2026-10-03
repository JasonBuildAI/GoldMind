<script setup lang="ts">
/**
 * 一层折叠。用原生 `<details>`：键盘可用、可打印、无需 JS 状态。
 *
 * 可读性规范要求**最多一层**折叠 —— 不要把本组件放进另一个 Disclosure 的
 * 默认插槽里。`title` 就是 summary 的文字，截图脚本与 e2e 会按它定位
 * （如「展开逐条因子」「展开详情」）。
 */
defineProps<{ title: string; testId?: string }>()
</script>

<template>
  <details class="disclosure" :data-testid="testId">
    <summary>{{ title }}</summary>
    <div class="disclosure__body">
      <slot />
    </div>
  </details>
</template>
