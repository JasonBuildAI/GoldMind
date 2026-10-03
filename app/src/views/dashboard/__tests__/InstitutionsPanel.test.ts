import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { byTestId, createBlockHarness, hasText } from '@/test/harness'
import { institutionApi, type InstitutionPredictionsResponse } from '@/services/api'

import InstitutionsPanel from '../InstitutionsPanel.vue'

/**
 * 机构观点：表格逐列、摘要、三态、占位标注、预测日期与滞后天数。
 *
 * 最要紧的一条：机构目标价是最不能编的东西 —— 取不到就整段留白，
 * 绝不用内置名单补一个数字。
 */
vi.mock('@/services/api', () => ({
  institutionApi: { getInstitutionPredictions: vi.fn() },
}))

const mocked = vi.mocked(institutionApi, true)

const RESPONSE: InstitutionPredictionsResponse = {
  institutions: [
    {
      name: '接口返回的机构',
      logo: 'X',
      rating: 'bullish',
      target_price: 5400,
      timeframe: '2026年底',
      reasoning: '接口返回的理由',
      key_points: ['要点甲', '要点乙'],
      as_of_date: '2026-02-08',
      stale_days: 235,
      source: 'legacy',
    },
  ],
  analysis_summary: '机构总结',
  last_updated: '2026-02-03 10:00:00',
}

const harness = createBlockHarness()

/**
 * 挂载并等到**终态**：内容表格、正在分析、不可用三者之一。
 * 只等 `institutions-loading` 会立刻返回，断言就落在「正在读取…」上。
 */
async function renderInstitutions() {
  const mounted = harness.mount(InstitutionsPanel)
  await vi.waitFor(() => {
    expect(
      mounted.root.querySelector(
        '[data-testid="institutions-table"], [data-testid="institutions-analyzing"], [data-testid="institutions-unavailable"]',
      ),
    ).not.toBeNull()
  })
  return mounted
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  harness.cleanup()
})

describe('Institutions', () => {
  it('把接口返回的机构整理成表格：机构、评级、目标价、时间框架、理由', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue(RESPONSE)

    const { root } = await renderInstitutions()

    const table = byTestId(root, 'institutions-table')!
    expect(table.textContent).toContain('接口返回的机构')
    expect(table.textContent).toContain('看涨')
    // 目标价统一为美元格式并在数字列右对齐
    expect(table.textContent).toContain('$5,400.00')
    expect(table.textContent).toContain('2026年底')
    expect(table.textContent).toContain('接口返回的理由')
  })

  it('表下显示接口返回的分析摘要，而不是写死的共识文案', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue(RESPONSE)

    const { root } = await renderInstitutions()

    expect(byTestId(root, 'institutions-summary')?.textContent).toContain('机构总结')
  })

  it('接口失败时如实说「暂不可用」，不显示任何目标价', async () => {
    // 机构目标价是最不能编的东西：宁可整段留白，也不能摆一个内置名单。
    mocked.getInstitutionPredictions.mockRejectedValue(new Error('boom'))

    const { root } = await renderInstitutions()

    expect(hasText(root, '机构观点暂不可用')).toBe(true)
    expect(byTestId(root, 'institutions-table')).toBeNull()
    expect(hasText(root, /\$/)).toBe(false)
    expect(hasText(root, '高盛 (Goldman Sachs)')).toBe(false)
    expect(byTestId(root, 'institutions-summary')).toBeNull()
    expect(hasText(root, /无法连接后端/)).toBe(true)
  })

  it('接口超时时给出针对超时的提示文案', async () => {
    const timeoutError = Object.assign(new Error('timeout of 120000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    mocked.getInstitutionPredictions.mockRejectedValue(timeoutError)

    const { root } = await renderInstitutions()

    expect(hasText(root, /分析耗时较长/)).toBe(true)
  })

  it('接口返回空列表且未在分析时，走「暂不可用」', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      institutions: [],
      analysis_summary: '',
      last_updated: '',
    })

    const { root } = await renderInstitutions()

    expect(hasText(root, '机构观点暂不可用')).toBe(true)
  })

  it('后端已开始分析时说明正在分析，而不是报「不可用」', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      institutions: [],
      analysis_summary: '',
      last_updated: '2026-02-03 10:00:00',
      metadata: { cached: false, status: 'analyzing' },
    })

    const { root } = await renderInstitutions()

    expect(hasText(root, '机构观点正在分析中')).toBe(true)
  })

  it('接口返回占位内容时明确标注，而不是当成分析结论', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      ...RESPONSE,
      metadata: { cached: false, status: 'analyzing', message: 'AI分析进行中' },
    })

    const { root } = await renderInstitutions()

    expect(byTestId(root, 'institutions-placeholder')).not.toBeNull()
  })

  it('真实分析结果不显示占位提示', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      ...RESPONSE,
      metadata: { cached: true, cache_source: 'file' },
    })

    const { root } = await renderInstitutions()

    expect(byTestId(root, 'institutions-placeholder')).toBeNull()
  })

  it('显示预测日期，且「已滞后 N 天」只在超过 30 天时出现', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      ...RESPONSE,
      institutions: [
        { ...RESPONSE.institutions[0], as_of_date: '2026-02-08', stale_days: 235 },
        { ...RESPONSE.institutions[0], name: '第二家机构', as_of_date: '2026-09-29', stale_days: 2 },
        { ...RESPONSE.institutions[0], name: '边界机构', as_of_date: '2026-09-01', stale_days: 30 },
      ],
    })

    const { root } = await renderInstitutions()

    const table = byTestId(root, 'institutions-table')!
    expect(table.textContent).toContain('2026-02-08')
    expect(table.textContent).toContain('已滞后 235 天')
    expect(table.textContent).toContain('2026-09-29')
    // 30 天是边界：不滞后，不该出现标注
    expect(table.textContent).not.toContain('已滞后 2 天')
    expect(table.textContent).not.toContain('已滞后 30 天')
  })

  it('没有预测日期的占位行显示「—」，且不标滞后', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue({
      ...RESPONSE,
      institutions: [
        {
          ...RESPONSE.institutions[0],
          as_of_date: null,
          stale_days: null,
          reasoning: '暂无最新预测',
        },
      ],
    })

    const { root } = await renderInstitutions()

    const table = byTestId(root, 'institutions-table')!
    expect(table.textContent).toContain('—')
    expect(table.textContent).not.toContain('已滞后')
  })

  it('文案说明机构观点是「最近一次可核实的预测，可能滞后」', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue(RESPONSE)

    const { root } = await renderInstitutions()

    expect(hasText(root, /最近一次可核实的预测/)).toBe(true)
    expect(hasText(root, /可能滞后/)).toBe(true)
  })

  it('机构缩写按字标渲染，不当图片地址（旧实现把 "GS" 当 src，页面上是碎图）', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue(RESPONSE)

    const { root } = await renderInstitutions()

    const logo = byTestId(root, 'field-institutions.logo')
    expect(logo?.tagName).toBe('SPAN')
    expect(logo?.textContent).toBe('X')
    // 整个面板不该再有 <img>：logo 字段不是图片地址。
    expect(root.querySelector('img')).toBeNull()
  })

  it('理由单元格里的要点收在一层折叠里，不嵌套第二层', async () => {
    mocked.getInstitutionPredictions.mockResolvedValue(RESPONSE)

    const { root } = await renderInstitutions()

    const details = byTestId(root, 'field-institutions.key_points')
    expect(details).not.toBeNull()
    expect(details?.querySelectorAll('details').length).toBe(0)
    expect(details?.querySelector('summary')?.textContent).toContain('要点（2）')
  })
})
