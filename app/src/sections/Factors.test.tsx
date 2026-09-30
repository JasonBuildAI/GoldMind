import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Factors from './Factors'
import { analysisApi } from '../services/api'

vi.mock('../services/api', () => ({
  analysisApi: {
    getBullishFactors: vi.fn(),
    getBearishFactors: vi.fn(),
  },
}))

const mocked = vi.mocked(analysisApi, true)

const BULLISH = {
  bullish_factors: [
    {
      id: 'fed-policy',
      title: '接口返回的看涨因素',
      subtitle: '来自接口',
      description: '描述',
      details: ['要点1', '要点2'],
      impact: 'high' as const,
    },
  ],
  analysis_summary: '看涨总结',
  last_updated: '2026-02-03 10:00:00',
}

const BEARISH = {
  bearish_factors: [
    {
      id: 'dollar-strength',
      title: '接口返回的看跌因素',
      subtitle: '来自接口',
      description: '描述',
      details: ['要点1', '要点2'],
      impact: 'medium' as const,
    },
  ],
  analysis_summary: '看跌总结',
  last_updated: '2026-02-03 10:00:00',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Factors', () => {
  it('两侧各自渲染接口返回的因子与总结', async () => {
    mocked.getBullishFactors.mockResolvedValue(BULLISH)
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    render(<Factors />)

    expect(await screen.findByText('接口返回的看涨因素')).toBeInTheDocument()
    expect(await screen.findByText('接口返回的看跌因素')).toBeInTheDocument()
    expect(screen.getByTestId('bullish-summary')).toHaveTextContent('看涨总结')
    expect(screen.getByTestId('bearish-summary')).toHaveTextContent('看跌总结')
    // 不应再显示内置默认因子
    expect(screen.queryByText('美联储降息周期')).not.toBeInTheDocument()
  })

  it('渲染接口返回的分析总结，而不是写死的文案', async () => {
    // 回归：原实现把总结写死在 JSX 里，接口返回的 analysis_summary
    // 被取到后直接丢弃，无论分析结果如何页面都显示同一段文案。
    mocked.getBullishFactors.mockResolvedValue(BULLISH)
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    render(<Factors />)

    expect(await screen.findByTestId('bullish-summary')).toHaveTextContent('看涨总结')
    expect(await screen.findByTestId('bearish-summary')).toHaveTextContent('看跌总结')
  })

  it('接口失败时如实说「暂不可用」，而不是摆内置文案', async () => {
    // 回归：原实现在接口失败时回退到一组内置因子与一段写死的总结，
    // 并展示给用户。那违反项目红线 ——「不为了好看而展示编造的数据，
    // 宁可显示「数据不可用」」。
    mocked.getBullishFactors.mockRejectedValue(new Error('boom'))
    mocked.getBearishFactors.mockRejectedValue(new Error('boom'))

    render(<Factors />)

    expect(await screen.findByText('看涨因素暂不可用')).toBeInTheDocument()
    expect(await screen.findByText('看跌因素暂不可用')).toBeInTheDocument()
    // 不能出现任何内置的因子或总结文案
    expect(screen.queryByText('美联储降息周期')).not.toBeInTheDocument()
    expect(screen.queryByTestId('bullish-summary')).not.toBeInTheDocument()
    expect(screen.queryByTestId('bearish-summary')).not.toBeInTheDocument()
    // 同时要说明失败原因
    await waitFor(() => {
      expect(screen.getAllByText(/无法连接后端/).length).toBeGreaterThan(0)
    })
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getBullishFactors.mockRejectedValue(timeoutError)
    mocked.getBearishFactors.mockRejectedValue(timeoutError)

    render(<Factors />)

    await waitFor(() => {
      expect(screen.getAllByText(/分析耗时较长/).length).toBe(2)
    })
  })

  it('接口返回空列表时也走「暂不可用」，不摆内置因子', async () => {
    mocked.getBullishFactors.mockResolvedValue({
      bullish_factors: [],
      analysis_summary: '',
      last_updated: '',
    })
    mocked.getBearishFactors.mockResolvedValue({
      bearish_factors: [],
      analysis_summary: '',
      last_updated: '',
    })

    render(<Factors />)

    expect(await screen.findByText('看涨因素暂不可用')).toBeInTheDocument()
    expect(screen.queryByText('美联储降息周期')).not.toBeInTheDocument()
  })

  it('一侧失败不影响另一侧', async () => {
    mocked.getBullishFactors.mockRejectedValue(new Error('boom'))
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    render(<Factors />)

    expect(await screen.findByText('看涨因素暂不可用')).toBeInTheDocument()
    expect(await screen.findByText('接口返回的看跌因素')).toBeInTheDocument()
    expect(screen.queryByTestId('bullish-summary')).not.toBeInTheDocument()
    expect(screen.getByTestId('bearish-summary')).toHaveTextContent('看跌总结')
  })

  // ------------------------------------------------------------------ #
  // 占位内容
  // ------------------------------------------------------------------ #
  it('接口返回占位内容时明确标注，而不是当成分析结论', async () => {
    // 缓存未命中时后端会立刻返回一份内置内容（metadata.status = 'analyzing'），
    // 结构与真实分析完全一样。不看 metadata 就会把内置常量当结论展示。
    mocked.getBullishFactors.mockResolvedValue({
      ...BULLISH,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })
    mocked.getBearishFactors.mockResolvedValue({
      ...BEARISH,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })

    render(<Factors />)

    expect(await screen.findByTestId('bullish-placeholder')).toBeInTheDocument()
    expect(screen.getByTestId('bearish-placeholder')).toBeInTheDocument()
  })

  it('真实分析结果不显示占位提示', async () => {
    mocked.getBullishFactors.mockResolvedValue({
      ...BULLISH,
      metadata: { cached: true, cache_source: 'file' },
    })
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    render(<Factors />)

    await screen.findByText('接口返回的看涨因素')
    expect(screen.queryByTestId('bullish-placeholder')).not.toBeInTheDocument()
  })

  it('空内容 + 正在分析时说明正在分析，并可以手动触发重算', async () => {
    mocked.getBullishFactors
      .mockResolvedValueOnce({
        bullish_factors: [],
        analysis_summary: '',
        last_updated: '',
        metadata: { cached: false, status: 'analyzing' },
      })
      .mockResolvedValueOnce(BULLISH)
    mocked.getBearishFactors.mockResolvedValue(BEARISH)

    render(<Factors />)

    expect(await screen.findByText('看涨因素正在分析中')).toBeInTheDocument()

    const column = screen.getByTestId('bullish-analyzing')
    fireEvent.click(within(column).getByRole('button', { name: '重新分析' }))

    await waitFor(() => {
      expect(screen.getByText('接口返回的看涨因素')).toBeInTheDocument()
    })
    expect(mocked.getBullishFactors).toHaveBeenLastCalledWith(true)
  })
})
