<script setup lang="ts">
import { modelLabel, useAiConfigStore } from '@/stores/aiConfig'
import { computed } from 'vue'

/**
 * 页脚：数据来源 / 分析模型 / 免责声明。
 *
 * 只列真实存在的数据来源。机构名称不是数据源 —— 机构观点由模型基于公开新闻
 * 整理，这一句必须在这里说清楚（见 docs/20-前端设计规范.md 第六节）。
 */
const DATA_SOURCES = [
  '实时金价：腾讯财经（纽约黄金期货 GC）',
  '实时美元指数：新浪财经（ICE 美元指数 DXY）',
  '新闻：RSS 源（默认 FXStreet / MarketWatch / CNBC / WSJ，可用 NEWS_RSS_SOURCES 配置）',
]

const aiStore = useAiConfigStore()
void aiStore.load()
const model = computed(() => modelLabel(aiStore.config))
</script>

<template>
  <footer class="footer">
    <div class="wrap grid-3">
      <section aria-labelledby="footer-sources">
        <h2 id="footer-sources">数据来源</h2>
        <ul>
          <li v-for="item in DATA_SOURCES" :key="item">{{ item }}</li>
        </ul>
      </section>

      <section aria-labelledby="footer-model">
        <h2 id="footer-model">分析模型</h2>
        <p class="footer__para">模型：{{ model }}</p>
        <p>
          除机构观点外，分析结果由大模型基于最近 24 小时的公开新闻与行情数据生成；
          机构观点取每家机构最近一次可核实的预测，可能滞后（表内标注预测日期）。
          联网搜索不可用时回退数据库与 RSS 新闻，不编造数据。
        </p>
      </section>

      <section aria-labelledby="footer-disclaimer">
        <h2 id="footer-disclaimer">免责声明</h2>
        <p>
          本页面内容仅供参考，不构成投资建议。投资有风险，入市需谨慎。过往表现不代表未来收益。
        </p>
      </section>
    </div>

    <div class="wrap footer__bottom">GoldMind · MIT License</div>
  </footer>
</template>

<style scoped>
.footer__para {
  margin-bottom: 8px;
}
</style>
