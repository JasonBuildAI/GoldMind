import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import BullishFactors from './BullishFactors'
import { analysisApi } from '../services/api'

vi.mock('../services/api', () => ({
  analysisApi: {
    getBullishFactors: vi.fn(),
  },
}))

const mocked = vi.mocked(analysisApi, true)

const API_RESPONSE = {
  bullish_factors: [
    {
      id: 'fed-policy',
      title: '接口返回的看涨因子',
      subtitle: '来自接口',
      description: '描述',
      details: ['要点1', '要点2'],
      impact: 'high' as const,
    },
  ],
  analysis_summary: '接口总结',
  last_updated: '2026-02-03 10:00:00',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('BullishFactors', () => {
  it('接口成功时渲染接口返回的因子', async () => {
    mocked.getBullishFactors.mockResolvedValue(API_RESPONSE)

    render(<BullishFactors />)

    expect(await screen.findByText('接口返回的看涨因子')).toBeInTheDocument()
    // 不应再显示内置默认因子
    expect(screen.queryByText('美联储降息周期')).not.toBeInTheDocument()
  })

  it('渲染接口返回的分析总结，而不是写死的文案', async () => {
    // 回归：原实现把总结写死在 JSX 里，接口返回的 analysis_summary
    // 被取到后直接丢弃，无论分析结果如何页面都显示同一段文案。
    mocked.getBullishFactors.mockResolvedValue(API_RESPONSE)

    render(<BullishFactors />)

    expect(await screen.findByTestId('bullish-summary')).toHaveTextContent('接口总结')
  })

  it('接口失败时如实说「暂不可用」，而不是摆内置文案', async () => {
    // 回归：原实现在接口失败时回退到一组内置因子与一段写死的总结，
    // 并展示给用户。那违反项目红线 ——「不为了好看而展示编造的数据，
    // 宁可显示「数据不可用」」。
    mocked.getBullishFactors.mockRejectedValue(new Error('boom'))

    render(<BullishFactors />)

    expect(await screen.findByText('看涨因子暂不可用')).toBeInTheDocument()
    // 不能出现任何内置的因子或总结文案
    expect(screen.queryByText('美联储降息周期')).not.toBeInTheDocument()
    expect(screen.queryByTestId('bullish-summary')).not.toBeInTheDocument()
    // 同时要说明失败原因
    await waitFor(() => {
      expect(screen.getByText(/获取最新分析失败/)).toBeInTheDocument()
    })
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getBullishFactors.mockRejectedValue(timeoutError)

    render(<BullishFactors />)

    await waitFor(() => {
      expect(screen.getByText(/AI 分析耗时较长/)).toBeInTheDocument()
    })
  })

  it('接口返回空列表时也走「暂不可用」，不摆内置因子', async () => {
    mocked.getBullishFactors.mockResolvedValue({
      bullish_factors: [],
      analysis_summary: '',
      last_updated: '',
    })

    render(<BullishFactors />)

    expect(await screen.findByText('看涨因子暂不可用')).toBeInTheDocument()
    expect(screen.queryByText('美联储降息周期')).not.toBeInTheDocument()
  })

  // ------------------------------------------------------------------ #
  // 占位内容
  // ------------------------------------------------------------------ #
  it('接口返回占位内容时明确标注，而不是当成分析结论', async () => {
    // 缓存未命中时后端会立刻返回一份内置内容（metadata.status = 'analyzing'），
    // 结构与真实分析完全一样。不看 metadata 就会把内置常量当结论展示。
    mocked.getBullishFactors.mockResolvedValue({
      ...API_RESPONSE,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })

    render(<BullishFactors />)

    expect(await screen.findByTestId('bullish-placeholder')).toBeInTheDocument()
  })

  it('真实分析结果不显示占位提示', async () => {
    mocked.getBullishFactors.mockResolvedValue({
      ...API_RESPONSE,
      metadata: { cached: true, cache_source: 'file' },
    })

    render(<BullishFactors />)

    await screen.findByText('接口返回的看涨因子')
    expect(screen.queryByTestId('bullish-placeholder')).not.toBeInTheDocument()
  })
})
