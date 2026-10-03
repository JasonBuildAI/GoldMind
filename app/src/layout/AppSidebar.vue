<script setup lang="ts">
import GoldPriceAsOf from '@/components/GoldPriceAsOf.vue'
import { displayStamp, formatNumber, formatPercent, formatUsd, trendOf } from '@/lib/format'
import { FRESHNESS_BLOCKS, FRESHNESS_STATE_LABEL, useFreshnessStore } from '@/stores/freshness'
import { useMarketStore } from '@/stores/market'
import { TESTIDS } from '@/testids'
import { computed } from 'vue'

/**
 * 左侧栏：字标 + 导航 + （看板才有的）今日速览与数据新鲜度。
 *
 * 两个入口共用：`variant="dashboard"` 是看板（带速览与新鲜度），
 * `variant="research"` 是研究页（只有字标、回看板的入口与本节导航）。
 *
 * 为什么用左栏而不是顶部横条：顶部横条只能横向铺开一行元信息，宽屏上大段留白、
 * 窄屏上被挤成两行；竖栏把「今天什么价 / 数据新不新 / 去哪一节」收在一列里
 * 常驻可见，右侧内容区就能把剩余宽度全部拿去看表格与图表。
 *
 * 类名仍叫 `.toolbar`（截图脚本与页面自检脚本按它定位），但它是栏不是条。
 *
 * 时间只展示后端返回的字段，不用浏览器时钟推算「今天」（见
 * docs/ARCHITECTURE.md 第七节）。新鲜度由各区块登记，见 stores/freshness。
 */
const props = withDefaults(defineProps<{ variant?: 'dashboard' | 'research' }>(), {
  variant: 'dashboard',
})

/** 看板导航：全部是页内锚点 + 一个跨页链接。 */
const DASHBOARD_NAV = [
  { href: '#conclusion', label: '今日结论' },
  { href: '#market', label: '行情' },
  { href: '#drivers', label: '驱动' },
  // 消息是一等板块，不是「驱动」下面的一个小块（2026-10-03）
  { href: '#messages', label: '消息' },
  { href: '#quant', label: '量化预测' },
  { href: '#strategy', label: '投资策略' },
  { href: '#data-methods', label: '数据与方法' },
  { href: './research.html', label: '研究' },
]

/**
 * 研究页导航：第一项也是回看板（左栏顶部另有一个显式的返回按钮，
 * 这里保留一项是为了两个入口的导航结构一致）。
 */
const RESEARCH_NAV = [
  { href: './index.html', label: '看板' },
  { href: '#verdict', label: '裁决' },
  { href: '#forward', label: '前向留出期' },
  { href: '#coverage', label: '覆盖度' },
  { href: '#diagnostics', label: '诊断' },
  { href: '#regimes', label: '分段' },
  { href: '#factors', label: '因子' },
  { href: '#benchmarks', label: '基准' },
  { href: '#sync', label: '同步报告' },
]

const NAV = computed(() => (props.variant === 'dashboard' ? DASHBOARD_NAV : RESEARCH_NAV))

const STATE_TONE: Record<string, string> = {
  unavailable: 'is-down',
  stale: 'is-down',
  analyzing: '',
  pending: '',
  fresh: '',
}

const market = useMarketStore()
const freshness = useFreshnessStore()

const gold = computed(() => market.stats)
const dollar = computed(() => market.dollarRealtime)
const goldTrend = computed(() => (gold.value ? trendOf(gold.value.window_return) : null))
const dollarTrend = computed(() => (dollar.value ? trendOf(dollar.value.change_percent) : null))

function toneOf(value: number): string {
  return value > 0 ? 'is-up' : value < 0 ? 'is-down' : ''
}
</script>

<template>
  <header class="toolbar no-print" :data-testid="TESTIDS.header">
    <!--
      返回按钮：研究页是**独立入口**（research.html），没有客户端路由，
      从它回看板只能靠一个普通链接。之前只在导航里放了「看板」一项，
      混在一堆锚点中间既不像返回控件、也不显眼 —— 用户反馈「进研究板块以后
      无法返回主页」。所以这里给一个真正的返回按钮，放在左栏最上面
      （macOS 里返回控件就在左上角），并且带上明确的箭头与文字。
      显式写 ./index.html：`./` 与 `./index.html` 在静态服务下等价，
      但写全文件名在「路径是否以 / 结尾」这类部署差异下没有歧义。
    -->
    <a v-if="variant === 'research'" class="toolbar__back" href="./index.html">
      <span class="toolbar__back-arrow" aria-hidden="true">‹</span>
      返回看板
    </a>

    <div class="toolbar__row">
      <div class="toolbar__brand">
        <!--
          字标本身也是回主页的链接（macOS 的标准做法：点应用名回主页）。
          与上面的返回按钮冗余是有意的 —— 返回这件事值得有两个入口，
          用户反馈过找不到回看板的路。
        -->
        <a class="toolbar__home" href="./index.html">
          <h1 class="toolbar__name">GoldMind</h1>
        </a>
        <span class="toolbar__sub">
          {{ variant === 'dashboard' ? '黄金市场分析' : '量化研究 · 技能评估' }}
        </span>
      </div>
    </div>

    <nav class="toolbar__nav" aria-label="页面导航" :data-testid="TESTIDS.headerNav">
      <a v-for="item in NAV" :key="item.href" :href="item.href">{{ item.label }}</a>
    </nav>

    <!-- 看板才有：今日速览（一行结论 + 关键数字）与数据新鲜度 -->
    <template v-if="variant === 'dashboard'">
      <section class="brief" :data-testid="TESTIDS.todaySummary" aria-label="今日速览">
        <span class="brief__label">今日速览</span>

        <template v-if="gold">
          <p class="brief__price">{{ formatUsd(gold.current_price) }}</p>
          <dl class="brief__facts">
            <div class="brief__fact">
              <dt>近 12 个月</dt>
              <dd :class="toneOf(gold.window_return)">
                <span v-if="goldTrend" aria-hidden="true">{{ goldTrend.symbol }}</span>
                {{ formatPercent(gold.window_return) }}
                <span v-if="goldTrend">（{{ goldTrend.label }}）</span>
              </dd>
            </div>
            <div v-if="dollar" class="brief__fact">
              <dt>美元指数</dt>
              <dd>
                {{ formatNumber(dollar.price, 2) }}
                <span :class="toneOf(dollar.change_percent)">
                  <span v-if="dollarTrend" aria-hidden="true">{{ dollarTrend.symbol }}</span>
                  {{ formatPercent(dollar.change_percent) }}
                </span>
              </dd>
            </div>
          </dl>
          <GoldPriceAsOf
            :as-of="gold.price_as_of ?? gold.updated_at"
            :basis-label="gold.price_basis_label"
            :source="gold.data_source"
          />
        </template>

        <p v-else-if="market.statsError" class="brief__meta">
          行情暂不可用（{{ market.statsError }}）
        </p>
        <p v-else class="brief__meta">行情读取中…</p>
      </section>

      <section class="freshness" :data-testid="TESTIDS.freshnessBar" aria-label="数据新鲜度">
        <span class="brief__label">数据新鲜度</span>
        <span
          :class="['freshness__state', STATE_TONE[freshness.summary.state] ?? '']"
          :data-testid="TESTIDS.freshnessState"
        >
          {{ freshness.summary.label }}
        </span>
        <ul class="freshness__list">
          <li
            v-for="block in FRESHNESS_BLOCKS"
            :key="block.key"
            class="freshness__item"
            :data-testid="`${TESTIDS.freshnessItemPrefix}${block.key}`"
          >
            <span class="freshness__name">{{ block.label }}</span>
            <span class="freshness__stamp">
              {{ displayStamp(freshness.entries[block.key]?.asOf) ?? '时间未知' }}
            </span>
            <span
              :class="[
                'freshness__tag',
                STATE_TONE[freshness.entries[block.key]?.state ?? 'pending'] ?? '',
              ]"
            >
              {{ FRESHNESS_STATE_LABEL[freshness.entries[block.key]?.state ?? 'pending'] }}
            </span>
          </li>
        </ul>
      </section>
    </template>

    <!-- 研究页：只多一行报告生成时间 -->
    <slot name="footer" />
  </header>
</template>

<style scoped>
.brief__facts {
  display: grid;
  gap: 4px;
  margin: 0;
}

.brief__meta {
  font-size: var(--text-2xs);
  color: var(--text-secondary);
}

.freshness {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.freshness__state {
  font-weight: 600;
  color: var(--text);
}

/* 左栏里逐块竖排：一块一行，标签 / 时间 / 状态三段对齐 */
.freshness__list {
  display: grid;
  gap: 3px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.freshness__item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: baseline;
  gap: 8px;
}

.freshness__name {
  color: var(--text);
}

.freshness__stamp {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.freshness__tag {
  padding: 0 6px;
  background: var(--surface-sunken);
  border-radius: var(--radius-pill);
  color: var(--text-secondary);
  white-space: nowrap;
}

/* 窄屏：左栏落成横条，逐块列表回到横排换行，避免占掉半屏高度 */
@media (max-width: 960px) {
  .freshness__list {
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  }
}
</style>
