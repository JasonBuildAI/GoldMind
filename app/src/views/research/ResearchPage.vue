<script setup lang="ts">
import AppSidebar from '@/layout/AppSidebar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SectionBlock from '@/components/SectionBlock.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useAsyncBlock } from '@/composables/useAsyncBlock'
import { describeApiError } from '@/lib/apiError'
import { displayStamp } from '@/lib/format'
import { quantApi, sourcesApi, type QuantResearchResponse, type SourcesStatusResponse } from '@/services/api'
import { TESTIDS } from '@/testids'
import { computed, ref } from 'vue'

import BenchmarksPanel from './BenchmarksPanel.vue'
import CoveragePanel from './CoveragePanel.vue'
import DiagnosticsPanel from './DiagnosticsPanel.vue'
import FactorBreakdownPanel from './FactorBreakdownPanel.vue'
import ForwardWindowPanel from './ForwardWindowPanel.vue'
import PosteriorPanel from './PosteriorPanel.vue'
import RegimesPanel from './RegimesPanel.vue'
import SyncReportPanel from './SyncReportPanel.vue'
import VerdictPanel from './VerdictPanel.vue'

/**
 * 研究页：版本与裁决 → 前向留出期 → 覆盖度 → 校准诊断 → 分段 → 因子拆解
 * → 基准候选 → 同步报告。顺序即优先级，与 docs/20-前端设计规范.md 第四节一致。
 *
 * 三条诚实规则在这里落地：
 * 1. 裁决只看前向留出期（预注册封板日之后**新增**的观测）；窗口没攒够就写
 *    「尚不可判」并给出还差多少个交易日 —— 不写「失败」，也不拿历史留出期顶替。
 * 2. 状态不是 ok 时整页降级：只显示后端给的原因，不摆任何替代数字。
 * 3. 研究数字与数据源状态是两条独立链路：数据源挂了只让「同步报告」少一块，
 *    不影响上面的技能面板。
 *
 * 版式与看板一致（`.app-shell` 两栏）：导航、回看板入口与报告生成时间在左栏，
 * 内容区铺满。这是独立的多页入口（research.html），没有客户端路由 ——
 * 左栏的「看板」是回 index.html 的普通链接。
 */

/** 技能指标是走查式回测，后端算一次约数秒并缓存 1 小时，超时给足。 */
const { data, loading, refreshing, error, load } = useAsyncBlock<QuantResearchResponse>(
  async () => quantApi.getResearch(),
  { fallback: '研究数据加载失败。', timeout: '研究计算超时，请稍后重试。' },
)

const sources = ref<SourcesStatusResponse | null>(null)
const sourcesError = ref<string | null>(null)

/** 数据源状态单独取：它失败不阻塞研究页，只是同步报告如实写原因。 */
async function loadSources(): Promise<void> {
  try {
    sources.value = await sourcesApi.getStatus()
    sourcesError.value = null
  } catch (err) {
    sourcesError.value = describeApiError(err, { fallback: '数据源状态加载失败。' })
  }
}

void load()
void loadSources()

const stamp = computed(() => (data.value ? displayStamp(data.value.generated_at) : null))
</script>

<template>
  <a class="skip-link no-print" href="#main">跳到主要内容</a>

  <div class="app-shell">
    <AppSidebar variant="research">
      <template #footer>
        <p v-if="stamp" class="research__stamp">报告生成：{{ stamp }}</p>
      </template>
    </AppSidebar>

    <div class="app-shell__content">
      <main id="main" class="app-main">
        <section v-if="loading" class="section">
          <StateBlock
            kind="analyzing"
            title="正在计算技能指标…"
            detail="技能指标是走查式回测，首次约数秒；结果缓存 1 小时。"
          />
        </section>

        <section v-else-if="error" class="section">
          <StateBlock kind="unavailable" title="研究数据不可用" :detail="error">
            <template #actions>
              <RefreshButton :busy="refreshing" label="重试" @click="load()" />
            </template>
          </StateBlock>
        </section>

        <!-- 接口说不可用就整页降级：只显示后端给的原因，不摆任何技能数字 -->
        <section v-else-if="data && data.status !== 'ok'" class="section">
          <StateBlock
            kind="unavailable"
            :test-id="TESTIDS.researchVerdict"
            :title="data.verdict.label"
            :detail="data.reason ?? data.verdict.detail"
          />
        </section>

        <template v-else-if="data">
          <SectionBlock
            id="verdict"
            title="版本与裁决"
            intro="先看裁决：裁决只看前向留出期（预注册封板之后的观测）；窗口没攒够就说「尚不可判」，还差多少个交易日一并摊开。"
          >
            <VerdictPanel :data="data" />
          </SectionBlock>

          <SectionBlock
            id="forward"
            title="前向留出期（裁决窗口）"
            intro="预注册封板日之后新增的观测才干净：这一段够不够判、还差多少，是「为什么现在没有结论」的唯一答案；Beta 后验给同口径的证据。"
          >
            <ForwardWindowPanel :horizons="data.horizons" />
            <div class="research__block">
              <h3 class="panel__title">Beta 后验与 CRPS</h3>
              <PosteriorPanel :horizons="data.horizons" />
            </div>
          </SectionBlock>

          <SectionBlock
            id="coverage"
            title="覆盖度"
            intro="五个尺度的方向命中率、基准对照、Brier 与 CRPS 技能分、区间覆盖率；数字全部来自走查式回测。"
          >
            <CoveragePanel :horizons="data.horizons" />
          </SectionBlock>

          <SectionBlock
            id="diagnostics"
            title="校准诊断"
            intro="把预测概率分成十桶，比较「平均预测」与「实际频率」——两者差距越小，概率越可信。"
          >
            <DiagnosticsPanel :horizons="data.horizons" />
          </SectionBlock>

          <SectionBlock
            id="regimes"
            title="分段与 Regime 候选"
            intro="第四轮 Regime 候选登记表：lab_only 只进研究台；过前向窗口闸门之前不应出现别的取值。"
          >
            <RegimesPanel :regimes="data.regime_candidates" />
          </SectionBlock>

          <SectionBlock
            id="factors"
            title="因子拆解"
            intro="逐因子的命中率、IC 与「永远看多」对齐度（HAC t / p）。低命中率不是丢脸的指标，是下一轮候选的线索。"
          >
            <FactorBreakdownPanel :horizons="data.horizons" />
          </SectionBlock>

          <SectionBlock
            id="benchmarks"
            title="基准候选"
            intro="研究基准的口径（含不含展期）与对照候选：口径提示必须让读者知道收益里有没有换月价差。"
          >
            <BenchmarksPanel :benchmark="data.benchmark" />
          </SectionBlock>

          <SectionBlock
            id="sync"
            title="同步报告"
            intro="本页数字依赖的数据源最近一次同步：状态、时间与错误原文；不可用时不补数字。"
          >
            <SyncReportPanel :sources="sources" :error="sourcesError" />
          </SectionBlock>
        </template>
      </main>

      <footer class="footer">
        <div class="wrap footer__bottom">GoldMind · 量化研究页 · MIT License</div>
      </footer>
    </div>
  </div>
</template>

<style scoped>
/* 报头里的报告生成时间：小字、次要色（与 React 版 masthead__stamp 一致） */
.research__stamp {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

/* 同一节里的第二块内容：与上一块拉开 18px */
.research__block {
  margin-top: 18px;
}
</style>
