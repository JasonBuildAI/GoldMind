import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Conclusion from './Conclusion'
import { marketSummaryApi } from '../services/api'

vi.mock('../services/api', () => ({
  marketSummaryApi: {
    getMarketSummary: vi.fn(),
  },
}))

const mocked = vi.mocked(marketSummaryApi, true)

const SUMMARY = {
  core_bullish_logic: ['接口返回的看涨逻辑'],
  main_risks: ['接口返回的主要风险'],
  market_consensus: ['接口返回的市场共识'],
  institution_targets: [
    { institution: '接口返回的机构', target: 5400, probability: '高', timeframe: '2026年底' },
  ],
  current_price: 2690,
  comprehensive_judgment: {
    bullish_summary: '接口返回的看多判断',
    bearish_summary: '接口返回的看空判断',
    neutral_summary: '接口返回的中性判断',
  },
  core_view: '接口返回的核心观点',
  investment_recommendation: '接口返回的投资建议',
  confidence_level: '中',
  time_horizon: '中期',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Conclusion', () => {
  it('渲染三栏要点、综合判断与核心观点', async () => {
    mocked.getMarketSummary.mockResolvedValue(SUMMARY)

    render(<Conclusion />)

    expect(await screen.findByText('接口返回的看涨逻辑')).toBeInTheDocument()
    expect(screen.getByText('接口返回的主要风险')).toBeInTheDocument()
    expect(screen.getByText('接口返回的市场共识')).toBeInTheDocument()
    expect(screen.getByText('接口返回的看多判断')).toBeInTheDocument()
    expect(screen.getByText('接口返回的看空判断')).toBeInTheDocument()
    expect(screen.getByText('接口返回的中性判断')).toBeInTheDocument()
    expect(screen.getByText('接口返回的核心观点')).toBeInTheDocument()
    expect(screen.getByText('接口返回的投资建议')).toBeInTheDocument()
    expect(screen.getByText('中期')).toBeInTheDocument()
  })

  it('目标价按接口返回展示，当前价格取接口字段而不是写死的数字', async () => {
    mocked.getMarketSummary.mockResolvedValue(SUMMARY)

    render(<Conclusion />)

    expect(await screen.findByText('$5,400.00')).toBeInTheDocument()
    expect(screen.getByText('当前价格')).toBeInTheDocument()
    expect(screen.getByText('$2,690.00')).toBeInTheDocument()
  })

  it('机构没有目标价、模型写成 0 时显示「—」，不是 $0.00', async () => {
    // 回归：模型对「暂无目标价」会写 target: 0，Intl 把它渲染成 $0.00 —— 那是
    // 一个并不存在的价格。设计规范要求算不出的字段显示「—」，不填默认值。
    mocked.getMarketSummary.mockResolvedValue({
      ...SUMMARY,
      institution_targets: [
        { institution: '接口返回的机构', target: 0, probability: '低', timeframe: '暂无' },
      ],
    })

    render(<Conclusion />)

    expect(await screen.findByText('接口返回的机构')).toBeInTheDocument()
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument()
  })

  it('接口没给当前价格时不显示「当前价格」这一行', async () => {
    // 回归：原实现把当前价格写死成 5067 —— 那是凭空的数字，
    // 会被当成「当前价格」摆在目标价表里。
    mocked.getMarketSummary.mockResolvedValue({
      ...SUMMARY,
      current_price: 0,
    })

    render(<Conclusion />)

    await screen.findByText('$5,400.00')
    expect(screen.queryByText('当前价格')).not.toBeInTheDocument()
    expect(screen.queryByText('$5,067.00')).not.toBeInTheDocument()
  })

  it('接口失败时如实说「暂不可用」，不摆内置结论', async () => {
    mocked.getMarketSummary.mockRejectedValue(new Error('boom'))

    render(<Conclusion />)

    expect(await screen.findByText('市场总结暂不可用')).toBeInTheDocument()
    expect(screen.queryByText('核心看涨逻辑')).not.toBeInTheDocument()
    expect(screen.getByText(/无法连接后端/)).toBeInTheDocument()
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getMarketSummary.mockRejectedValue(timeoutError)

    render(<Conclusion />)

    expect(await screen.findByText(/分析耗时较长/)).toBeInTheDocument()
  })

  it('后端已开始分析（空内容）时说明正在分析，而不是报「不可用」', async () => {
    mocked.getMarketSummary.mockResolvedValue({
      core_bullish_logic: [],
      main_risks: [],
      market_consensus: [],
      institution_targets: [],
      current_price: 0,
      comprehensive_judgment: { bullish_summary: '', bearish_summary: '', neutral_summary: '' },
      core_view: '',
      investment_recommendation: '',
      confidence_level: '',
      time_horizon: '',
      metadata: { cached: false, status: 'analyzing' },
    })

    render(<Conclusion />)

    expect(await screen.findByText('市场总结正在分析中')).toBeInTheDocument()
  })

  it('市场总结的占位标记（cache_source=default）也会被标注', async () => {
    // 市场总结与其余区块不同：它用 cache_source === 'default' 表示占位内容。
    mocked.getMarketSummary.mockResolvedValue({
      ...SUMMARY,
      metadata: { cached: true, cache_source: 'default' },
    })

    render(<Conclusion />)

    expect(await screen.findByTestId('conclusion-placeholder')).toBeInTheDocument()
  })
})
