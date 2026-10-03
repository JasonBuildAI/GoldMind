<script setup lang="ts">
import type { HorizonResearch } from '@/services/api'
import { fieldTestId, TESTIDS } from '@/testids'

/**
 * 前向裁决窗口：够不够判、还差多少，逐字段给展示位。
 *
 * 裁决只认预注册封板日之后**新增**的观测；窗口没攒够就写「尚不可判」并给出
 * 还差多少个交易日 —— 不拿历史留出期的成绩顶替（见 README「六、回测口径」）。
 * 每一格都挂字段级选择器：少一个字段都算口径不完整。
 */
defineProps<{ horizons: readonly HorizonResearch[] }>()

const field = (path: string) => fieldTestId(path)
</script>

<template>
  <div class="table-scroll">
    <table class="data-table" :data-testid="TESTIDS.researchForwardWindow">
      <caption class="note">
        裁决只认前向留出期：预注册封板日之后**新增**的观测。窗口内的观测按尺度折算成
        互不相干的独立下注，够 20 次才有资格说「有 / 没有优势」；在那之前状态一律是
        「尚不可判」，不用历史留出期的成绩顶替。
      </caption>
      <thead>
        <tr>
          <th scope="col">尺度</th>
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
        <tr v-for="horizon in horizons" :key="horizon.horizon_days">
          <th scope="row">
            <span :data-testid="field('research.horizons.label')">{{ horizon.label }}</span>
            <span class="note" :data-testid="field('research.horizons.horizon_days')">{{ horizon.horizon_days }} 个交易日</span>
            <span class="note" :data-testid="field('research.horizons.headline')">{{ horizon.headline }}</span>
          </th>
          <td :data-testid="field('research.horizons.forward_readiness.window_start')">
            {{ horizon.forward_readiness.window_start }}
          </td>
          <td class="num" :data-testid="field('research.horizons.forward_readiness.observations')">
            {{ horizon.forward_readiness.observations }}
          </td>
          <td class="num" :data-testid="field('research.horizons.forward_readiness.independent_bets')">
            {{ horizon.forward_readiness.independent_bets }}
          </td>
          <td class="num" :data-testid="field('research.horizons.forward_readiness.required_bets')">
            {{ horizon.forward_readiness.required_bets }}
          </td>
          <td class="num" :data-testid="field('research.horizons.forward_readiness.shortfall_bets')">
            {{ horizon.forward_readiness.shortfall_bets }}
          </td>
          <td
            class="num"
            :data-testid="field('research.horizons.forward_readiness.approx_trading_days_needed')"
          >
            {{ horizon.forward_readiness.decidable ? '—' : horizon.forward_readiness.approx_trading_days_needed }}
          </td>
          <td :data-testid="field('research.horizons.forward_readiness.decidable')">
            {{ horizon.forward_readiness.decidable ? '可判' : '尚不可判' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
