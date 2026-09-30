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

  it('接口失败时总结回退到兜底文案', async () => {
    mocked.getBullishFactors.mockRejectedValue(new Error('boom'))

    render(<BullishFactors />)

    await waitFor(() => {
      expect(screen.getByTestId('bullish-summary')).toHaveTextContent(/美联储降息周期/)
    })
  })

  it('接口失败时回退到内置默认因子，并给出提示', async () => {
    mocked.getBullishFactors.mockRejectedValue(new Error('boom'))

    render(<BullishFactors />)

    // 默认因子仍然渲染（页面不至于空白）
    expect(await screen.findByText('美联储降息周期')).toBeInTheDocument()
    // 但必须明确告知用户这不是最新分析
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
      expect(screen.getByText(/AI分析耗时较长/)).toBeInTheDocument()
    })
  })

  it('接口返回空列表时保留默认因子而不是渲染空白', async () => {
    mocked.getBullishFactors.mockResolvedValue({
      bullish_factors: [],
      analysis_summary: '',
      last_updated: '',
    })

    render(<BullishFactors />)

    expect(await screen.findByText('美联储降息周期')).toBeInTheDocument()
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
