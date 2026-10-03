<script setup lang="ts">
import PanelBlock from '@/components/PanelBlock.vue'
import { displayStamp } from '@/lib/format'
import type { QuantResearchResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

/**
 * 版本与裁决：所有顶层字段逐一给展示位。
 *
 * 裁决只看前向留出期；状态不是 ok 时整页诚实降级（见 ResearchPage 的降级分支），
 * 这一块只在 status === 'ok' 时出现。
 * 「数据窗口」是本页所有数字的来源 —— README 与历史报告是各自时点的快照，
 * 两者对不上时以本页为准，这句话必须留在页面上。
 */
const props = defineProps<{ data: QuantResearchResponse }>()

const field = (path: string) => fieldTestId(path)

const stamp = computed(() => displayStamp(props.data.generated_at))
const dataWindow = computed(() => props.data.data_window)
</script>

<template>
  <PanelBlock :test-id="TESTIDS.researchVerdict">
    <template #head>
      <h3 class="panel__title" :data-testid="field('research.verdict.label')">
        {{ data.verdict.label }}
      </h3>
      <span class="tag" :data-testid="field('research.verdict.status')">
        {{ data.verdict.status }}
      </span>
    </template>

    <p class="section__conclusion" :data-testid="field('research.verdict.detail')">
      {{ data.verdict.detail }}
    </p>

    <dl class="metrics">
      <div>
        <dt>模型版本</dt>
        <dd :data-testid="field('research.model_version')">{{ data.model_version }}</dd>
      </div>
      <div>
        <dt>状态</dt>
        <dd :data-testid="field('research.status')">{{ data.status }}</dd>
      </div>
      <div>
        <dt>历史留出期起点</dt>
        <dd :data-testid="field('research.holdout_start')">{{ data.holdout_start }}</dd>
      </div>
      <div>
        <dt>前向留出期起点（裁决窗口）</dt>
        <dd :data-testid="field('research.active_holdout_start')">
          {{ data.active_holdout_start }}
        </dd>
      </div>
      <div>
        <dt>数据截至</dt>
        <dd :data-testid="field('research.as_of')">{{ data.as_of ?? '—' }}</dd>
      </div>
      <div>
        <dt>数据窗口（本页数字来源）</dt>
        <dd :data-testid="TESTIDS.researchDataWindow">
          <!-- 有窗口：起止 + 交易日数 + 年数，三段都给展示位 -->
          <template v-if="dataWindow">
            <span :data-testid="field('research.data_window.start')">{{ dataWindow.start }}</span> →
            <span :data-testid="field('research.data_window.end')">{{ dataWindow.end }}</span> ·
            <span :data-testid="field('research.data_window.trading_days')">{{ dataWindow.trading_days }} 个交易日</span> · 约
            <span :data-testid="field('research.data_window.years')">{{ dataWindow.years }} 年</span>
          </template>
          <!-- 没有窗口：三个字段各自如实写「—」，不拼一个假区间 -->
          <template v-else>
            <span :data-testid="field('research.data_window.start')">—</span><span :data-testid="field('research.data_window.trading_days')">—</span><span :data-testid="field('research.data_window.years')">—</span>
          </template>
        </dd>
      </div>
      <div>
        <dt>报告生成</dt>
        <dd :data-testid="field('research.generated_at')">{{ stamp ?? '—' }}</dd>
      </div>
      <div>
        <dt>本次结果</dt>
        <dd :data-testid="field('research.cached')">
          {{ data.cached ? '来自 1 小时缓存' : '本次现算' }}
        </dd>
      </div>
      <div>
        <dt>不可用原因</dt>
        <dd :data-testid="field('research.reason')">{{ data.reason ?? '—' }}</dd>
      </div>
    </dl>

    <p class="note">
      本页所有数字都基于当前库的这个窗口现算（缓存 1 小时），各样本期的可评估窗口见
      「覆盖度」里的窗口列。README 与历史研究台报告引用的是各自时点的快照 ——
      两者对不上时以本页为准。
    </p>
  </PanelBlock>
</template>
