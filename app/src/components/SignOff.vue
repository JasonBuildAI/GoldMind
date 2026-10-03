<script setup lang="ts">
import { displayStamp } from '@/lib/format'
import { modelLabel, useAiConfigStore } from '@/stores/aiConfig'
import { computed } from 'vue'

/**
 * 分析区块的署名行：谁生成的、什么时候生成的。
 *
 * 模型名从 `/health` 读（见 stores/aiConfig），分析时间只用后端返回的字段 ——
 * 两者都不许猜。读不到模型名时如实写「模型未知」，不硬编码一个型号。
 */
const props = defineProps<{ generatedAt?: string | null }>()

const store = useAiConfigStore()
void store.load()

const model = computed(() =>
  store.config?.model ? modelLabel(store.config) : '模型未知（/health 未返回）',
)
const stamp = computed(() => displayStamp(props.generatedAt))
</script>

<template>
  <p class="provenance">
    由 {{ model }} 生成<span v-if="stamp"> · 分析时间 {{ stamp }}</span> · 仅供参考
  </p>
</template>
