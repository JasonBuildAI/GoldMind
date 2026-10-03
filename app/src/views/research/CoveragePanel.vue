<script setup lang="ts">
import type { HorizonResearch, ResearchPeriod } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

import CoverageChart from './CoverageChart.vue'
import { diffTone, interval, num, pct, pp } from './researchFormat'

/**
 * 覆盖度：技能总览（五个尺度一行、基准并排）+ 覆盖率柱图 + 四个样本期明细。
 *
 * 三件事不能省：
 * 1. 「留出期」列是**历史**留出期（已被前两轮裁决看过，只作记录），列头必须这么写；
 *    裁决窗口的成绩在「前向留出期」一节，两者不能混着读。
 * 2. 每个格子都有字段级选择器 —— 四个样本期 × 全部字段，少一格都算口径不完整。
 * 3. 算不出来的值写「—」，不补 0（0% 与「没算出来」是两回事）。
 */
const props = defineProps<{ horizons: readonly HorizonResearch[] }>()

const field = (path: string) => fieldTestId(path)

interface SkillRow {
  key: number
  label: string
  headline: string
  developmentAccuracy: string
  /** 样本不足时后端给的原因：挂在单元格 title 上，鼠标悬停可读 */
  developmentReason: string | undefined
  holdoutAccuracy: string
  holdoutReason: string | undefined
  baselineUp: string
  diff: number | null
  pValue: string
  brierSkill: string
  crpsSkill: string
  coverage: string
}

const skillRows = computed<SkillRow[]>(() =>
  props.horizons.map((horizon) => {
    const development = horizon.periods.development
    const holdout = horizon.periods.holdout
    return {
      key: horizon.horizon_days,
      label: horizon.label,
      headline: horizon.headline,
      developmentAccuracy: pct(development?.accuracy),
      developmentReason: development?.reason ?? undefined,
      holdoutAccuracy: pct(holdout?.accuracy),
      holdoutReason: holdout?.reason ?? undefined,
      baselineUp: pct(holdout?.baseline_up_accuracy),
      diff: holdout?.accuracy_diff_vs_up ?? null,
      pValue: num(holdout?.p_value_vs_up),
      brierSkill: num(holdout?.brier_skill_score),
      crpsSkill: num(holdout?.crps_skill_vs_flat),
      coverage: pct(holdout?.interval_coverage_80),
    }
  }),
)

interface PeriodRow {
  key: string
  label: string
  value: (period: ResearchPeriod) => string | number
}

/**
 * 四个样本期 × 全部字段的对照网格：行是字段、列是样本期。
 * 行顺序与后端 `ResearchPeriod` 的字段一一对应，不留空行、不合并同类项。
 */
const PERIOD_ROWS: ReadonlyArray<PeriodRow> = [
  { key: 'label', label: '样本期', value: (period) => period.label },
  { key: 'window_start', label: '窗口起点', value: (period) => period.window_start ?? '—' },
  { key: 'window_end', label: '窗口终点', value: (period) => period.window_end ?? '—' },
  { key: 'sample_size', label: '可评估样本', value: (period) => period.sample_size },
  { key: 'accuracy', label: '命中率', value: (period) => pct(period.accuracy) },
  {
    key: 'baseline_up_accuracy',
    label: '永远看多',
    value: (period) => pct(period.baseline_up_accuracy),
  },
  {
    key: 'baseline_momentum_accuracy',
    label: '动量基准（60 日）',
    value: (period) => pct(period.baseline_momentum_accuracy),
  },
  { key: 'brier_score', label: 'Brier 分数', value: (period) => num(period.brier_score) },
  {
    key: 'brier_skill_score',
    label: 'Brier 技能分',
    value: (period) => num(period.brier_skill_score),
  },
  {
    key: 'brier_skill_p_value',
    label: 'Brier 技能 p 值',
    value: (period) => num(period.brier_skill_p_value),
  },
  { key: 'mean_crps', label: '平均 CRPS', value: (period) => num(period.mean_crps) },
  {
    key: 'crps_skill_vs_flat',
    label: 'CRPS 技能 vs 零漂移',
    value: (period) => num(period.crps_skill_vs_flat),
  },
  {
    key: 'accuracy_diff_vs_up',
    label: '与「永远看多」的差',
    value: (period) => pp(period.accuracy_diff_vs_up),
  },
  {
    key: 'direction_edge_vs_up_ci95',
    label: '方向增量 95% CI',
    value: (period) => interval(period.direction_edge_vs_up_ci95),
  },
  { key: 'down_calls', label: '看空喊话次数', value: (period) => period.down_calls ?? '—' },
  {
    key: 'down_call_accuracy',
    label: '看空命中率',
    value: (period) => pct(period.down_call_accuracy),
  },
  {
    key: 'down_call_edge_vs_up',
    label: '看空相对看多增量',
    value: (period) => pp(period.down_call_edge_vs_up),
  },
  { key: 'accuracy_ci95', label: '命中率 95% CI', value: (period) => interval(period.accuracy_ci95) },
  { key: 'p_value_vs_up', label: 'p 值 vs 看多', value: (period) => num(period.p_value_vs_up) },
  {
    key: 'interval_coverage_80',
    label: '80% 区间覆盖率',
    value: (period) => pct(period.interval_coverage_80),
  },
  {
    key: 'interval_coverage_ci95',
    label: '覆盖率 95% CI',
    value: (period) => interval(period.interval_coverage_ci95),
  },
  {
    key: 'effective_sample_size',
    label: '有效样本量',
    value: (period) => num(period.effective_sample_size, 1),
  },
  { key: 'independent_bets', label: '独立下注', value: (period) => period.independent_bets ?? '—' },
  {
    key: 'independent_bet_stride',
    label: '独立下注步长（交易日）',
    value: (period) => period.independent_bet_stride ?? '—',
  },
  {
    key: 'accuracy_independent_bets',
    label: '独立命中率',
    value: (period) => pct(period.accuracy_independent_bets),
  },
  {
    key: 'interval_coverage_80_independent_bets',
    label: '独立覆盖率',
    value: (period) => pct(period.interval_coverage_80_independent_bets),
  },
  {
    key: 'expected_cap_rate',
    label: '期望封顶比例',
    value: (period) => pct(period.expected_cap_rate),
  },
  { key: 'reason', label: '说明 / 原因', value: (period) => period.reason ?? '—' },
]

interface PeriodColumn {
  /** development / holdout / forward / full —— 字段级选择器的路径段 */
  key: string
  /** 列头用各样本期自己的 label（后端原文） */
  label: string
  period: ResearchPeriod
}

interface PeriodGrid {
  key: number
  label: string
  columns: PeriodColumn[]
}

/** 四个样本期固定顺序：开发 → 历史留出 → 前向留出（裁决）→ 全样本。 */
const periodGrids = computed<PeriodGrid[]>(() =>
  props.horizons.map((horizon) => {
    const periods = horizon.periods
    return {
      key: horizon.horizon_days,
      label: horizon.label,
      columns: [
        { key: 'development', label: periods.development.label, period: periods.development },
        { key: 'holdout', label: periods.holdout.label, period: periods.holdout },
        { key: 'forward', label: periods.forward.label, period: periods.forward },
        { key: 'full', label: periods.full.label, period: periods.full },
      ],
    }
  }),
)
</script>

<template>
  <div class="table-scroll">
    <table class="data-table" :data-testid="TESTIDS.researchOverview">
      <caption class="note">
        命中率 = 方向命中；「差」= 留出期命中率 − 永远看多；Brier 技能分要在 HAC DM
        单尾 p &lt; 0.05 下为正才算显著。这一列的「留出期」是**历史**留出期（已被前两轮
        裁决看过，只作记录）；裁决窗口的成绩见「前向留出期」。CRPS 技能分是整张分布
        （不只涨 / 跌方向）相对「零漂移」基准的改进，&gt; 0 才算给幅度信息加了分。
      </caption>
      <thead>
        <tr>
          <th scope="col">尺度</th>
          <th scope="col" class="num">开发期命中</th>
          <th scope="col" class="num">留出期命中（历史）</th>
          <th scope="col" class="num">永远看多</th>
          <th scope="col" class="num">差</th>
          <th scope="col" class="num">p(&gt;看多)</th>
          <th scope="col" class="num">Brier 技能</th>
          <th scope="col" class="num">CRPS 技能</th>
          <th scope="col" class="num">覆盖率（历史留出）</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in skillRows" :key="row.key">
          <th scope="row">{{ row.label }}<span class="coverage__sub">{{ row.headline }}</span></th>
          <td class="num" :title="row.developmentReason">{{ row.developmentAccuracy }}</td>
          <td class="num" :title="row.holdoutReason">{{ row.holdoutAccuracy }}</td>
          <td class="num">{{ row.baselineUp }}</td>
          <td class="num">
            <span v-if="row.diff === null">—</span>
            <span v-else :class="diffTone(row.diff)">{{ pp(row.diff) }}</span>
          </td>
          <td class="num">{{ row.pValue }}</td>
          <td class="num">{{ row.brierSkill }}</td>
          <td class="num">{{ row.crpsSkill }}</td>
          <td class="num">{{ row.coverage }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="coverage__chart">
    <CoverageChart :horizons="horizons" />
  </div>

  <div class="stack stack--lg coverage__periods" :data-testid="TESTIDS.researchCoverage">
    <div v-for="grid in periodGrids" :key="grid.key" class="factor">
      <details>
        <summary>
          <span class="factor__title">{{ grid.label }} · 四个样本期明细</span>
          <span class="factor__subtitle">开发 / 历史留出 / 前向留出（裁决）/ 全样本；样本不足的格子给出原因。</span>
        </summary>
        <div class="factor__body">
          <div class="table-scroll">
            <table class="data-table">
              <caption class="note">
                「独立下注」= 把逐日样本按尺度（stride = 天数）抽成互不相干的下注后的次数；
                250 日的留出期有几千个重叠样本，却只有个位数次下注，两者不能混着读。
              </caption>
              <thead>
                <tr>
                  <th scope="col">字段</th>
                  <th v-for="column in grid.columns" :key="column.key" scope="col">
                    {{ column.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in PERIOD_ROWS" :key="row.key">
                  <th scope="row">{{ row.label }}</th>
                  <td
                    v-for="column in grid.columns"
                    :key="column.key"
                    :data-testid="field(`research.periods.${column.key}.${row.key}`)"
                  >
                    {{ row.value(column.period) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </div>
  </div>
</template>

<style scoped>
/* 尺度下的补充说明：块级小字，不占表格列宽（对应 React 版的行内 SUB_STYLE） */
.coverage__sub {
  display: block;
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--text-secondary);
}

.coverage__chart {
  margin-top: 18px;
}

.coverage__periods {
  margin-top: 18px;
}
</style>
