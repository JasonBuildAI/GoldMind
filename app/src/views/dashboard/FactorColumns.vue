<script setup lang="ts">
import { TESTIDS } from '@/testids'

import FactorColumn from './FactorColumn.vue'

/**
 * 多空对照：看涨与看跌各一栏，两栏结构完全对称，各自独立取数与刷新。
 *
 * 两栏的锚点 id（`drivers-bullish` / `drivers-bearish`）保留 ——
 * 导航与截图脚本按它定位。
 */
</script>

<template>
  <div class="stack stack--lg">
    <div id="drivers-bullish">
      <FactorColumn side="bullish" heading="看涨因素" :test-id="TESTIDS.bullishFactors" />
    </div>
    <div id="drivers-bearish">
      <FactorColumn side="bearish" heading="看跌因素" :test-id="TESTIDS.bearishFactors" />
    </div>
  </div>
</template>
