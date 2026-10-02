import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Quant from './Quant'
import { quantApi } from '../services/api'
import type {
  QuantAccuracyRow,
  QuantDecomposition,
  QuantFactorSnapshot,
  QuantFactorsResponse,
  QuantMonitorResponse,
  QuantPredictionItem,
  QuantPredictionsResponse,
  QuantScenario,
} from '../services/api'

vi.mock('../services/api', () => ({
  quantApi: {
    getFactors: vi.fn(),
    getPredictions: vi.fn(),
    getAccuracy: vi.fn(),
    getMonitor: vi.fn(),
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

const SCENARIOS: QuantScenario[] = [
  {
    key: 'base',
    label: '基准情景',
    probability: 0.5,
    price_low: 4150,
    price_high: 4280,
    trigger: 'VIX 方向对齐 z 停留在 ±1 之间，且金价在 [4,150, 4,280] 内震荡',
    invalidation: 'VIX 方向对齐 z 越过 ±1，或金价收盘走出 [4,150, 4,280]',
  },
  {
    key: 'bull',
    label: '看涨情景',
    probability: 0.25,
    price_low: 4280,
    price_high: null,
    trigger: 'VIX 方向对齐 z 维持为正，且金价站上 200 日均线（4,050）',
    invalidation: 'VIX 方向对齐 z 转负，或金价跌破 200 日均线（4,050）',
  },
  {
    key: 'bear',
    label: '看跌情景',
    probability: 0.25,
    price_low: null,
    price_high: 4150,
    trigger: 'VIX 方向对齐 z 转负，或金价跌破 200 日均线（4,050）',
    invalidation: 'VIX 方向对齐 z 转正，或金价站上 200 日均线（4,050）',
  },
]

const FAIR_VALUE: QuantDecomposition = {
  status: 'ok',
  reason: null,
  as_of: '2026-09-30',
  market_price: 4200,
  fair_value: 4130.5,
  deviation_pct: 0.0168,
  r2: 0.912,
  samples: 780,
  blocks: [
    {
      key: 'anchor',
      name: '宏观锚（实际利率 + 美元）',
      usd: 3900,
      share_pct: 92.9,
      drivers: [{ key: 'real_yield_10y', name: '美债 10 年期实际利率', log_contribution: -0.12 }],
    },
    { key: 'demand', name: '需求结构（央行购金）', usd: 120, share_pct: 2.9, drivers: [] },
    { key: 'risk', name: '风险溢价（VIX）', usd: 400, share_pct: 9.5, drivers: [] },
    { key: 'residual', name: '情绪残差', usd: -219.5, share_pct: -5.3, drivers: [] },
  ],
}

function prediction(overrides: Partial<QuantPredictionItem>): QuantPredictionItem {
  return {
    horizon_days: 1,
    scale_label: '1 日',
    scale: '日内～一周',
    scale_description: '资金流、技术面、仓位拥挤度主导，宏观基本面权重最低',
    headline: '方向 / 校准区间',
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
    range_low: 4100,
    range_high: 4330,
    scenarios: SCENARIOS,
    scenario_reason: null,
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
  fair_value: FAIR_VALUE,
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
      range_low: null,
      range_high: null,
      scenarios: [],
      scenario_reason: '预测不可用，无法生成情景',
      score: null,
      available_factors: 2,
      factors: [],
    }),
    prediction({
      horizon_days: 60,
      direction: 'up',
      direction_label: '看涨',
      base_price: 4200,
      target_price: 4380,
      expected_return: 0.0429,
      probability_up: 0.66,
      score: 0.55,
      range_low: null,
      range_high: null,
      scenarios: [],
      scenario_reason: '200 日均线历史样本不足，无法生成触发条件',
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
  metrics: {
    interval_nominal_80: 0.8,
    interval_coverage_80: 0.764,
    score_direction_accuracy: 0.512,
    regimes: {
      split_date: '2022-01-01',
      note: '2022 年起央行购金与地缘冲突改变了定价结构',
      pre: {
        label: '2022-01-01 之前',
        window_start: '2015-01-02',
        window_end: '2021-12-31',
        sample_size: 400,
        accuracy: 0.585,
        baseline_up_accuracy: 0.51,
        baseline_momentum_accuracy: 0.47,
        reason: null,
      },
      post: {
        label: '2022-01-01 起',
        window_start: '2022-01-03',
        window_end: '2026-09-30',
        sample_size: 380,
        accuracy: 0.658,
        baseline_up_accuracy: 0.58,
        baseline_momentum_accuracy: 0.51,
        reason: null,
      },
    },
  },
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

const MONITOR_RESPONSE: QuantMonitorResponse = {
  as_of: '2026-09-30',
  rows: [
    {
      key: 'ma200',
      name: '金价 vs 200 日均线',
      frequency: '日',
      source: '自有价格序列',
      value: 4050,
      unit: '美元',
      change: 3.7,
      obs_date: '2026-09-30',
      signal: 'bull',
      signal_label: '看涨',
      note: '偏离 ≥ +0.5% 看涨、≤ −0.5% 看跌',
      status: 'ok',
      reason: null,
    },
    {
      key: 'rrp',
      name: '纽约联储逆回购（RRP）',
      frequency: '日',
      source: '纽约联储公开市场操作结果',
      value: 320.5,
      unit: '亿美元',
      change: -82.4,
      obs_date: '2026-09-29',
      signal: 'bull',
      signal_label: '看涨',
      note: '20 个观测增加 ≥ 50 亿看跌、减少 ≥ 50 亿看涨（释放流动性）',
      status: 'ok',
      reason: null,
    },
    {
      key: 'usdcny',
      name: '美元兑人民币（USDCNY）',
      frequency: '日',
      source: 'Yahoo Finance（CNY=X）',
      value: 7.12,
      unit: '元',
      change: 0.03,
      obs_date: '2026-09-30',
      signal: null,
      signal_label: '信息',
      note: '信息行：只作人民币金价换算参考，不参与多空',
      status: 'ok',
      reason: null,
    },
    {
      key: 'shanghai_premium',
      name: '上海金溢价',
      frequency: '日',
      source: '上海黄金交易所 AU9999',
      value: null,
      unit: '元/克',
      change: null,
      obs_date: null,
      signal: null,
      signal_label: '不可用',
      note: '公开无密钥接口实测不可用：如实标不可用，不编数',
      status: 'unavailable',
      reason: '公开无密钥接口（上海黄金交易所 AU9999）实测返回空，不编数',
    },
  ],
}

function mockApi() {
  mocked.getFactors.mockResolvedValue(FACTOR_RESPONSE)
  mocked.getPredictions.mockResolvedValue(PREDICTION_RESPONSE)
  mocked.getAccuracy.mockResolvedValue(ACCURACY_RESPONSE)
  mocked.getMonitor.mockResolvedValue(MONITOR_RESPONSE)
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

    await user.click(screen.getAllByRole('tab', { name: '1 日' })[0])

    const panel = await screen.findByTestId('quant-prediction-1')
    expect(within(panel).getByText('▲ 看涨')).toBeInTheDocument()
    expect(within(panel).getByText('$4,260.00')).toBeInTheDocument()
  })

  it('每个尺度给出主输出口径，1 年是公允价值偏离 + 校准区间', async () => {
    mockApi()
    mocked.getPredictions.mockResolvedValue({
      ...PREDICTION_RESPONSE,
      predictions: [
        prediction({
          horizon_days: 250,
          scale_label: '1 年',
          scale: '6～18 个月',
          headline: '公允价值偏离 / 年度校准区间',
        }),
      ],
    })
    const user = userEvent.setup()

    render(<Quant />)
    await screen.findByText('量化预测')

    await user.click(screen.getAllByRole('tab', { name: '1 年' })[0])

    const headline = await screen.findByTestId('quant-prediction-headline-250')
    expect(headline).toHaveTextContent('公允价值偏离 / 年度校准区间')
  })

  it('给出五个尺度，切换后各自给结论', async () => {
    mockApi()
    const user = userEvent.setup()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    for (const label of ['1 日', '1 周', '1 月', '1 季', '1 年']) {
      expect(screen.getAllByRole('tab', { name: label }).length).toBeGreaterThan(0)
    }

    await user.click(screen.getAllByRole('tab', { name: '1 月' })[0])
    expect(await screen.findByText('1 月的预测不可用')).toBeInTheDocument()
  })

  it('预测不可用时只给原因，不给方向与数字', async () => {
    mockApi()
    const user = userEvent.setup()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    await user.click(screen.getAllByRole('tab', { name: '1 月' })[0])

    const block = await screen.findByTestId('quant-prediction-unavailable-20')
    expect(within(block).getByText('1 月的预测不可用')).toBeInTheDocument()
    expect(within(block).getByText(/可用因子只有 2 个/)).toBeInTheDocument()
    expect(screen.queryByTestId('quant-prediction-20')).not.toBeInTheDocument()
    expect(within(block).queryByText(/\$/)).not.toBeInTheDocument()
  })

  it('方向取校准后的漂移，未校准的因子偏向单列一行作对照', async () => {
    mockApi()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    const panel = screen.getByTestId('quant-prediction-5')
    expect(within(panel).getByText(/校准后的漂移/)).toBeInTheDocument()
    // 1 周这一档：得分为负、方向也是负 —— 两行各说各的，不是同一份结论
    expect(within(panel).getByText('因子偏向（未校准）')).toBeInTheDocument()
    expect(within(panel).getByText('偏空 -0.31')).toBeInTheDocument()
  })

  it('期望收益恰为 0 时方向写持平，因子偏向为 0 时写中性', async () => {
    mockApi()
    mocked.getPredictions.mockResolvedValue({
      ...PREDICTION_RESPONSE,
      predictions: [
        prediction({
          horizon_days: 5,
          direction: 'flat',
          direction_label: '持平',
          expected_return: 0,
          probability_up: 0.5,
          score: 0,
          target_price: 4200,
        }),
      ],
    })

    render(<Quant />)

    expect(await screen.findByText('＝ 持平')).toBeInTheDocument()
    expect(screen.getByText('中性 0.00')).toBeInTheDocument()
  })

  it('三情景给出区间、触发与失效条件', async () => {
    mockApi()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    expect(screen.getByText('基准情景')).toBeInTheDocument()
    expect(screen.getByText('$4,150.00 ~ $4,280.00')).toBeInTheDocument()
    expect(screen.getByText('$4,280.00 以上')).toBeInTheDocument()
    expect(screen.getByText('$4,150.00 以下')).toBeInTheDocument()
    expect(screen.getByText(/VIX 方向对齐 z 停留在 ±1 之间/)).toBeInTheDocument()
    expect(screen.getAllByText(/金价跌破 200 日均线/).length).toBeGreaterThan(0)
  })

  it('情景缺样本时只说明原因，不摆区间', async () => {
    mockApi()
    const user = userEvent.setup()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    await user.click(screen.getAllByRole('tab', { name: '1 季' })[0])

    expect(await screen.findByTestId('quant-scenarios-unavailable-60')).toBeInTheDocument()
    expect(screen.getByText(/200 日均线历史样本不足，无法生成触发条件/)).toBeInTheDocument()
  })

  it('公允价分解给出四块构成与偏离度', async () => {
    mockApi()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    expect(screen.getByText('公允价值分解')).toBeInTheDocument()
    expect(screen.getByText('$4,130.50')).toBeInTheDocument()
    expect(screen.getByText('+1.68%')).toBeInTheDocument()
    expect(screen.getByText('0.912')).toBeInTheDocument()
    expect(screen.getByText('宏观锚（实际利率 + 美元）')).toBeInTheDocument()
    expect(screen.getByText('情绪残差')).toBeInTheDocument()
    expect(screen.getByText('92.9%')).toBeInTheDocument()
  })

  it('公允价不可用时只给原因，不摆分解数字', async () => {
    mockApi()
    mocked.getPredictions.mockResolvedValue({
      ...PREDICTION_RESPONSE,
      fair_value: {
        ...FAIR_VALUE,
        status: 'unavailable',
        reason: '回归样本不足（最近 250 个交易日）',
        market_price: null,
        fair_value: null,
        deviation_pct: null,
        r2: null,
        samples: 0,
        blocks: [],
      },
    })

    render(<Quant />)

    expect(await screen.findByTestId('quant-fair-value-unavailable')).toBeInTheDocument()
    expect(screen.getByText(/回归样本不足/)).toBeInTheDocument()
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
    expect(screen.getAllByText('本模型').length).toBeGreaterThan(0)
    expect(screen.getByText('62.1%')).toBeInTheDocument()
    expect(screen.getAllByText('永远看多').length).toBeGreaterThan(0)
    expect(screen.getByText('54.0%')).toBeInTheDocument()
    expect(screen.getByText('动量（60 日）')).toBeInTheDocument()
    expect(screen.getByText('抛硬币')).toBeInTheDocument()
    expect(screen.getByText('50.0%')).toBeInTheDocument()
    expect(screen.getByText(/样本 780 个交易日/)).toBeInTheDocument()

    // 未校准的因子偏向在这段历史里的成绩，单列一行
    const accuracy = screen.getByTestId('quant-accuracy-5')
    expect(within(accuracy).getByText('因子偏向（未校准）')).toBeInTheDocument()
    expect(within(accuracy).getByText('51.2%')).toBeInTheDocument()

    expect(screen.getByText(/实际覆盖率 76.4%/)).toBeInTheDocument()
    expect(screen.getByText('2022-01-01 之前')).toBeInTheDocument()
    expect(screen.getByText('2022-01-01 起')).toBeInTheDocument()
    expect(screen.getByText('65.8%')).toBeInTheDocument()
    // 58.0% 也出现在逐因子命中率表里，用 all 断言存在即可
    expect(screen.getAllByText('58.0%').length).toBeGreaterThan(1)
  })

  it('回测没有因子偏向成绩时不摆这一行，也不拿别的数字顶替', async () => {
    mockApi()
    mocked.getAccuracy.mockResolvedValue({
      ...ACCURACY_RESPONSE,
      latest: [
        {
          ...ACCURACY_ROW,
          metrics: {
            interval_nominal_80: ACCURACY_ROW.metrics.interval_nominal_80,
            interval_coverage_80: ACCURACY_ROW.metrics.interval_coverage_80,
            regimes: ACCURACY_ROW.metrics.regimes,
          },
        },
      ],
    })

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    const accuracy = screen.getByTestId('quant-accuracy-5')
    expect(within(accuracy).queryByText('因子偏向（未校准）')).not.toBeInTheDocument()
    expect(within(accuracy).getAllByText('本模型').length).toBeGreaterThan(0)
  })

  it('监测仪表盘给出值、数据截至与信号，不可用的行说明原因', async () => {
    mockApi()

    render(<Quant />)
    await screen.findByText('▼ 看跌')

    expect(screen.getByText('监测仪表盘（周更表）')).toBeInTheDocument()
    expect(screen.getByText('金价 vs 200 日均线')).toBeInTheDocument()
    expect(screen.getByText('4050 美元')).toBeInTheDocument()
    expect(screen.getByText('+3.70')).toBeInTheDocument()
    expect(screen.getByText('2026-09-29')).toBeInTheDocument()
    expect(screen.getAllByText('▲ 看涨').length).toBeGreaterThan(0)
    // 信息型指标不给方向，照实标「信息」
    expect(screen.getByText('信息')).toBeInTheDocument()
    // 上海金溢价拿不到数据：只给原因，不编一个数
    expect(screen.getByText('上海金溢价')).toBeInTheDocument()
    expect(screen.getByTestId('quant-monitor-reason-shanghai_premium')).toBeInTheDocument()
    expect(screen.getByText(/AU9999）实测返回空，不编数/)).toBeInTheDocument()
  })

  it('接口失败时如实说不可用，不摆内置数字', async () => {
    mocked.getFactors.mockRejectedValue(new Error('boom'))
    mocked.getPredictions.mockRejectedValue(new Error('boom'))
    mocked.getAccuracy.mockRejectedValue(new Error('boom'))
    mocked.getMonitor.mockRejectedValue(new Error('boom'))

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
