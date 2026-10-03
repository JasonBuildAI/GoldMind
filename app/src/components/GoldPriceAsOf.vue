<script setup lang="ts">
import { displayStamp } from '@/lib/format'
import { fieldTestId } from '@/testids'
import { computed } from 'vue'

/**
 * 金价刷新时间 —— 「这个价是什么时候的」这句话的唯一写法。
 *
 * 为什么必须是一个组件：国际金价在页面上出现在六处（侧边栏今日速览 / 行情节与报价块 /
 * 今日结论「当前价格」/ 投资策略降级快照 / 量化基准价 / 公允价值「市场价」），
 * 只给数字不给时间，读者无法判断「$4,170 是刚才的报价，还是昨天的收盘」。
 * 各写一句的结果一定是各漂各的，所以措辞、缺失时的说法、字段级选择器都在这里定一次。
 *
 * 三条约定：
 * 1. 时间取**这个价格自己的** as-of 字段（`price_as_of` / `snapshot.as_of` / `predictions.as_of`），
 *    不用浏览器时钟、不用页面加载时间顶替（项目红线：时间只走后端字段）。
 * 2. as-of 缺失时如实写「时间未知（后端未返回）」—— 编一个「刚刚」比不给时间更糟。
 * 3. 口径与来源有就一起给：没有口径的价格读者无法与其它数字对照。
 */
const props = withDefaults(
  defineProps<{
    /** 这个价格自己的截至时间；缺失时组件如实写「未知」 */
    asOf?: string | null
    /** 口径中文标签（实时报价 / 日收盘 / 量化基准） */
    basisLabel?: string | null
    /** 来源（人类可读），例如「腾讯财经-纽约黄金」 */
    source?: string | null
    /** 前缀，用于「基准价」这类需要点名的地方 */
    label?: string
    /** 字段级选择器后缀（见 testids.ts 的 field 契约）；不给则不挂 testid */
    asOfField?: string
    basisField?: string
    sourceField?: string
  }>(),
  { asOf: null, basisLabel: null, source: null, label: '', asOfField: '', basisField: '', sourceField: '' },
)

const stamp = computed(() => displayStamp(props.asOf))
</script>

<template>
  <span class="price-asof note">
    {{ label ? `${label} ` : '' }}金价刷新
    <span v-if="stamp" :data-testid="asOfField ? fieldTestId(asOfField) : undefined">{{ stamp }}</span>
    <span v-else :data-testid="asOfField ? fieldTestId(asOfField) : undefined">
      时间未知（后端未返回）
    </span>
    <template v-if="basisLabel">
      · <span :data-testid="basisField ? fieldTestId(basisField) : undefined">{{ basisLabel }}</span>
    </template>
    <template v-if="source">
      · <span :data-testid="sourceField ? fieldTestId(sourceField) : undefined">{{ source }}</span>
    </template>
  </span>
</template>

<style scoped>
.price-asof {
  white-space: normal;
}
</style>
