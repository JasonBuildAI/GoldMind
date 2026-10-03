<script setup lang="ts">
import type { InvestmentStrategy } from '@/services/api'
import { fieldTestId } from '@/testids'

const RISK_LABEL: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

const TYPE_LABEL: Record<string, string> = {
  conservative: '保守',
  balanced: '均衡',
  opportunistic: '机会',
}

/**
 * 三档策略（保守 / 均衡 / 机会）横向对照。
 *
 * 每档的字段完全同名同序 —— 读的时候可以横向比，而不是在三种卡片设计里找。
 * 窄屏落成单栏（`.grid-3` 在 720px 以上才并排）。
 */
defineProps<{
  strategies: readonly InvestmentStrategy[]
  testId?: string
}>()

/** 一行「标签 + 值」；value 为空也保留槽位，显示「—」。 */
const ENTRY_ROWS = [
  { label: '当前评估', key: 'current_price_assessment' },
  { label: '建议区间', key: 'recommended_entry_range' },
  { label: '时机', key: 'entry_timing' },
  { label: '建仓方式', key: 'position_building' },
] as const

const EXIT_ROWS = [
  { label: '止盈目标', key: 'profit_target' },
  { label: '止损', key: 'stop_loss' },
  { label: '再平衡', key: 'rebalancing_trigger' },
] as const

/** 列表为空时保留一个「—」行，避免槽位整块消失。 */
function listOrDash(list: readonly string[] | undefined): string[] {
  return list && list.length > 0 ? [...list] : ['—']
}
</script>

<template>
  <div class="grid-3" :data-testid="testId">
    <article v-for="strategy in strategies" :key="strategy.type" class="panel" :data-testid="`strategy-${strategy.type}`">
      <h3 class="strategy__title" :data-testid="fieldTestId('advice.strategy.title')">
        {{ strategy.title }}
      </h3>
      <p class="strategy__lead" :data-testid="fieldTestId('advice.strategy.description')">
        {{ strategy.description }}
      </p>
      <p class="note">
        <span :data-testid="fieldTestId('advice.strategy.type')">
          类型 {{ strategy.type }}（{{ TYPE_LABEL[strategy.type] ?? '未知' }}）
        </span>
      </p>

      <dl class="strategy__facts">
        <div>
          <dt>仓位</dt>
          <dd :data-testid="fieldTestId('advice.strategy.allocation')">
            {{ strategy.allocation || '—' }}
          </dd>
        </div>
        <div>
          <dt>时间框架</dt>
          <dd :data-testid="fieldTestId('advice.strategy.timeframe')">
            {{ strategy.timeframe || '—' }}
          </dd>
        </div>
        <div>
          <dt>风险</dt>
          <dd :data-testid="fieldTestId('advice.strategy.risk_level')">
            {{ RISK_LABEL[strategy.risk_level] ?? '未知' }}（{{ strategy.risk_level }}）
          </dd>
        </div>
      </dl>

      <div class="strategy__block">
        <h4>入场</h4>
        <dl class="strategy__rows">
          <div v-for="row in ENTRY_ROWS" :key="row.key">
            <dt>{{ row.label }}</dt>
            <dd :data-testid="fieldTestId(`advice.entry.${row.key}`)">
              {{ strategy.entry_strategy?.[row.key] || '—' }}
            </dd>
          </div>
        </dl>
      </div>

      <div class="strategy__block">
        <h4>离场</h4>
        <dl class="strategy__rows">
          <div v-for="row in EXIT_ROWS" :key="row.key">
            <dt>{{ row.label }}</dt>
            <dd :data-testid="fieldTestId(`advice.exit.${row.key}`)">
              {{ strategy.exit_strategy?.[row.key] || '—' }}
            </dd>
          </div>
        </dl>
      </div>

      <div class="strategy__block">
        <h4>优缺点</h4>
        <p class="strategy__label">优点</p>
        <ul class="strategy__list" :data-testid="fieldTestId('advice.strategy.pros')">
          <li v-for="item in listOrDash(strategy.pros)" :key="item">{{ item }}</li>
        </ul>
        <p class="strategy__label">缺点</p>
        <ul class="strategy__list" :data-testid="fieldTestId('advice.strategy.cons')">
          <li v-for="item in listOrDash(strategy.cons)" :key="item">{{ item }}</li>
        </ul>
      </div>

      <div class="strategy__block">
        <h4>适合</h4>
        <ul class="strategy__list" :data-testid="fieldTestId('advice.strategy.suitable_for')">
          <li v-for="item in listOrDash(strategy.suitable_for)" :key="item">{{ item }}</li>
        </ul>
      </div>

      <div class="strategy__block">
        <h4>执行步骤</h4>
        <ol class="strategy__list" :data-testid="fieldTestId('advice.strategy.execution_steps')">
          <li v-for="(step, index) in listOrDash(strategy.execution_steps)" :key="`${index}-${step}`">
            {{ step }}
          </li>
        </ol>
      </div>
    </article>
  </div>
</template>
