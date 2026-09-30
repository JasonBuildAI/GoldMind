import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Quant from './Quant'
import { quantApi } from '../services/api'
import type {
  QuantAccuracyRow,
  QuantFactorSnapshot,
  QuantFactorsResponse,
  QuantPredictionItem,
  QuantPredictionsResponse,
} from '../services/api'

vi.mock('../services/api', () => ({
  quantApi: {
    getFactors: vi.fn(),
    getPredictions: vi.fn(),
    getAccuracy: vi.fn(),
    refresh: vi.fn(),
  },
}))

const mocked = vi.mocked(quantApi, true)

function factor(overrides: Partial<QuantFactorSnapshot> & { key: string }): QuantFactorSnapshot {
  return {
    name: overrides.key,
    category: 'monetary',
    category_name: '货币政策与利率',
    weight: 1,
    sign: -1,
    value: 1.23,
    obs_date: '2026-09-30',
    z: 0.5,
    signed_z: -0.5,
    contribution: -0.12,
    status: 'ok',
    reason: null,
    unit: '%',
    source: '美国财政部（TIPS 实际收益率曲线）',
    description: '持有黄金的机会成本。',
    age_days: 1,
    max_age_days: 7,
    ...overrides,
  }
}

const FACTORS: QuantFactorSnapshot[] = [
  factor({ key: 'real_yield_10y', name: '美债 10 年期实际利率' }),
  factor({
    key: 'vix',
    name: 'VIX 波动率指数',
    category: 'risk',
    category_name: '避险与信用',
    sign: 1,
    contribution: 0.2,
    signed_z: 0.8,
    source: 'Yahoo Finance（^VIX）',
  }),
  factor({
    key: 'central_bank',
    name: '央行购金（中国官方储备）',
    category: 'supply',
    category_name: '供需结构',
    sign: 1,
    source: '新浪财经宏观数据',
  }),
  factor({
    key: 'geopolitical',
    name: '地缘风险强度',
    category: 'risk',
    category_name: '避险与信用',
    sign: 1,
    status: 'stale',
    signed_z: null,
    contribution: null,
    age_days: 20,
    max_age_days: 3,
    source: '本系统 RSS 语料（关键词强度代理指标）',
    reason: '最近一条数据是 20 天前，超过该因子的更新周期（3 天）',
  }),
  factor({
    key: 'momentum',
    name: '黄金趋势动量',
    category: 'technical',
    category_name: '市场与技术面',
    sign: 1,
    source: 'Yahoo Finance（GC=F 收盘）',
  }),
]

const FACTOR_RESPONSE: QuantFactorsResponse = {
  model_version: 'quant-v1',
  as_of: '2026-09-30',
  available_factors: 4,
  total_factors: 5,
  categories: [
    { key: 'monetary', name: '货币政策与利率', total: 1, available: 1 },
    { key: 'risk', name: '避险与信用', total: 2, available: 1 },
    { key: 'supply', name: '供需结构', total: 1, available: 1 },
    { key: 'technical', name: '市场与技术面', total: 1, available: 1 },
  ],
  factors: FACTORS,
  sources: [{ name: 'yahoo', label: 'Yahoo Finance 行情', status: 'ok', error: null, reason: null }],
  sync: { started_at: '2026-09-30T12:15:00', finished_at: '2026-09-30T12:16:00', sources_ok: 6, sources_total: 6 },
  unavailable_reason: null,
}

function prediction(overrides: Partial<QuantPredictionItem>): QuantPredictionItem {
  return {
    horizon_days: 1,
    status: 'ok',
    reason: null,
    direction: 'up',
    direction_label: '看涨',
    as_of: '2026-09-30',
    base_price: 4200,
    target_price: 4260,
    expected_return: 0.0143,
    uncertainty: 0.02,
    probability_up: 0.62,
    score: 0.42,
    model_version: 'quant-v1',
    available_factors: 4,
    total_factors: 5,
    factors: [
      {
        key: 'real_yield_10y',
        name: '美债 10 年期实际利率',
        category: 'monetary',
        category_name: '货币政策与利率',
        weight: 1,
        sign: -1,
        value: 1.23,
        obs_date: '2026-09-30',
        z: -0.5,
        signed_z: 0.5,
        contribution: 0.3,
        status: 'ok',
        reason: null,
      },
      {
        key: 'vix',
        name: 'VIX 波动率指数',
        category: 'risk',
        category_name: '避险与信用',
        weight: 0.4,
        sign: 1,
        value: 18.2,
        obs_date: '2026-09-30',
        z: 0.3,
        signed_z: 0.3,
        contribution: 0.12,
        status: 'ok',
        reason: null,
      },
    ],
    ...overrides,
  }
}

const PREDICTION_RESPONSE: QuantPredictionsResponse = {
  model_version: 'quant-v1',
  as_of: '2026-09-30',
  predictions: [
    prediction({ horizon_days: 1 }),
    prediction({
      horizon_days: 5,
      direction: 'down',
      direction_label: '看跌',
      base_price: 4200,
      target_price: 4150,
      expected_return: -0.0119,
      probability_up: 0.38,
      score: -0.31,
    }),
    prediction({
      horizon_days: 20,
      status: 'unavailable',
      reason: '可用因子只有 2 个（至少需要 3 个）',
      direction: null,
      direction_label: null,
      base_price: null,
      target_price: null,
      expected_return: null,
      uncertainty: null,
      probability_up: null,
      score: null,
      available_factors: 2,
      factors: [],
    }),
  ],
}

const ACCURACY_ROW: QuantAccuracyRow = {
  horizon_days: 5,
  evaluated_at: '2026-09-30T12:20:00',
  window_start: '2025-01-02',
  window_end: '2026-09-30',
  sample_size: 780,
  accuracy: 0.621,
  baseline_up_accuracy: 0.54,
  baseline_momentum_accuracy: 0.487,
  brier_score: 0.241,
  metrics: {},
  factors: [
    {
      key: 'real_yield_10y',
      name: '美债 10 年期实际利率',
      category: 'monetary',
      category_name: '货币政策与利率',
      weight: 1,
      sign: -1,
      samples: 780,
      hit_rate: 0.58,
      ic: -0.07,
      rank_ic: -0.06,
    },
  ],
  reason: null,
}

const ACCURACY_RESPONSE = {
  model_version: 'quant-v1',
  latest: [
    { ...ACCURACY_ROW, horizon_days: 1, sample_size: 790 },
    ACCURACY_ROW,
    {
      ...ACCURACY_ROW,
      horizon_days: 20,
      sample_size: 0,
      accuracy: null,
      baseline_up_accuracy: null,
      baseline_momentum_accuracy: null,
      brier_score: null,
      factors: [],
      reason: '可评估样本只有 12 个（至少需要 30 个）',
    },
  ],
  history: [ACCURACY_ROW],
}

function mockApi() {
  mocked.getFactors.mockResolvedValue(FACTOR_RESPONSE)
  mocked.getPredictions.mockResolvedValue(PREDICTION_RESPONSE)
  mocked.getAccuracy.mockResolvedValue(ACCURACY_RESPONSE)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Quant', () => {
  it('渲染选中周期的方向、目标价与上行概率', async () => {
    mockApi()

    render(<Quant />)

    expect(await screen.findByText('量化预测')).toBeInTheDocument()
    // 默认 5 个交易日：接口说看跌，页面必须同时给符号与文字
    expect(screen.getByText('▼ 看跌')).toBeInTheDocument()
    expect(screen.getByText('$4,150.00')).toBeInTheDocument()
    expect(screen.getByText('38%')).toBeInTheDocument()
    expect(screen.getByText('−1.19%')).toBeInTheDocument()
  })

  it('切换周期看得到该周期的结论', async () => {
    mockApi()
    const user = userEvent.setup()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    await user.click(screen.getAllByRole('tab', { name: '1 个交易日' })[0])

    expect(await screen.findByText('▲ 看涨')).toBeInTheDocument()
    expect(screen.getByText('$4,260.00')).toBeInTheDocument()
  })

  it('预测不可用时只给原因，不给方向与数字', async () => {
    mockApi()
    const user = userEvent.setup()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    await user.click(screen.getAllByRole('tab', { name: '20 个交易日' })[0])

    expect(await screen.findByText('20 个交易日的预测不可用')).toBeInTheDocument()
    expect(screen.getByText(/可用因子只有 2 个/)).toBeInTheDocument()
    expect(screen.queryByText('▲ 看涨')).not.toBeInTheDocument()
  })

  it('四类因素表都渲染，并给出数据截至、来源与陈旧原因', async () => {
    mockApi()

    render(<Quant />)

    // 类别名在预测的贡献表里也会出现，所以按每个面板的标题（h3）来认
    expect(await screen.findByRole('heading', { name: '货币政策与利率' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '避险与信用' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '供需结构' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '市场与技术面' })).toBeInTheDocument()

    expect(screen.getByText('美国财政部（TIPS 实际收益率曲线）')).toBeInTheDocument()
    expect(screen.getAllByText(/2026-09-30/).length).toBeGreaterThan(0)
    // 陈旧因子：带标记，并说明为什么没有参与合成
    expect(screen.getByText('陈旧')).toBeInTheDocument()
    expect(screen.getByText(/超过该因子的更新周期（3 天）/)).toBeInTheDocument()
  })

  it('回测把本模型与三个基准并排展示', async () => {
    mockApi()

    render(<Quant />)

    expect(await screen.findByText('回测命中率')).toBeInTheDocument()
    expect(screen.getByText('本模型')).toBeInTheDocument()
    expect(screen.getByText('62.1%')).toBeInTheDocument()
    expect(screen.getByText('永远看多')).toBeInTheDocument()
    expect(screen.getByText('54.0%')).toBeInTheDocument()
    expect(screen.getByText('动量（60 日）')).toBeInTheDocument()
    expect(screen.getByText('抛硬币')).toBeInTheDocument()
    expect(screen.getByText('50.0%')).toBeInTheDocument()
    expect(screen.getByText(/样本 780 个交易日/)).toBeInTheDocument()
  })

  it('接口失败时如实说不可用，不摆内置数字', async () => {
    mocked.getFactors.mockRejectedValue(new Error('boom'))
    mocked.getPredictions.mockRejectedValue(new Error('boom'))
    mocked.getAccuracy.mockRejectedValue(new Error('boom'))

    render(<Quant />)

    expect(await screen.findByText('量化数据不可用')).toBeInTheDocument()
    expect(screen.queryByText(/\$\d/)).not.toBeInTheDocument()
  })

  it('点「重新抓取」会触发一次后端刷新', async () => {
    mockApi()
    mocked.refresh.mockResolvedValue({
      success: true,
      message: 'ok',
      sources: [],
      factor_status: {},
      predictions: [],
      evaluations: [],
    })
    const user = userEvent.setup()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    await user.click(screen.getByRole('button', { name: '重新抓取' }))

    expect(mocked.refresh).toHaveBeenCalledTimes(1)
  })
})
