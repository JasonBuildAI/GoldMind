<script setup lang="ts">
/**
 * 研究简报的一节：锚点、标题、一句话说明、操作区。
 *
 * 层级由留白、字号与发丝线建立 —— 不靠编号与装饰。
 * 每节第一行允许放一句「结论 + 关键数字」（`verdict` 插槽），细节收进
 * 至多一层折叠（`Disclosure`），不允许嵌套两层。
 */
defineProps<{
  id: string
  title: string
  intro?: string
}>()
</script>

<template>
  <section :id="id" class="section" :aria-labelledby="`${id}-title`">
    <div class="section__head">
      <div>
        <h2 :id="`${id}-title`" class="section__title">{{ title }}</h2>
        <p v-if="intro" class="section__intro">{{ intro }}</p>
      </div>
      <div v-if="$slots.actions" class="section__actions no-print">
        <slot name="actions" />
      </div>
    </div>

    <p v-if="$slots.verdict" class="section__verdict">
      <slot name="verdict" />
    </p>

    <slot />
  </section>
</template>
