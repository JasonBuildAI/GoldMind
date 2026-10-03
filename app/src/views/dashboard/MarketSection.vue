<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import type { Column } from '@/components/dataTable'
import GoldPriceAsOf from '@/components/GoldPriceAsOf.vue'
import QuoteBlock from '@/components/QuoteBlock.vue'
import SectionBlock from '@/components/SectionBlock.vue'
import StateBlock from '@/components/StateBlock.vue'
import AreaChart from '@/components/charts/AreaChart.vue'
import DualAxisLineChart from '@/components/charts/DualAxisLineChart.vue'
import { useFreshnessBlock } from '@/composables/useFreshnessBlock'
import {
  displayStamp,
  formatNumber,
  formatPercent,
  formatUsd,
  formatUsdCompact,
  trendOf,
} from '@/lib/format'
import { useMarketStore } from '@/stores/market'
import { fieldTestId, TESTIDS } from '@/testids'
import type { CorrelationData, DailyPrice } from '@/services/api'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

/**
 * 行情：一行结论 + 报价表（每个字段都有槽位）在最上，走势图与逐日数据收进
 * 一层折叠。数字一律进表格；口径与来源固定成列。
 */
const market = useMarketStore()
// storeToRefs 而不是直接解构：解构 store 的 state 会丢掉响应性，
// 页面就永远停在首帧的「正在读取行情…」。
const {
  stats,
  statsLoading,
  statsError,
  dailyPrices,
  dailyLoading,
  dailyError,
  correlationData,
  correlationLoading,
  correlationError,
  dollarRealtime,
} = storeToRefs(market)

// 日期是 YYYY-MM-DD，直接按字符串排序 —— 不 new Date()（那是 UTC 解析，
// 东八区凌晨会把交易日算错一天，见 docs/ARCHITECTURE.md 第七节）。
const daily = computed(() =>
  dailyPrices.value
    .map((item: DailyPrice) => ({ date: item.date, value: item.price }))
    .sort((a, b) => a.date.localeCompare(b.date)),
)

const comparison = computed(() =>
  correlationData.value
    .map((item: CorrelationData) => ({
      date: item.date,
      left: item.gold_price,
      right: item.dollar_index,
    }))
    .sort((a, b) => a.date.localeCompare(b.date)),
)

const dailyRows = computed(() => [...dailyPrices.value].sort((a, b) => b.date.localeCompare(a.date)))
const correlationRows = computed(() =>
  [...correlationData.value].sort((a, b) => b.date.localeCompare(a.date)),
)

const chartError = computed(() => dailyError.value ?? correlationError.value)
const chartLoading = computed(() => dailyLoading.value || correlationLoading.value)

useFreshnessBlock(
  'market',
  '行情',
  computed(() => (stats.value ? 'fresh' : statsLoading.value ? 'pending' : 'unavailable')),
  computed(() => stats.value?.price_as_of ?? stats.value?.updated_at ?? null),
)
useFreshnessBlock(
  'dollar',
  '美元指数',
  computed(() => (dollarRealtime.value ? 'fresh' : statsLoading.value ? 'pending' : 'unavailable')),
  computed(() => dollarRealtime.value?.updated_at ?? dollarRealtime.value?.date ?? null),
)

const goldTrend = computed(() => (stats.value ? trendOf(stats.value.window_return) : null))
const dollarTrend = computed(() =>
  dollarRealtime.value ? trendOf(dollarRealtime.value.change_percent) : null,
)

/** 市场状态只决定文字颜色（红涨绿跌），方向本身仍由文字表达。 */
function statusTone(status: string): string {
  if (status.includes('涨')) return 'is-up'
  if (status.includes('跌') || status.includes('回调')) return 'is-down'
  return ''
}

// ---------------------------------------------------------------------------
// 行情快照（全部字段）：每行一个字段，`path` 同时是字段级 testid 的后半段
// 与「口径 / 来源」列里显示的字段名 —— 一处定义，两处使用。
// ---------------------------------------------------------------------------
interface SnapshotRow {
  label: string
  path: string
  value: string
}

const SNAPSHOT_COLUMNS: ReadonlyArray<Column<SnapshotRow>> = [
  { key: 'label', header: '字段' },
  { key: 'value', header: '值' },
  { key: 'path', header: '口径 / 来源' },
]

const snapshotRows = computed<SnapshotRow[]>(() => {
  const value = stats.value
  if (!value) return []
  const rows: SnapshotRow[] = [
    { label: '当前价', path: 'stats.current_price', value: formatUsd(value.current_price) },
    { label: '区间起价', path: 'stats.start_price', value: formatUsd(value.start_price) },
    { label: '区间标签', path: 'stats.window_label', value: value.window_label || '—' },
    { label: '区间起', path: 'stats.window_start', value: value.window_start || '—' },
    { label: '区间末', path: 'stats.window_end', value: value.window_end || '—' },
    { label: '区间涨跌', path: 'stats.window_return', value: formatPercent(value.window_return) },
    { label: '期间最高', path: 'stats.max_price', value: formatUsd(value.max_price) },
    { label: '最高日', path: 'stats.max_date', value: value.max_date || '—' },
    { label: '期间最低', path: 'stats.min_price', value: formatUsd(value.min_price) },
    { label: '最低日', path: 'stats.min_date', value: value.min_date || '—' },
    { label: '高低振幅', path: 'stats.amplitude', value: formatPercent(value.amplitude) },
    { label: '市场状态', path: 'stats.market_status', value: value.market_status || '—' },
    { label: '状态说明', path: 'stats.market_status_desc', value: value.market_status_desc || '—' },
    { label: '数据时间', path: 'stats.updated_at', value: displayStamp(value.updated_at) ?? '—' },
    { label: '数据来源', path: 'stats.data_source', value: value.data_source || '—' },
    {
      label: '是否实时',
      path: 'stats.is_realtime',
      value: value.is_realtime ? '是（实时报价）' : '否（数据库历史）',
    },
    { label: '价格口径', path: 'stats.price_basis', value: value.price_basis || '—' },
    { label: '口径说明', path: 'stats.price_basis_label', value: value.price_basis_label || '—' },
    { label: '口径时间', path: 'stats.price_as_of', value: displayStamp(value.price_as_of) ?? '—' },
  ]

  const dollar = dollarRealtime.value
  if (dollar) {
    // 可空字段一律「有值才格式化，没值就 —」：把 null 当 0 渲染会造出一个
    // 并不存在的报价。
    const nullable = (input: number | null | undefined) =>
      input === null || input === undefined ? '—' : formatNumber(input, 2)
    rows.push(
      { label: '美元指数最新', path: 'dollar.price', value: formatNumber(dollar.price, 2) },
      {
        label: '美元指数前收',
        path: 'dollar.previous_close',
        value: formatNumber(dollar.previous_close, 2),
      },
      { label: '美元指数涨跌', path: 'dollar.change', value: nullable(dollar.change) },
      {
        label: '美元指数涨跌幅',
        path: 'dollar.change_percent',
        value: formatPercent(dollar.change_percent),
      },
      { label: '美元指数开盘', path: 'dollar.open', value: nullable(dollar.open) },
      { label: '美元指数最高', path: 'dollar.high', value: nullable(dollar.high) },
      { label: '美元指数最低', path: 'dollar.low', value: nullable(dollar.low) },
      {
        label: '美元指数时间',
        path: 'dollar.updated_at',
        value: displayStamp(dollar.updated_at) ?? '—',
      },
      { label: '美元指数交易日', path: 'dollar.date', value: dollar.date || '—' },
      { label: '美元指数来源', path: 'dollar.source', value: dollar.source || '—' },
    )
  }
  return rows
})
</script>

<template>
  <SectionBlock
    id="market"
    title="行情"
    intro="纽约黄金与美元指数的当日报价与近期走势；每行都带口径、来源与数据截至。取不到数据时如实说明，不用内置序列顶替。"
  >
    <template v-if="stats" #actions>
      <span class="tag" :title="stats.data_source">
        {{ stats.is_realtime ? '实时报价' : '历史数据' }}
      </span>
    </template>

    <StateBlock v-if="!stats && statsLoading" title="正在读取行情…" />

    <StateBlock
      v-else-if="!stats"
      kind="unavailable"
      :test-id="TESTIDS.marketUnavailable"
      title="金价数据暂不可用"
      :detail="statsError ?? '没能从后端取到行情数据，请稍后重试。'"
    />

    <div v-else class="stack stack--lg" :data-testid="TESTIDS.marketStats">
      <p class="section__conclusion">
        纽约黄金
        <span :data-testid="fieldTestId('stats.current_price')">{{ formatUsd(stats.current_price) }}</span>
        <span :class="statusTone(stats.market_status)">
          （{{ stats.market_status || '状态未知' }}
          <template v-if="goldTrend"> {{ goldTrend.symbol }}{{ goldTrend.label }}</template>
          {{ ` ${formatPercent(stats.window_return)}` }}）
        </span>
        <span class="note">
          区间：{{ stats.window_label }}（{{ stats.window_start }} ~ {{ stats.window_end }}）；
          高低振幅 {{ formatPercent(stats.amplitude) }}。
        </span>
      </p>

      <!-- 结论行里的数字也必须能回答「这是什么时候的价」。
           字段级选择器不在这里重复挂：快照表已经逐字段给过了（同一事实一个槽位）。 -->
      <GoldPriceAsOf
        :as-of="stats.price_as_of ?? stats.updated_at"
        :basis-label="stats.price_basis_label"
        :source="stats.data_source"
      />

      <div class="grid-2">
        <div class="panel">
          <h3 class="panel__title">纽约黄金</h3>
          <QuoteBlock
            label="最新价格"
            :value="formatUsd(stats.current_price)"
            :change="stats.window_return"
            :change-note="stats.window_label"
            :title="stats.data_source"
          >
            <template #meta>
              <GoldPriceAsOf
                :as-of="stats.price_as_of ?? stats.updated_at"
                :basis-label="stats.price_basis_label"
                :source="stats.data_source"
              />
            </template>
          </QuoteBlock>
          <div :data-testid="TESTIDS.goldQuote" class="note">
            {{ stats.is_realtime ? '实时报价' : '历史数据' }} · 口径 {{ stats.price_basis_label || '—' }}
          </div>
        </div>

        <div class="panel">
          <h3 class="panel__title">美元指数</h3>
          <template v-if="dollarRealtime">
            <QuoteBlock
              label="最新报价"
              :value="formatNumber(dollarRealtime.price, 2)"
              :change="dollarRealtime.change_percent"
              change-note="较前收"
              :meta="`数据来源：${dollarRealtime.source || '未知'} · 数据时间：${displayStamp(dollarRealtime.updated_at) ?? '未知'}`"
            />
            <div :data-testid="TESTIDS.dollarQuote" class="note">
              交易日 {{ dollarRealtime.date || '—' }}
              <template v-if="dollarTrend"> · 方向 {{ dollarTrend.symbol }}{{ dollarTrend.label }}</template>
            </div>
          </template>
          <StateBlock v-else title="美元指数暂不可用" detail="没能取到实时美元指数。" />
        </div>
      </div>

      <div class="panel">
        <h3 class="panel__title">行情快照（全部字段）</h3>
        <DataTable
          test-id="market-snapshot-table"
          :rows="snapshotRows"
          :columns="SNAPSHOT_COLUMNS"
          :row-key="(row) => row.path"
        >
          <template #value="{ row }">
            <span :data-testid="fieldTestId(row.path)">{{ row.value }}</span>
          </template>
          <template #path="{ row }">
            <span class="note">{{ row.path }}</span>
          </template>
        </DataTable>
        <p class="provenance">
          报价来自数据源，历史序列来自数据库；两者取不到时本页不显示替代数据。
          价格口径的完整图例见「数据与方法」一节。
        </p>
      </div>

      <details class="row-details" :data-testid="TESTIDS.marketChart">
        <summary>
          展开走势图与逐日数据（{{ dailyRows.length }} 个交易日 / {{ correlationRows.length }} 个对比点）
        </summary>

        <div class="stack stack--lg market__details">
          <StateBlock
            v-if="daily.length === 0"
            :kind="chartError ? 'unavailable' : 'loading'"
            test-id="market-daily-unavailable"
            :title="chartError ? '价格数据暂不可用' : '正在读取价格数据…'"
            :detail="chartError ?? (chartLoading ? null : '后端还没有可用的历史行情。')"
          />
          <AreaChart
            v-else
            :points="daily"
            label="纽约黄金"
            :format-value="formatUsdCompact"
            :height="300"
          >
            <template #caption>最近 {{ daily.length }} 个交易日 · 来源：{{ stats.data_source }}</template>
          </AreaChart>

          <StateBlock
            v-if="comparison.length === 0"
            :kind="chartError ? 'unavailable' : 'loading'"
            test-id="market-comparison-unavailable"
            :title="chartError ? '价格数据暂不可用' : '正在读取价格数据…'"
            :detail="chartError ?? (chartLoading ? null : '后端还没有可用的历史行情。')"
          />
          <DualAxisLineChart
            v-else
            :points="comparison"
            left-label="纽约黄金"
            right-label="美元指数"
            :format-left="formatUsdCompact"
            :format-right="(value: number) => formatNumber(value, 1)"
            :height="300"
          >
            <template #caption>
              左轴：纽约黄金（美元/盎司）· 右轴：美元指数 · 共 {{ comparison.length }} 个交易日
            </template>
          </DualAxisLineChart>

          <div class="panel">
            <h3 class="panel__title">逐日金价（{{ dailyRows.length }} 行）</h3>
            <div class="table-scroll">
              <table class="data-table" :data-testid="TESTIDS.dailyTable">
                <thead>
                  <tr>
                    <th scope="col">日期</th>
                    <th scope="col" class="num">价格</th>
                    <th scope="col" class="num">成交量</th>
                    <th scope="col">口径</th>
                    <th scope="col">口径说明</th>
                    <th scope="col">来源</th>
                    <th scope="col">数据截至</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in dailyRows" :key="row.date">
                    <th scope="row">
                      <span :data-testid="fieldTestId('daily.date')">{{ row.date }}</span>
                    </th>
                    <td class="num">
                      <span :data-testid="fieldTestId('daily.price')">{{ formatUsd(row.price) }}</span>
                    </td>
                    <td class="num">
                      <span :data-testid="fieldTestId('daily.volume')">
                        {{ formatNumber(row.volume, 0) }}
                      </span>
                    </td>
                    <td>
                      <span :data-testid="fieldTestId('daily.basis')">{{ row.basis ?? '—' }}</span>
                    </td>
                    <td>
                      <span :data-testid="fieldTestId('daily.basis_label')">
                        {{ row.basis_label ?? '—' }}
                      </span>
                    </td>
                    <td class="note">
                      <span :data-testid="fieldTestId('daily.source')">{{ row.source ?? '—' }}</span>
                    </td>
                    <td class="note">
                      <span :data-testid="fieldTestId('daily.as_of')">
                        {{ displayStamp(row.as_of) ?? '—' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="panel">
            <h3 class="panel__title">金价与美元指数对照（{{ correlationRows.length }} 行）</h3>
            <div class="table-scroll">
              <table class="data-table" :data-testid="TESTIDS.correlationTable">
                <thead>
                  <tr>
                    <th scope="col">日期</th>
                    <th scope="col" class="num">金价</th>
                    <th scope="col">金价口径</th>
                    <th scope="col">金价来源</th>
                    <th scope="col" class="num">美元指数</th>
                    <th scope="col">美元口径</th>
                    <th scope="col">美元来源</th>
                    <th scope="col">数据截至</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in correlationRows" :key="row.date">
                    <th scope="row">
                      <span :data-testid="fieldTestId('correlation.date')">{{ row.date }}</span>
                    </th>
                    <td class="num">
                      <span :data-testid="fieldTestId('correlation.gold_price')">
                        {{ formatUsd(row.gold_price) }}
                      </span>
                    </td>
                    <td>
                      <span :data-testid="fieldTestId('correlation.gold_basis')">
                        {{ row.gold_basis ?? '—' }}
                      </span>
                      <span class="note">
                        <span :data-testid="fieldTestId('correlation.gold_basis_label')">
                          {{ row.gold_basis_label ?? '—' }}
                        </span>
                      </span>
                    </td>
                    <td class="note">
                      <span :data-testid="fieldTestId('correlation.gold_source')">
                        {{ row.gold_source ?? '—' }}
                      </span>
                    </td>
                    <td class="num">
                      <span :data-testid="fieldTestId('correlation.dollar_index')">
                        {{ formatNumber(row.dollar_index, 2) }}
                      </span>
                    </td>
                    <td>
                      <span :data-testid="fieldTestId('correlation.dollar_basis')">
                        {{ row.dollar_basis ?? '—' }}
                      </span>
                      <span class="note">
                        <span :data-testid="fieldTestId('correlation.dollar_basis_label')">
                          {{ row.dollar_basis_label ?? '—' }}
                        </span>
                      </span>
                    </td>
                    <td class="note">
                      <span :data-testid="fieldTestId('correlation.dollar_source')">
                        {{ row.dollar_source ?? '—' }}
                      </span>
                    </td>
                    <td class="note">
                      <span :data-testid="fieldTestId('correlation.as_of')">
                        {{ displayStamp(row.as_of) ?? '—' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </details>
    </div>
  </SectionBlock>
</template>

<style scoped>
.market__details {
  margin-top: 12px;
}
</style>
