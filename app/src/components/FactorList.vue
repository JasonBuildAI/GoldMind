<script setup lang="ts">
import { fieldTestId } from '@/testids'

/** 因子条目在两个方向上的结构一致，这里只声明界面真正会用到的字段。 */
export interface FactorItem {
  id: string
  title: string
  subtitle: string
  description: string
  details: string[]
  impact: string
}

const IMPACT_LABEL: Record<string, string> = {
  high: '高影响',
  medium: '中影响',
  low: '低影响',
}

/**
 * 因子列表：一条因子一行，点开看要点。
 *
 * 用原生 `<details>` —— 键盘、屏幕阅读器与打印都直接可用，不必为「展开」
 * 再写一遍无障碍逻辑。影响程度只给文字（高/中/低），不靠颜色区分。
 * `fieldPrefix` 决定字段级 testid（bullish.items.* / bearish.items.*）。
 */
const props = defineProps<{
  factors: readonly FactorItem[]
  fieldPrefix: 'bullish' | 'bearish'
}>()

const fid = (name: string) => fieldTestId(`${props.fieldPrefix}.items.${name}`)
</script>

<template>
  <ul class="factors">
    <li v-for="factor in factors" :key="factor.id" class="factor" :data-testid="`${fieldPrefix}-factor-${factor.id}`">
      <details>
        <summary>
          <span class="factor__title" :data-testid="fid('title')">{{ factor.title }}</span>
          <span class="tag" :data-testid="fid('impact')">
            {{ IMPACT_LABEL[factor.impact] ?? '中影响' }}
          </span>
          <span class="factor__subtitle" :data-testid="fid('subtitle')">{{ factor.subtitle }}</span>
        </summary>
        <div class="factor__body">
          <p :data-testid="fid('description')">{{ factor.description }}</p>
          <p class="note">
            编号 <span :data-testid="fid('id')">{{ factor.id }}</span>
          </p>
          <ul v-if="factor.details.length > 0" :data-testid="fid('details')">
            <li v-for="(detail, index) in factor.details" :key="`${index}-${detail}`">{{ detail }}</li>
          </ul>
        </div>
      </details>
    </li>
  </ul>
</template>
