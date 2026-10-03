<script setup lang="ts">
import StateBlock from '@/components/StateBlock.vue'
import TabsNav from '@/components/TabsNav.vue'
import { displayStamp, formatPercent, formatShare, formatUsd } from '@/lib/format'
import type { QuantPredictionsResponse } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'
import { computed } from 'vue'

import {
  HORIZONS,
  INTERVAL_ALPHA_TEXT,
  directionClass,
  directionHeadlineText,
  directionText,
  factorTilt,
  horizonLabel,
  statusLabel,
} from './shared'

/**
 * 决策尺度 tab：五个尺度共用一组 tab，切换只改视图，不重新取数。
 * 顶部先把目标价与区间所用的价格口径说清楚。
 *
 * 每个尺度给「一行结论 + 关键数字」，细节收进唯一一层折叠；三情景与逐因子贡献
 * 都是后端算好的值，前端只排版，不重排、不补算。
 */
const props = withDefaults(
  defineProps<{
    predictions: QuantPredictionsResponse
    horizon: string
    /** tabpanel 的 id 前缀：同页有多组尺度标签，id 只用 key 拼会撞车 */
    panelIdPrefix?: string
  }>(),
  { panelIdPrefix: 'quant-scale' },
)

const emit = defineEmits<{ 'update:horizon': [value: string] }>()

const field = (path: string) => fieldTestId(path)

const TAB_ITEMS = HORIZONS.map((days) => ({ key: String(days), label: horizonLabel(days) }))

const ordered = computed(() =>
  [...props.predictions.predictions].sort((left, right) => left.horizon_days - right.horizon_days),
)

/** 当前尺度的预测；接口没返回这个周期时为 null（照实说明，不借用别的尺度）。 */
const active = computed(
  () => ordered.value.find((item) => String(item.horizon_days) === props.horizon) ?? null,
)

/** 一行结论：后端给了 headline 就用它，否则按方向 / 概率 / 目标价拼一句。 */
const headline = computed(() => {
  const item = active.value
  if (!item) return ''
  if (item.headline) return item.headline
  const probability = item.probability_up === null ? '—' : formatShare(item.probability_up * 100, 0)
  return `${horizonLabel(item.horizon_days)} ${directionHeadlineText(item.direction, item.direction_status)}，上行概率 ${probability}，目标价 ${formatUsd(item.target_price)}`
})

/** 逐因子贡献：按贡献绝对值降序，只展示后端算好的值。 */
const contributions = computed(() =>
  [...(active.value?.factors ?? [])].sort(
    (left, right) => Math.abs(right.contribution ?? 0) - Math.abs(left.contribution ?? 0),
  ),
)

/** 本尺度全部模型字段的原始取值；「基准口径」一格两字段（标签 + 代号）。 */
interface RawRow {
  label: string
  path: string
  value: string
  path2?: string
  value2?: string
}

const rawRows = computed<RawRow[]>(() => {
  const item = active.value
  if (!item) return []
  return [
    { label: '尺度', path: 'predictions.scale_label', value: item.scale_label ?? '—' },
    { label: '尺度代号', path: 'predictions.scale', value: item.scale ?? '—' },
    {
      label: '交易日数',
      path: 'predictions.horizon_days',
      value: `${item.horizon_days} 个交易日`,
    },
    {
      label: '主控层',
      path: 'predictions.scale_description',
      value: item.scale_description ?? '—',
    },
    { label: '状态', path: 'predictions.status', value: statusLabel(item.status) },
    { label: '不可用原因', path: 'predictions.reason', value: item.reason ?? '—' },
    {
      label: '基准口径',
      path: 'predictions.base_basis_label',
      value: item.base_basis_label,
      path2: 'predictions.base_basis',
      value2: item.base_basis,
    },
    {
      label: '分布口径',
      path: 'predictions.distribution_mode',
      value:
        item.distribution_mode === null
          ? '—'
          : (INTERVAL_ALPHA_TEXT[item.distribution_mode] ?? item.distribution_mode),
    },
    {
      label: '区间名义水平',
      path: 'predictions.interval_nominal',
      value: item.interval_nominal === null ? '—' : formatShare(item.interval_nominal * 100, 1),
    },
    {
      label: '区间实际水平（1 − α）',
      path: 'predictions.interval_alpha',
      value: item.interval_alpha === null ? '—' : formatShare((1 - item.interval_alpha) * 100, 1),
    },
    {
      label: '期望收益是否被护栏封顶',
      path: 'predictions.expected_capped',
      value: item.expected_capped ? '是（已夹回市场真动过的量级）' : '否',
    },
    { label: '模型版本', path: 'predictions.model_version', value: item.model_version },
  ]
})
</script>

<template>
  <div class="stack" :data-testid="TESTIDS.quantScaleTable">
    <p class="note">
      <template v-if="predictions.price_basis">
        目标价与区间口径：<span :data-testid="field('predictions.price_basis.label')">{{ predictions.price_basis.label }}</span><span class="note" :data-testid="field('predictions.price_basis.basis')">{{ predictions.price_basis.basis }}</span><span :data-testid="field('predictions.price_basis.source')">来源 {{ predictions.price_basis.source }}</span><span :data-testid="field('predictions.price_basis.as_of')">截至 {{ displayStamp(predictions.price_basis.as_of) ?? predictions.price_basis.as_of }}</span>
      </template>
      <span v-else :data-testid="field('predictions.price_basis.label')">价格口径未提供</span>
    </p>

    <TabsNav
      :items="TAB_ITEMS"
      :model-value="horizon"
      label="预测周期"
      :panel-id="panelIdPrefix"
      @update:model-value="emit('update:horizon', $event)"
    />

    <div
      :id="`${panelIdPrefix}-${horizon}`"
      role="tabpanel"
      :aria-labelledby="`${panelIdPrefix}-tab-${horizon}`"
    >
      <StateBlock
        v-if="!active"
        kind="unavailable"
        :title="`${horizonLabel(Number(horizon))}的预测不可用`"
        detail="接口没有返回这个周期。"
      />
      <StateBlock
        v-else-if="active.status !== 'ok'"
        kind="unavailable"
        :test-id="`quant-prediction-unavailable-${active.horizon_days}`"
        :title="`${horizonLabel(active.horizon_days)}的预测不可用`"
        :detail="
          active.reason ??
          '因子数据不足。这里不显示方向与目标价 —— 与其给一个编出来的数，不如如实说明。'
        "
      />

      <div v-else class="stack stack--lg" :data-testid="`quant-prediction-${active.horizon_days}`">
        <p
          class="section__conclusion"
          :data-testid="`quant-prediction-headline-${active.horizon_days}`"
        >
          <span :data-testid="field('predictions.headline')">{{ headline }}</span>
        </p>

        <dl class="metrics">
          <div>
            <dt>方向</dt>
            <dd>
              <!-- 方向停发（not_published）时只给原因，不画箭头 -->
              <span v-if="active.direction_status === 'not_published'" class="note">
                <span :data-testid="field('predictions.direction_status')">{{ statusLabel(active.direction_status) }}</span>：<span :data-testid="field('predictions.direction_reason')">{{ active.direction_reason ?? '后端未说明原因' }}</span>
              </span>
              <span v-else :class="directionClass(active.direction)">
                <span :data-testid="field('predictions.direction')">{{ directionText(active.direction) }}</span><span class="metrics__note" :data-testid="field('predictions.direction_label')">（{{ active.direction_label ?? '后端未给方向标签' }}）</span><span class="metrics__note" :data-testid="field('predictions.direction_status')">{{ statusLabel(active.direction_status) }}</span>
              </span>
              <span class="metrics__note">（校准后的期望收益符号）</span>
            </dd>
          </div>
          <div>
            <dt>上行概率</dt>
            <dd :data-testid="field('predictions.probability_up')">
              {{
                active.probability_up === null
                  ? '不可用（历史样本不足）'
                  : formatShare(active.probability_up * 100, 0)
              }}
            </dd>
          </div>
          <div>
            <dt>基准价</dt>
            <dd class="num" :data-testid="field('predictions.base_price')">
              {{ formatUsd(active.base_price) }}
            </dd>
          </div>
          <div>
            <dt>目标价</dt>
            <dd class="num" :data-testid="field('predictions.target_price')">
              {{ formatUsd(active.target_price) }}
            </dd>
          </div>
          <div>
            <dt>期望收益</dt>
            <dd :data-testid="field('predictions.expected_return')">
              {{ active.expected_return === null ? '—' : formatPercent(active.expected_return * 100) }}<span
                v-if="active.expected_capped"
                class="metrics__note"
                :data-testid="`quant-prediction-capped-${active.horizon_days}`"
              >（已封顶：模型原本想报更夸张的幅度，被护栏夹回市场真动过的量级）</span>
            </dd>
          </div>
          <div>
            <dt>不确定度</dt>
            <dd :data-testid="field('predictions.uncertainty')">
              {{ active.uncertainty === null ? '—' : `±${formatShare(active.uncertainty * 100, 2)}` }}<span
                v-if="active.interval_nominal !== null"
                class="metrics__note"
                :data-testid="`quant-prediction-nominal-${active.horizon_days}`"
              >（名义 {{ formatShare(active.interval_nominal * 100, 1) }}{{ active.distribution_mode === 'normal' ? ' · 正态兜底' : ' · 经验分布' }}）</span>
            </dd>
          </div>
          <div>
            <dt>区间（实际水平）</dt>
            <dd class="num">
              <span :data-testid="field('predictions.range_low')">{{ formatUsd(active.range_low) }}</span> ~ <span :data-testid="field('predictions.range_high')">{{ formatUsd(active.range_high) }}</span>
            </dd>
          </div>
          <div>
            <dt>可用因子</dt>
            <dd>
              <span :data-testid="field('predictions.available_factors')">{{ active.available_factors }}</span> / <span :data-testid="field('predictions.total_factors')">{{ active.total_factors }}</span>
            </dd>
          </div>
          <div>
            <dt>数据截至</dt>
            <dd :data-testid="field('predictions.as_of')">{{ displayStamp(active.as_of) ?? '—' }}</dd>
          </div>
        </dl>

        <p class="note">
          <span>情景说明：</span><span :data-testid="field('predictions.scenario_reason')">{{ active.scenario_reason ?? '—' }}</span>
        </p>

        <!-- 三情景：区间来自预测分布分位数；触发条件出现就改情景，失效条件出现就作废 -->
        <p
          v-if="active.scenarios.length === 0"
          class="note"
          :data-testid="`quant-scenarios-unavailable-${active.horizon_days}`"
        >
          三情景不可用：{{ active.scenario_reason ?? '预测分布或历史样本不足，这里不摆区间。' }}
        </p>
        <div v-else class="table-scroll">
          <table class="data-table">
            <caption class="note">
              三情景由该尺度预测分布的分位数定义：Base 50%、Bull 25%、Bear 25%。
              点位必须带失效条件 —— 触发条件出现就切换情景，失效条件出现就作废。
            </caption>
            <thead>
              <tr>
                <th scope="col">情景</th>
                <th scope="col" class="num">概率</th>
                <th scope="col" class="num">价格区间</th>
                <th scope="col">触发条件</th>
                <th scope="col">失效条件</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in active.scenarios" :key="item.key">
                <th scope="row">
                  <span :data-testid="field('predictions.scenarios.label')">{{ item.label }}</span><span class="note" :data-testid="field('predictions.scenarios.key')">{{ item.key }}</span>
                </th>
                <td class="num" :data-testid="field('predictions.scenarios.probability')">
                  {{ formatShare(item.probability * 100, 0) }}
                </td>
                <td class="num">
                  <template v-if="item.price_low !== null && item.price_high !== null">
                    <span :data-testid="field('predictions.scenarios.price_low')">{{ formatUsd(item.price_low) }}</span> ~ <span :data-testid="field('predictions.scenarios.price_high')">{{ formatUsd(item.price_high) }}</span>
                  </template>
                  <template v-else-if="item.price_low !== null">
                    <span :data-testid="field('predictions.scenarios.price_low')">{{ formatUsd(item.price_low) }}</span> 以上
                  </template>
                  <template v-else-if="item.price_high !== null">
                    <span :data-testid="field('predictions.scenarios.price_high')">{{ formatUsd(item.price_high) }}</span> 以下
                  </template>
                  <template v-else>—</template>
                </td>
                <td class="note" :data-testid="field('predictions.scenarios.trigger')">
                  {{ item.trigger }}
                </td>
                <td class="note" :data-testid="field('predictions.scenarios.invalidation')">
                  {{ item.invalidation }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <details
          class="row-details"
          :data-testid="`quant-prediction-tilt-${active.horizon_days}`"
        >
          <summary>模型字段与口径（含未校准的因子偏向）</summary>
          <p class="note">
            这 {{ active.available_factors }} 个因子按方向对齐加权后的原始倾向：<span :data-testid="field('predictions.score')">{{ factorTilt(active.score) }}</span>（只作对照；方向、概率、目标价与区间都出自校准后的分布，不取它）。
          </p>
          <div class="table-scroll">
            <table class="data-table">
              <caption class="note">本尺度全部模型字段的原始取值与口径，供核对。</caption>
              <thead>
                <tr>
                  <th scope="col">字段</th>
                  <th scope="col">值</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rawRows" :key="row.label">
                  <th scope="row">{{ row.label }}</th>
                  <td>
                    <span :data-testid="field(row.path)">{{ row.value }}</span><span v-if="row.path2" class="note" :data-testid="field(row.path2)">{{ row.value2 }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>

        <!-- 逐因子贡献：只展示后端算好的值，前端不重排、不补算 -->
        <p v-if="contributions.length === 0" class="note">这个尺度没有可展示的因子贡献。</p>
        <div v-else class="table-scroll">
          <table class="data-table" :data-testid="TESTIDS.quantFactorTable">
            <caption class="note">合成得分 {{ active.score === null ? '—' : active.score.toFixed(2) }}（把每个因子的滚动 z 分数按方向对齐后加权平均；缺的因子按剩余权重归一，不会被当成 0）</caption>
            <thead>
              <tr>
                <th scope="col">因子</th>
                <th scope="col">类别</th>
                <th scope="col" class="num">权重</th>
                <th scope="col">数据截至</th>
                <th scope="col" class="num">最新值</th>
                <th scope="col" class="num">z（原始）</th>
                <th scope="col" class="num">方向信号 z</th>
                <th scope="col" class="num">贡献</th>
                <th scope="col">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="factor in contributions" :key="factor.key">
                <th scope="row">
                  <span :data-testid="field('predictions.factors.name')">{{ factor.name }}</span><span class="note" :data-testid="field('predictions.factors.key')">{{ factor.key }}</span>
                </th>
                <td>
                  <span :data-testid="field('predictions.factors.category_name')">{{ factor.category_name }}</span><span class="note" :data-testid="field('predictions.factors.category')">{{ factor.category }}</span>
                </td>
                <td class="num" :data-testid="field('predictions.factors.weight')">
                  {{ factor.weight }}<span class="note" :data-testid="field('predictions.factors.sign')">{{ factor.sign > 0 ? '上升利多' : '上升利空' }}</span>
                </td>
                <td :data-testid="field('predictions.factors.obs_date')">{{ factor.obs_date ?? '—' }}</td>
                <td class="num" :data-testid="field('predictions.factors.value')">
                  {{ factor.value === null ? '—' : factor.value.toFixed(2) }}
                </td>
                <td class="num" :data-testid="field('predictions.factors.z')">
                  {{ factor.z === null ? '—' : factor.z.toFixed(2) }}
                </td>
                <td class="num" :data-testid="field('predictions.factors.signed_z')">
                  {{ factor.signed_z === null ? '—' : factor.signed_z.toFixed(2) }}
                </td>
                <td
                  :class="factor.contribution !== null && factor.contribution < 0 ? 'num is-down' : 'num'"
                  :data-testid="field('predictions.factors.contribution')"
                >
                  {{ factor.contribution === null ? '—' : formatPercent(factor.contribution * 100, 2) }}
                </td>
                <td :data-testid="field('predictions.factors.status')">
                  {{ statusLabel(factor.status) }}<span class="note" :data-testid="field('predictions.factors.reason')">{{ factor.reason ? `（${factor.reason}）` : '—' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p class="provenance">
          方向 = 校准后的期望收益（漂移）符号，与目标价、上行概率、区间、情景出自同一个分布；
          因子偏向（未校准）是这 {{ active.available_factors }} 个因子加权后的原始倾向，收在上面的折叠说明里，
          只作对照，不顶替方向。数据源不可用时该因子不参与，并在因子表里标注原因。
        </p>
      </div>
    </div>
  </div>
</template>
