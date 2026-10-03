<script setup lang="ts">
import SectionBlock from '@/components/SectionBlock.vue'
import { TESTIDS } from '@/testids'

import MessagesPanel from './MessagesPanel.vue'

/**
 * 消息：一等板块（`#messages`）。
 *
 * 为什么把它从「驱动」里搬出来单独成节：消息是**当天的原始事实**，
 * 而多空因素与机构观点是**模型对这些事实的解读**。两者混在一节里时，
 * 侧边栏连一个「消息」入口都没有 —— 想读消息得先知道它在「驱动」下面。
 * 现在它与行情、量化并列，导航直达。
 *
 * 面板本身（取数、三窗口、展开详情、手动抓取）仍然全部在 `MessagesPanel` 里，
 * 这一层只负责「它是一节」这件事。
 */
</script>

<template>
  <SectionBlock
    id="messages"
    title="消息"
    intro="央行 / 通讯社 / 行业机构 / 专业财经的高权威消息，按重要性与置信度确定性排序；24 小时 / 7 天 / 30 天三个窗口各取前 10 条，可展开看摘要、评分依据与同题报道，也可点原文。抓不到就如实显示不可用与原因。"
  >
    <div :data-testid="TESTIDS.sectionMessages">
      <MessagesPanel />
    </div>
  </SectionBlock>
</template>
