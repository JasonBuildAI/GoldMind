<script setup lang="ts">
import FooterBar from '@/layout/FooterBar.vue'
import AppSidebar from '@/layout/AppSidebar.vue'
import { useMarketStore } from '@/stores/market'
import { TESTIDS } from '@/testids'
import { onBeforeUnmount, onMounted } from 'vue'

import ConclusionSection from './ConclusionSection.vue'
import DataMethodsSection from './DataMethodsSection.vue'
import DriversSection from './DriversSection.vue'
import MarketSection from './MarketSection.vue'
import QuantSection from './QuantSection.vue'
import StrategySection from './StrategySection.vue'

/**
 * 看板阅读顺序（自上而下，唯一入口）：
 *   左侧栏（字标 + 锚点导航 + 今日速览 + 数据新鲜度）
 *   → 今日结论 → 行情 → 驱动（看涨 / 看跌 / 消息 / 机构）
 *   → 量化预测 → 投资策略 → 数据与方法 → 页脚
 *
 * 顺序即优先级：最重要的结论在最上面，不必让读者先读方法再读结论。
 *
 * 版式是「左栏 + 内容区」两栏（`.app-shell`）：左栏常驻可见，内容区
 * 把剩余宽度全部吃掉（整页铺满），宽屏上表格与图表能一次看全。
 *
 * `autoPoll` 默认开启（生产行为不变）；整页测试把它关掉 —— 否则每个用例
 * 都会留下一个 30 秒的定时器与一组在飞请求，跑到后面的用例时定时器正好
 * 触发，页面被改成「取数失败」，断言随机变红。
 */
const props = withDefaults(defineProps<{ autoPoll?: boolean }>(), { autoPoll: true })

const market = useMarketStore()
let stopPolling: (() => void) | null = null

onMounted(() => {
  if (props.autoPoll) stopPolling = market.startPolling()
})

onBeforeUnmount(() => {
  stopPolling?.()
})
</script>

<template>
  <a class="skip-link no-print" href="#main">跳到主要内容</a>

  <div class="app-shell">
    <AppSidebar variant="dashboard" />

    <div class="app-shell__content">
      <main id="main" class="app-main">
        <div :data-testid="TESTIDS.app">
          <ConclusionSection />
          <MarketSection />
          <DriversSection />
          <QuantSection />
          <StrategySection />
          <DataMethodsSection />
        </div>
      </main>

      <FooterBar />
    </div>
  </div>
</template>
