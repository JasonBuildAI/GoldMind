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
    accuracy_diff_vs_up: 0,
    accuracy_ci95: [0.52, 0.6],
    p_value_vs_up: 0.5,
    interval_coverage_80: 0.789,
    interval_coverage_ci95: [0.75, 0.82],
    effective_sample_size: 140,
    reason: null,
    ...overrides,
  }
}

function response(): QuantResearchResponse {
  return {
    model_version: 'quant-v4',
    status: 'ok',
    reason: null,
    as_of: '2026-10-01',
    holdout_start: '2023-10-02',
    generated_at: '2026-10-02T10:00:00+08:00',
    cached: false,
    verdict: {
      status: 'no_edge',
      label: '无统计优势',
      detail: '留出期没有尺度满足预注册规则 ①/②，按预注册规则保留 quant-v4。',
    },
    horizons: [
      {
        horizon_days: 1,
        label: '1 日',
        headline: '方向 / 校准区间',
        periods: {
          development: period({ label: '开发期', accuracy: 0.522 }),
          holdout: period(),
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
    expect(screen.getAllByText('quant-v4').length).toBeGreaterThan(0)
    expect(screen.getByText('2023-10-02')).toBeInTheDocument()
  })

  it('shows the honest unavailable state without fabricating numbers', async () => {
    mocked.getResearch.mockResolvedValue({
      ...response(),
      status: 'unavailable',
      reason: '库里还没有因子面板或黄金价格序列（先同步数据，再看研究页）',
      as_of: null,
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
