<script setup lang="ts">
import type { Column } from '@/components/dataTable'
import DataTable from '@/components/DataTable.vue'
import StateBlock from '@/components/StateBlock.vue'
import TabsNav from '@/components/TabsNav.vue'
import { displayStamp, formatShare } from '@/lib/format'
import type {
  QuantAccuracyResponse,
  QuantAccuracyRow,
  QuantFactorPerformance,
  QuantRegimeBlock,
  QuantResearchResponse,
} from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

import { HORIZONS, horizonLabel, interval, num, pct, posteriorRows, pp } from './shared'

/**
 * 回测评估：五个尺度的 tab + 历史评估记录；每个数字都注明口径。
 *
 * 三件事不能省：本模型与基准（永远看多 / 动量 / 抛硬币）并排、CRPS 评整张分布
 * 而不只评涨跌、分段走查逐段给命中率与原因。样本不足就写原因，不摆数字。
 * 前向裁决只认预注册封板日之后的观测，历史留出期不顶替它。
 */
const props = withDefaults(
  defineProps<{
    accuracy: QuantAccuracyResponse
    research: QuantResearchResponse | null
    horizon: string
    /** tabpanel 的 id 前缀：同页有多组尺度标签，id 只用 key 拼会撞车 */
    panelIdPrefix?: string
  }>(),
  { panelIdPrefix: 'quant-accuracy' },
)

const emit = defineEmits<{ 'update:horizon': [value: string] }>()

const field = (path: string) => fieldTestId(path)

const TAB_ITEMS = HORIZONS.map((days) => ({ key: String(days), label: horizonLabel(days) }))

/** 当前尺度的评估行；接口没返回这个周期时为 null（照实说明，不借用别的尺度）。 */
const activeRow = computed(
  () => props.accuracy.latest.find((row) => String(row.horizon_days) === props.horizon) ?? null,
)

/** 技能表一行：字段选择器路径 + 已格式化的值；「抛硬币」没有字段槽位。 */
interface SkillRow {
  label: string
  path: string | null
  value: string
  /** 「评估窗口」这类一格两字段的行 */
  path2?: string
  value2?: string
}

const summaryRows = computed<SkillRow[]>(() => {
  const row = activeRow.value
  if (!row) return []
  const metrics = row.metrics
  const nominal =
    typeof metrics.interval_nominal_80 === 'number' ? metrics.interval_nominal_80 : null
  const coverage =
    typeof metrics.interval_coverage_80 === 'number' ? metrics.interval_coverage_80 : null
  return [
    {
      label: '本模型（校准后的期望收益方向）',
      path: 'accuracy.latest.accuracy',
      value: pct(row.accuracy),
    },
    {
      label: '永远看多',
      path: 'accuracy.latest.baseline_up_accuracy',
      value: pct(row.baseline_up_accuracy),
    },
    {
      label: '动量（60 日）',
      path: 'accuracy.latest.baseline_momentum_accuracy',
      value: pct(row.baseline_momentum_accuracy),
    },
    { label: '抛硬币', path: null, value: '50.0%' },
    {
      label: '与「永远看多」的差',
      path: 'accuracy.metrics.accuracy_diff_vs_up',
      value: pp(metrics.accuracy_diff_vs_up),
    },
    {
      label: 'p 值（vs 永远看多）',
      path: 'accuracy.metrics.p_value_vs_up',
      value: num(metrics.p_value_vs_up),
    },
    {
      label: '命中率 95% 置信区间',
      path: 'accuracy.metrics.accuracy_ci95',
      value: interval(metrics.accuracy_ci95),
    },
    {
      label: '方向增量 95% CI（相对看多，下界 > 0 才算有增量）',
      path: 'accuracy.metrics.direction_edge_vs_up_ci95',
      value: interval(metrics.direction_edge_vs_up_ci95),
    },
    { label: 'Brier 分数', path: 'accuracy.latest.brier_score', value: num(row.brier_score) },
    {
      label: '区间名义水平',
      path: 'accuracy.latest.metrics.interval_nominal_80',
      value: nominal === null ? '—' : formatShare(nominal * 100, 1),
    },
    {
      label: '区间实际覆盖率（80% 名义）',
      path: 'accuracy.latest.metrics.interval_coverage_80',
      value: coverage === null ? '—' : formatShare(coverage * 100, 1),
    },
    {
      label: '区间平均锐度（越小越锐）',
      path: 'accuracy.metrics.interval_sharpness_80',
      value: num(metrics.interval_sharpness_80),
    },
    {
      label: '平均 CRPS（整张分布）',
      path: 'accuracy.metrics.mean_crps',
      value: num(metrics.mean_crps),
    },
    {
      label: '零漂移基准 CRPS',
      path: 'accuracy.metrics.mean_crps_flat',
      value: num(metrics.mean_crps_flat),
    },
    {
      label: 'CRPS 技能分（> 0 才算给幅度加分）',
      path: 'accuracy.metrics.crps_skill_vs_flat',
      value: num(metrics.crps_skill_vs_flat),
    },
    {
      label: 'CRPS 样本',
      path: 'accuracy.metrics.crps_samples',
      value: String(metrics.crps_samples ?? '—'),
    },
    {
      label: '独立下注样本',
      path: 'accuracy.metrics.nonoverlapping_samples',
      value: String(metrics.nonoverlapping_samples ?? '—'),
    },
    {
      label: '独立下注命中率',
      path: 'accuracy.metrics.accuracy_nonoverlapping',
      value: pct(metrics.accuracy_nonoverlapping),
    },
    {
      label: '独立下注覆盖率',
      path: 'accuracy.metrics.coverage_nonoverlapping',
      value: pct(metrics.coverage_nonoverlapping),
    },
    {
      label: '有效样本量',
      path: 'accuracy.metrics.effective_sample_size',
      value: num(metrics.effective_sample_size),
    },
    {
      label: '期望收益被护栏封顶的样本占比',
      path: 'accuracy.metrics.expected_cap_rate',
      value: pct(metrics.expected_cap_rate),
    },
    {
      label: '幅度 MAPE',
      path: 'accuracy.metrics.magnitude_mape',
      value: num(metrics.magnitude_mape),
    },
    {
      label: '幅度技能 vs 零漂移',
      path: 'accuracy.metrics.magnitude_skill_vs_flat',
      value: num(metrics.magnitude_skill_vs_flat),
    },
    {
      label: '看空喊话次数',
      path: 'accuracy.metrics.down_calls',
      value: String(metrics.down_calls ?? '—'),
    },
    {
      label: '看空命中率',
      path: 'accuracy.metrics.down_call_accuracy',
      value: pct(metrics.down_call_accuracy),
    },
    {
      label: '看空相对看多的增量',
      path: 'accuracy.metrics.down_call_edge_vs_up',
      value: pp(metrics.down_call_edge_vs_up),
    },
    { label: '样本量', path: 'accuracy.latest.sample_size', value: String(row.sample_size) },
    {
      label: '评估窗口',
      path: 'accuracy.latest.window_start',
      value: row.window_start ?? '—',
      path2: 'accuracy.latest.window_end',
      value2: row.window_end ?? '—',
    },
    {
      label: '评估时间',
      path: 'accuracy.latest.evaluated_at',
      value: displayStamp(row.evaluated_at) ?? '—',
    },
    { label: '样本不足原因', path: 'accuracy.latest.reason', value: row.reason ?? '—' },
  ]
})

const regimes = computed(() => activeRow.value?.metrics.regimes ?? null)

/**
 * 分段走查的两段：顺序口径照搬 React 版 —— 第一段记 pre、第二段记 post。
 * 只有 post 时它会顶到第一段的位置，这是既有选择器契约的一部分。
 */
const regimeRows = computed(() => {
  const value = regimes.value
  return [value?.pre, value?.post]
    .filter((block): block is QuantRegimeBlock => Boolean(block))
    .map((block, index) => ({ prefix: index === 0 ? 'pre' : 'post', block }))
})

/** 未校准的合成得分方向命中率（只作对照，生产口径是校准后的期望收益方向）。 */
const tilt = computed(() => {
  const value = activeRow.value?.metrics.score_direction_accuracy
  return typeof value === 'number' ? value : null
})

/**
 * 前向裁决：够不够判 + Beta 后验；与历史留出期分开，不互相顶替。
 *
 * 拆成几个 computed 而不是一个联合对象：模板里的 v-if 链要逐项收窄，
 * 独立 computed 的收窄比联合对象的深层属性稳。
 */
const forwardHorizon = computed(() => {
  const research = props.research
  if (!research || research.status !== 'ok') return null
  return research.horizons.find((item) => String(item.horizon_days) === props.horizon) ?? null
})

/** 研究结果整体取不到时的原因；取到了就为 null。 */
const researchReason = computed(() =>
  props.research && props.research.status === 'ok'
    ? null
    : (props.research?.reason ?? '接口没有返回研究结果'),
)

const readiness = computed(() => forwardHorizon.value?.forward_readiness ?? null)
const posterior = computed(() => forwardHorizon.value?.forward_posterior ?? null)

const posteriorTableRows = computed(() => (posterior.value ? posteriorRows(posterior.value) : []))

const FACTOR_COLUMNS: ReadonlyArray<Column<QuantFactorPerformance>> = [
  { key: 'name', header: '因子' },
  { key: 'category', header: '类别' },
  { key: 'weight', header: '权重', numeric: true },
  { key: 'sign', header: '方向' },
  { key: 'hit_rate', header: '单独命中率', numeric: true },
  { key: 'ic', header: 'IC', numeric: true },
  { key: 'rank_ic', header: 'Rank IC', numeric: true },
  { key: 'samples', header: '样本', numeric: true },
]

const HISTORY_COLUMNS: ReadonlyArray<Column<QuantAccuracyRow>> = [
  { key: 'evaluated_at', header: '评估时间' },
  { key: 'horizon', header: '尺度' },
  { key: 'window', header: '评估窗口' },
  { key: 'sample_size', header: '样本', numeric: true },
  { key: 'accuracy', header: '命中率', numeric: true },
  { key: 'brier', header: 'Brier', numeric: true },
  { key: 'crps', header: 'CRPS', numeric: true },
  { key: 'reason', header: '原因' },
]
</script>

<template>
  <div class="stack" :data-testid="TESTIDS.quantAccuracy">
    <p class="note">模型版本 <span :data-testid="field('accuracy.model_version')">{{ accuracy.model_version }}</span>。每个尺度给一行结论与完整指标；没有样本的尺度如实说明，不给数字。</p>

    <TabsNav
      :items="TAB_ITEMS"
      :model-value="horizon"
      label="回测周期"
      :panel-id="panelIdPrefix"
      @update:model-value="emit('update:horizon', $event)"
    />

    <div
      :id="`${panelIdPrefix}-${horizon}`"
      role="tabpanel"
      :aria-labelledby="`${panelIdPrefix}-tab-${horizon}`"
    >
      <StateBlock
        v-if="!activeRow"
        kind="unavailable"
        :title="`${horizonLabel(Number(horizon))}还没有可用的回测`"
        detail="接口没有返回这个周期的评估。"
      />
      <StateBlock
        v-else-if="activeRow.sample_size === 0 || activeRow.accuracy === null"
        kind="unavailable"
        :test-id="`quant-accuracy-unavailable-${activeRow.horizon_days}`"
        :title="`${horizonLabel(activeRow.horizon_days)}还没有可用的回测`"
        :detail="activeRow.reason ?? '样本不足，不给出命中率。'"
      />

      <div v-else class="stack stack--lg" :data-testid="`quant-accuracy-${activeRow.horizon_days}`">
        <p class="section__conclusion"><span :data-testid="field('accuracy.latest.horizon_days')">{{ horizonLabel(activeRow.horizon_days) }}</span>：本模型命中率 <span :data-testid="field('accuracy.latest.accuracy')">{{ pct(activeRow.accuracy) }}</span>，永远看多 <span :data-testid="field('accuracy.latest.baseline_up_accuracy')">{{ pct(activeRow.baseline_up_accuracy) }}</span>，差 <span :data-testid="field('accuracy.metrics.accuracy_diff_vs_up')">{{ pp(activeRow.metrics.accuracy_diff_vs_up) }}</span>（p = <span :data-testid="field('accuracy.metrics.p_value_vs_up')">{{ num(activeRow.metrics.p_value_vs_up) }}</span>，样本 <span :data-testid="field('accuracy.latest.sample_size')">{{ activeRow.sample_size }}</span>）。</p>

        <div class="table-scroll">
          <table class="data-table">
            <caption class="note">
              本模型 = 校准后的期望收益方向；「永远看多」与「动量（60 日）」是并排基准 ——
              不并排给出几个基准，单一命中率没有意义。CRPS 评整张分布，不只评涨 / 跌方向。
            </caption>
            <thead>
              <tr>
                <th scope="col">项目</th>
                <th scope="col" class="num">值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in summaryRows" :key="item.label">
                <th scope="row">{{ item.label }}</th>
                <td class="num"><span v-if="item.path" :data-testid="field(item.path)">{{ item.value }}</span><template v-else>{{ item.value }}</template><template v-if="item.path2"> ~ <span :data-testid="field(item.path2)">{{ item.value2 }}</span></template></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="regimeRows.length > 0" class="table-scroll">
          <table class="data-table">
            <caption class="note">
              分段走查：{{ regimes?.split_date ?? '—' }} 前后各一段；{{ regimes?.note ?? '按市场结构分段复核' }}
            </caption>
            <thead>
              <tr>
                <th scope="col">分段</th>
                <th scope="col" class="num">本模型命中率</th>
                <th scope="col" class="num">永远看多</th>
                <th scope="col" class="num">动量基准（60 日）</th>
                <th scope="col" class="num">样本</th>
                <th scope="col">覆盖时段 / 原因</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="note" :data-testid="field('accuracy.latest.metrics.regimes.split_date')">
                  分段日 {{ regimes?.split_date ?? '—' }}
                </td>
                <td class="note" colspan="4" :data-testid="field('accuracy.latest.metrics.regimes.note')">
                  {{ regimes?.note ?? '—' }}
                </td>
                <td class="note" :data-testid="field('accuracy.latest.metrics.reason')">
                  {{ activeRow.metrics.reason ?? '—' }}
                </td>
              </tr>
              <tr v-for="entry in regimeRows" :key="entry.block.label">
                <th scope="row" :data-testid="field(`accuracy.regimes.${entry.prefix}.label`)">
                  {{ entry.block.label }}
                </th>
                <td class="num" :data-testid="field(`accuracy.regimes.${entry.prefix}.accuracy`)">
                  {{ pct(entry.block.accuracy) }}
                </td>
                <td
                  class="num"
                  :data-testid="field(`accuracy.regimes.${entry.prefix}.baseline_up_accuracy`)"
                >
                  {{ pct(entry.block.baseline_up_accuracy) }}
                </td>
                <td
                  class="num"
                  :data-testid="field(`accuracy.regimes.${entry.prefix}.baseline_momentum_accuracy`)"
                >
                  {{ pct(entry.block.baseline_momentum_accuracy) }}
                </td>
                <td class="num" :data-testid="field(`accuracy.regimes.${entry.prefix}.sample_size`)">
                  {{ entry.block.sample_size }}
                </td>
                <td class="note"><span :data-testid="field(`accuracy.regimes.${entry.prefix}.window_start`)">{{ entry.block.window_start ?? '—' }}</span> ~ <span :data-testid="field(`accuracy.regimes.${entry.prefix}.window_end`)">{{ entry.block.window_end ?? '—' }}</span><span :data-testid="field(`accuracy.regimes.${entry.prefix}.reason`)">{{ entry.block.reason ? `（${entry.block.reason}）` : '' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div>
          <h4>前向裁决（独立下注口径）</h4>

          <p
            v-if="researchReason !== null"
            class="note"
            :data-testid="`quant-accuracy-posterior-${activeRow.horizon_days}`"
          >
            前向裁决数据不可用：{{ researchReason }}。这里不用历史留出期顶替。
          </p>
          <p
            v-else-if="!forwardHorizon"
            class="note"
            :data-testid="`quant-accuracy-posterior-${activeRow.horizon_days}`"
          >
            这个尺度没有研究裁决数据。
          </p>
          <div
            v-else-if="readiness"
            class="stack"
            :data-testid="`quant-accuracy-posterior-${activeRow.horizon_days}`"
          >
            <div class="table-scroll">
              <table class="data-table">
                <caption class="note">
                  裁决只认前向留出期：预注册封板日之后新增的观测，按尺度折算成互不相干的独立下注；
                  够 {{ readiness.required_bets }} 次才有资格下结论。
                </caption>
                <thead>
                  <tr>
                    <th scope="col">窗口起点</th>
                    <th scope="col" class="num">已积累观测</th>
                    <th scope="col" class="num">独立下注</th>
                    <th scope="col" class="num">需要</th>
                    <th scope="col" class="num">还差</th>
                    <th scope="col" class="num">还差约（交易日）</th>
                    <th scope="col">状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td :data-testid="field('research.horizons.forward_readiness.window_start')">
                      {{ readiness.window_start }}
                    </td>
                    <td
                      class="num"
                      :data-testid="field('research.horizons.forward_readiness.observations')"
                    >
                      {{ readiness.observations }}
                    </td>
                    <td
                      class="num"
                      :data-testid="field('research.horizons.forward_readiness.independent_bets')"
                    >
                      {{ readiness.independent_bets }}
                    </td>
                    <td
                      class="num"
                      :data-testid="field('research.horizons.forward_readiness.required_bets')"
                    >
                      {{ readiness.required_bets }}
                    </td>
                    <td
                      class="num"
                      :data-testid="field('research.horizons.forward_readiness.shortfall_bets')"
                    >
                      {{ readiness.shortfall_bets }}
                    </td>
                    <td
                      class="num"
                      :data-testid="field('research.horizons.forward_readiness.approx_trading_days_needed')"
                    >
                      {{ readiness.approx_trading_days_needed }}
                    </td>
                    <td :data-testid="field('research.horizons.forward_readiness.decidable')">
                      {{ readiness.decidable ? '可下结论' : '尚不可判' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Beta 后验：响应模型没透出该字段时如实说明，不摆一个假的后验 -->
            <p
              v-if="!posterior"
              class="note"
              :data-testid="field('research.horizons.forward_posterior.prior')"
            >
              尚无 Beta 后验：接口响应未包含该字段（响应模型未透出）。这里不摆替代数字。
            </p>
            <div v-else class="table-scroll">
              <table class="data-table">
                <caption class="note">
                  Beta 后验按独立下注口径合成（先验 Beta(1,1)），与命中率并排给证据；CRPS 评整张分布，
                  不只评涨 / 跌方向。
                </caption>
                <thead>
                  <tr>
                    <th scope="col">项目</th>
                    <th scope="col" class="num">值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in posteriorTableRows" :key="item.path">
                    <th scope="row">{{ item.label }}</th>
                    <td
                      class="num"
                      :data-testid="field(`research.horizons.forward_posterior.${item.path}`)"
                    >
                      {{ item.value }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <details class="row-details" :data-testid="`quant-accuracy-tilt-${activeRow.horizon_days}`">
          <summary>未校准的因子偏向（对照）与逐因子单独检验</summary>
          <p class="note">未校准的合成得分方向命中率：<span :data-testid="field('accuracy.latest.metrics.score_direction_accuracy')">{{ pct(tilt) }}</span>（只作对照 —— 生产口径是校准后的期望收益方向，不取它）。</p>
          <DataTable
            v-if="activeRow.factors.length > 0"
            :rows="activeRow.factors"
            :columns="FACTOR_COLUMNS"
            :row-key="(factor) => factor.key"
            caption="逐个因子单独检验：命中率低于 50% 说明它的方向先验在这段历史里与实际相反，权重可能失效。"
          >
            <template #name="{ row }">
              <span :data-testid="field('accuracy.factors.name')">{{ row.name }}</span><span class="note" :data-testid="field('accuracy.factors.key')">{{ row.key }}</span>
            </template>
            <template #category="{ row }">
              <span :data-testid="field('accuracy.factors.category_name')">{{ row.category_name }}</span><span class="note" :data-testid="field('accuracy.factors.category')">{{ row.category }}</span>
            </template>
            <template #weight="{ row }">
              <span :data-testid="field('accuracy.factors.weight')">{{ row.weight }}</span>
            </template>
            <template #sign="{ row }">
              <span :data-testid="field('accuracy.factors.sign')">{{ row.sign > 0 ? '上升利多' : '上升利空' }}</span>
            </template>
            <template #hit_rate="{ row }">
              <span :data-testid="field('accuracy.factors.hit_rate')">{{ pct(row.hit_rate) }}</span>
            </template>
            <template #ic="{ row }">
              <span :data-testid="field('accuracy.factors.ic')">{{ num(row.ic, 2) }}</span>
            </template>
            <template #rank_ic="{ row }">
              <span :data-testid="field('accuracy.factors.rank_ic')">{{ num(row.rank_ic, 2) }}</span>
            </template>
            <template #samples="{ row }">
              <span :data-testid="field('accuracy.factors.samples')">{{ row.samples }}</span>
            </template>
          </DataTable>
          <p v-else class="note">没有逐因子回测记录。</p>
        </details>

        <p class="provenance">走查式回测：{{ activeRow.window_start ?? '—' }} ~ {{ activeRow.window_end ?? '—' }}，样本 {{ activeRow.sample_size }} 个交易日{{ activeRow.brier_score === null ? '' : `，Brier 分数 ${activeRow.brier_score.toFixed(3)}` }}，评估时间 {{ displayStamp(activeRow.evaluated_at) ?? '—' }}。命中率不看永远看多这一档 —— 牛市里它天然很高。</p>
      </div>
    </div>

    <details
      v-if="accuracy.history.length > 0"
      class="row-details"
      :data-testid="TESTIDS.quantAccuracyHistory"
    >
      <summary>历史评估记录（{{ accuracy.history.length }} 次）</summary>
      <DataTable
        :rows="accuracy.history"
        :columns="HISTORY_COLUMNS"
        :row-key="(row, index) => `${row.evaluated_at ?? 'record'}-${row.horizon_days}-${index}`"
        caption="每次滚动评估的存档：同一模型在不同时间的成绩，用来看稳定性，不顶替最新一档。"
      >
        <template #evaluated_at="{ row }">
          <span :data-testid="field('accuracy.history.evaluated_at')">{{ displayStamp(row.evaluated_at) ?? '—' }}</span>
        </template>
        <template #horizon="{ row }">
          <span :data-testid="field('accuracy.history.horizon_days')">{{ horizonLabel(row.horizon_days) }}</span>
        </template>
        <template #window="{ row }">
          <span :data-testid="field('accuracy.history.window_start')">{{ row.window_start ?? '—' }}</span> ~ <span :data-testid="field('accuracy.history.window_end')">{{ row.window_end ?? '—' }}</span>
        </template>
        <template #sample_size="{ row }">
          <span :data-testid="field('accuracy.history.sample_size')">{{ row.sample_size }}</span>
        </template>
        <template #accuracy="{ row }">
          <span :data-testid="field('accuracy.history.accuracy')">{{ pct(row.accuracy) }}</span>
        </template>
        <template #brier="{ row }">
          <span :data-testid="field('accuracy.history.brier_score')">{{ num(row.brier_score) }}</span>
        </template>
        <template #crps="{ row }">
          <span :data-testid="field('accuracy.history.mean_crps')">{{ num(row.metrics.mean_crps) }}</span>
        </template>
        <template #reason="{ row }">
          <span :data-testid="field('accuracy.history.reason')">{{ row.reason ?? '—' }}</span>
        </template>
      </DataTable>
    </details>
  </div>
</template>
