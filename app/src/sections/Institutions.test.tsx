import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Institutions from './Institutions'
import { institutionApi } from '../services/api'

vi.mock('../services/api', () => ({
  institutionApi: {
    getInstitutionPredictions: vi.fn(),
  },
}))

const mocked = vi.mocked(institutionApi, true)

const RESPONSE = {
  institutions: [
    {
      name: '接口返回的机构',
      logo: 'X',
      rating: 'bullish' as const,
      target_price: 5400,
      timeframe: '2026年底',
      reasoning: '接口返回的理由',
      key_points: ['要点甲', '要点乙'],
    },
  ],
  analysis_summary: '机构总结',
  last_updated: '2026-02-03 10:00:00',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Institutions', () => {
  it('把接口返回的机构整理成表格：机构、评级、目标价、时间框架、理由', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue(RESPONSE)

    render(<Institutions />)

    const table = within(await screen.findByTestId('institutions-table'))
    expect(table.getByText('接口返回的机构')).toBeInTheDocument()
    expect(table.getByText(/看涨/)).toBeInTheDocument()
    // 目标价统一为美元格式并在数字列右对齐
    expect(table.getByText('$5,400.00')).toBeInTheDocument()
    expect(table.getByText('2026年底')).toBeInTheDocument()
    expect(table.getByText('接口返回的理由')).toBeInTheDocument()
  })

  it('表下显示接口返回的分析摘要，而不是写死的共识文案', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue(RESPONSE)

    render(<Institutions />)

    expect(await screen.findByTestId('institutions-summary')).toHaveTextContent('机构总结')
  })

  it('接口失败时如实说「暂不可用」，不显示任何目标价', async () => {
    // 机构目标价是最不能编的东西：宁可整段留白，也不能摆一个内置名单。
    mocked.getInstitutionPredictions.mockRejectedValue(new Error('boom'))

    render(<Institutions />)

    expect(await screen.findByText('机构观点暂不可用')).toBeInTheDocument()
    expect(screen.queryByTestId('institutions-table')).not.toBeInTheDocument()
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument()
    expect(screen.queryByText('高盛 (Goldman Sachs)')).not.toBeInTheDocument()
    expect(screen.queryByTestId('institutions-summary')).not.toBeInTheDocument()
    expect(screen.getByText(/无法连接后端/)).toBeInTheDocument()
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getInstitutionPredictions.mockRejectedValue(timeoutError)

    render(<Institutions />)

    expect(await screen.findByText(/分析耗时较长/)).toBeInTheDocument()
  })

  it('接口返回空列表且未在分析时，走「暂不可用」', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      institutions: [],
      analysis_summary: '',
      last_updated: '',
    })

    render(<Institutions />)

    expect(await screen.findByText('机构观点暂不可用')).toBeInTheDocument()
  })

  it('后端已开始分析时说明正在分析，而不是报「不可用」', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      institutions: [],
      analysis_summary: '',
      last_updated: '2026-02-03 10:00:00',
      metadata: { cached: false, status: 'analyzing' },
    })

    render(<Institutions />)

    expect(await screen.findByText('机构观点正在分析中')).toBeInTheDocument()
  })

  it('接口返回占位内容时明确标注，而不是当成分析结论', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      ...RESPONSE,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })

    render(<Institutions />)

    expect(await screen.findByTestId('institutions-placeholder')).toBeInTheDocument()
  })

  it('真实分析结果不显示占位提示', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      ...RESPONSE,
      metadata: { cached: true, cache_source: 'file' },
    })

    render(<Institutions />)

    await screen.findByTestId('institutions-table')
    expect(screen.queryByTestId('institutions-placeholder')).not.toBeInTheDocument()
  })
})
