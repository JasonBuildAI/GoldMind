import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ResearchPage from './ResearchPage'
import { quantApi } from '@/services/api'
import type { QuantResearchResponse, ResearchPeriod } from '@/services/api'

vi.mock('@/services/api', () => ({
  quantApi: { getResearch: vi.fn() },
}))

const mocked = vi.mocked(quantApi, true)

function period(overrides: Partial<ResearchPeriod> = {}): ResearchPeriod {
  return {
    label: '留出期',
    window_start: '2023-10-02',
    window_end: '2026-09-30',
    sample_size: 700,
    accuracy: 0.563,
    baseline_up_accuracy: 0.563,
    baseline_momentum_accuracy: 0.55,
    brier_score: 0.24,
    brier_skill_score: -0.02,
    brier_skill_p_value: 0.9,
    mean_crps: 0.021,
    crps_skill_vs_flat: 0.031,
    accuracy_diff_vs_up: 0,
    accuracy_ci95: [0.52, 0.6],
    p_value_vs_up: 0.5,
    interval_coverage_80: 0.789,
    interval_coverage_ci95: [0.75, 0.82],
    effective_sample_size: 140,
    independent_bets: 31,
    independent_bet_stride: 5,
    accuracy_independent_bets: 0.548,
    interval_coverage_80_independent_bets: 0.774,
    direction_edge_vs_up_ci95: [0.4, 0.6],
    down_calls: 10,
    down_call_accuracy: 0.5,
    down_call_edge_vs_up: -0.05,
    expected_cap_rate: 0.1,
    reason: null,
    ...overrides,
  }
}

function response(): QuantResearchResponse {
  return {
    model_version: 'quant-v5',
    status: 'ok',
    reason: null,
    as_of: '2026-10-01',
    data_window: { start: '2025-07-18', end: '2026-10-01', trading_days: 311, years: 1.2 },
    holdout_start: '2023-10-02',
    active_holdout_start: '2026-10-02',
    generated_at: '2026-10-02T10:00:00+08:00',
    cached: false,
    benchmark: {
      key: 'gold_spot_no_roll',
      name: '伦敦金现货（不含展期）',
      note: '现货序列没有换月价差，因此不包含展期收益。',
      alternatives: [
        {
          key: 'gold_futures_roll',
          name: 'COMEX 黄金期货（含展期）',
          note: '期货收益包含换月价差，口径与现货不同。',
          available: false,
          reason: '暂无连续合约序列',
        },
      ],
    },
    regime_candidates: [
      {
        key: 'real_rate_regime',
        name: '实际利率状态',
        series_key: 'real_yield_10y',
        description: '按实际利率水平划分的宏观状态',
        status: 'lab_only',
        note: '仅进研究台，未过前向窗口闸门',
      },
    ],
    verdict: {
      status: 'no_edge',
      label: '无统计优势',
      detail: '留出期没有尺度满足预注册规则 ①/②，按预注册规则保留 quant-v5。',
    },
    horizons: [
      {
        horizon_days: 1,
        label: '1 日',
        headline: '方向 / 校准区间',
        forward_readiness: {
          window_start: '2026-10-02',
          observations: 0,
          independent_bets: 0,
          required_bets: 20,
          decidable: false,
          shortfall_bets: 20,
          approx_trading_days_needed: 20,
        },
        periods: {
          development: period({ label: '开发期', accuracy: 0.522 }),
          holdout: period(),
          forward: period({
            label: '前向留出期（裁决窗口）',
            sample_size: 0,
            accuracy: null,
            accuracy_independent_bets: null,
            interval_coverage_80: null,
            interval_coverage_80_independent_bets: null,
            reason: '可评估样本只有 0 个（至少需要 30 个）',
          }),
          full: period({ label: '全样本', accuracy: 0.528 }),
        },
        reliability_bins: [
          { lo: 0.5, hi: 0.6, count: 120, mean_predicted: 0.55, frequency: 0.52 },
        ],
        factors: [
          {
            key: 'real_yield_10y',
            name: '美债 10 年期实际利率',
            category: 'monetary',
            category_name: '货币政策与利率',
            weight: 1.2,
            sign: -1,
            samples: 700,
            hit_rate: 0.54,
            ic: -0.05,
            rank_ic: -0.04,
            alignment: 0.5,
            alignment_t: 1.2,
            alignment_p_value: 0.2,
            alignment_naive_t: 1.1,
          },
        ],
      },
    ],
  }
}

describe('ResearchPage', () => {
  beforeEach(() => {
    mocked.getResearch.mockReset()
  })

  it('renders the verdict, the skill table and the factor breakdown', async () => {
    mocked.getResearch.mockResolvedValue(response())

    render(<ResearchPage />)

    expect(await screen.findByText('无统计优势')).toBeInTheDocument()
    expect(screen.getByTestId('research-overview')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /覆盖率/ })).toBeInTheDocument()
    expect(screen.getByText('美债 10 年期实际利率')).toBeInTheDocument()
    // 留出期 1 日的命中率与覆盖率都要按接口数字展示
    expect(screen.getAllByText('56.3%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('78.9%').length).toBeGreaterThan(0)
    // 模型版本与样本外起点是裁决的关键字段
    expect(screen.getAllByText('quant-v5').length).toBeGreaterThan(0)
    expect(screen.getAllByText('2023-10-02').length).toBeGreaterThan(0)
    // 裁决窗口：起点、还差多少个交易日、以及「尚不可判」的状态
    expect(screen.getByTestId('research-forward-window')).toBeInTheDocument()
    expect(screen.getAllByText('2026-10-02').length).toBeGreaterThan(0)
    expect(screen.getAllByText('尚不可判').length).toBeGreaterThan(0)
    expect(screen.getAllByText('20').length).toBeGreaterThan(0)
    // 独立下注口径：开发 / 历史留出 / 前向留出 / 全样本，每列各自报次数与 stride
    for (const period of ['development', 'holdout', 'forward', 'full']) {
      expect(
        screen.getByTestId(`field-research.periods.${period}.independent_bets`),
      ).toBeInTheDocument()
    }
    expect(screen.getByTestId('field-research.periods.holdout.independent_bets')).toHaveTextContent(
      '31',
    )
    expect(
      screen.getByTestId('field-research.periods.holdout.accuracy_independent_bets'),
    ).toHaveTextContent('54.8%')
    expect(screen.getAllByText('54.8%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('77.4%').length).toBeGreaterThan(0)
    // CRPS：分布级评分与它对零漂移基准的技能分一起展示
    expect(screen.getAllByText('0.021').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.031').length).toBeGreaterThan(0)
    // 数据窗口显著标注：起止 + 交易日数 + 年数，README 快照对不上时以本页为准
    expect(screen.getByTestId('research-data-window')).toHaveTextContent(
      '2025-07-18 → 2026-10-01 · 311 个交易日 · 约 1.2 年',
    )
    expect(screen.getByText(/对不上时以本页为准/)).toBeInTheDocument()
    // Regime 候选登记：lab_only 只进研究台，不改变线上口径
    expect(screen.getByTestId('research-regimes')).toHaveTextContent('实际利率状态')
    expect(screen.getByTestId('research-regimes')).toHaveTextContent('lab_only')
    expect(screen.getByTestId('research-regimes')).toHaveTextContent('仅进研究台')
  })

  it('shows the honest unavailable state without fabricating numbers', async () => {
    mocked.getResearch.mockResolvedValue({
      ...response(),
      status: 'unavailable',
      reason: '库里还没有因子面板或黄金价格序列（先同步数据，再看研究页）',
      as_of: null,
      data_window: null,
      horizons: [],
      verdict: {
        status: 'unavailable',
        label: '数据不可用',
        detail: '没有可评估的数据，研究页不给出任何技能结论。',
      },
    })

    render(<ResearchPage />)

    expect(await screen.findByText('数据不可用')).toBeInTheDocument()
    expect(
      screen.getByText('库里还没有因子面板或黄金价格序列（先同步数据，再看研究页）'),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('research-overview')).not.toBeInTheDocument()
  })

  it('offers a retry when the request fails', async () => {
    mocked.getResearch.mockRejectedValueOnce(new Error('network down'))
    mocked.getResearch.mockResolvedValueOnce(response())

    render(<ResearchPage />)

    expect(await screen.findByText('研究数据不可用')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByTestId('research-overview')).toBeInTheDocument()
  })
})
