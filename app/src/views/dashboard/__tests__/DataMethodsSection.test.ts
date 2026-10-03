import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { byTestId, createBlockHarness, hasText } from '@/test/harness'
import * as fixtures from '@/test/fixtures'
import { healthApi, quantApi, sourcesApi } from '@/services/api'
import { TESTIDS } from '@/testids'

import DataMethodsSection from '../DataMethodsSection.vue'

/**
 * 数据与方法：同步报告、数据源可用性、初始化进度、配置与热加载、服务状态、口径图例。
 *
 * 这一节的特殊之处：它**只陈述事实与口径**，不产生任何新数字。因此测试的
 * 重点不是「数字对不对」，而是：
 *   1. 后端给什么就显示什么（含「未到期」「不可用」这类如实状态）；
 *   2. 密钥永远只以「是否配置」出现，端点可以显示、值不可以；
 *   3. 任一路接口挂了只影响自己那一块，其余照常。
 */
vi.mock('@/services/api', () => ({
  sourcesApi: { getStatus: vi.fn() },
  quantApi: { getFactors: vi.fn() },
  healthApi: { getHealth: vi.fn() },
}))

const mocked = vi.mocked({ sourcesApi, quantApi, healthApi }, true)

const harness = createBlockHarness()

/** 挂载并等到正文出现（三路取数都落定后才从「正在读取」切过去）。 */
async function renderDataMethods() {
  const mounted = harness.mount(DataMethodsSection, { pinia: createPinia() })
  await vi.waitFor(() => {
    expect(byTestId(mounted.root, TESTIDS.dataSourcesStatus)).not.toBeNull()
  })
  return mounted
}

beforeEach(() => {
  vi.clearAllMocks()
  mocked.sourcesApi.getStatus.mockResolvedValue(fixtures.SOURCES)
  mocked.quantApi.getFactors.mockResolvedValue(fixtures.FACTORS_RESPONSE)
  mocked.healthApi.getHealth.mockResolvedValue(fixtures.HEALTH)
})

afterEach(() => {
  harness.cleanup()
})

describe('DataMethods', () => {
  it('面板顺序固定：同步报告 → 数据源可用性 → 初始化进度 → 配置与热加载 → 服务状态 → 口径图例', async () => {
    const { root } = await renderDataMethods()

    const order = [
      TESTIDS.dataSync,
      TESTIDS.dataSourcesStatus,
      TESTIDS.dataBootstrap,
      TESTIDS.dataConfigWatch,
      TESTIDS.dataLegend,
    ]
    const all = [...root.querySelectorAll('*')]
    const positions = order.map((id) => {
      const node = byTestId(root, id)
      expect(node, `缺少 ${id}`).not.toBeNull()
      return all.indexOf(node!)
    })

    expect(positions).toEqual([...positions].sort((a, b) => a - b))
  })

  it('数据源可用性逐行给出渠道、状态、陈旧、年龄与错误原文', async () => {
    const { root } = await renderDataMethods()

    const panel = byTestId(root, TESTIDS.dataSourcesStatus)!
    // 汇总句里的六个计数
    for (const key of ['total', 'ok', 'empty', 'error', 'skipped', 'stale']) {
      expect(byTestId(panel, `field-sources.summary.${key}`), `缺 sources.summary.${key}`).not.toBeNull()
    }
    expect(byTestId(panel, 'field-sources.generated_at')?.textContent).toContain('2026-10-02')

    // 失败行必须带错误原文，不吞掉
    expect(panel.textContent).toContain('连接超时')
    expect(panel.textContent).toContain('黄金新闻 RSS')
    expect(panel.textContent).toContain('量化同步')
    // 陈旧与年龄都按后端字段展示：夹具里第 2 行（量化同步）是 stale: true
    const stale = [...panel.querySelectorAll('[data-testid="field-sources.rows.stale"]')].map(
      (node) => node.textContent?.trim(),
    )
    expect(stale).toEqual(['否', '是', '否'])
    // 年龄用后端给的数字，不自己算
    expect(
      [...panel.querySelectorAll('[data-testid="field-sources.rows.age_hours"]')].map(
        (node) => node.textContent?.trim(),
      ),
    ).toEqual(['1.5', '30', '2'])
  })

  it('初始化进度按 /health 原样展示：阶段表 + 数据空档表', async () => {
    const { root } = await renderDataMethods()

    const panel = byTestId(root, TESTIDS.dataBootstrap)!
    expect(byTestId(panel, 'field-health.bootstrap.status')?.textContent).toContain('done')
    expect(byTestId(panel, 'field-health.bootstrap.step.index')?.textContent).toContain('4')
    expect(byTestId(panel, 'field-health.bootstrap.step.total')?.textContent).toContain('4')
    // 阶段表逐行
    expect(panel.textContent).toContain('数据库迁移')
    expect(byTestId(panel, 'field-health.bootstrap.phases.status')?.textContent).toContain('done')
    // 空档表：四张表 + 量化面板
    expect(byTestId(panel, 'field-health.bootstrap.gaps.gold_prices.rows')).not.toBeNull()
    expect(byTestId(panel, 'field-health.bootstrap.gaps.dollar_index.last_date')).not.toBeNull()
    expect(byTestId(panel, 'field-health.bootstrap.gaps.gold_news.last_published_at')).not.toBeNull()
    expect(byTestId(panel, 'field-health.bootstrap.gaps.news_digest.rows')).not.toBeNull()
    expect(byTestId(panel, 'field-health.bootstrap.gaps.quant.series_without_data')?.textContent).toContain(
      'cftc_net_oi_ratio',
    )
  })

  it('配置与热加载只展示文件名与键名，不展示任何值', async () => {
    const { root } = await renderDataMethods()

    const panel = byTestId(root, TESTIDS.dataConfigWatch)!
    expect(byTestId(panel, 'field-health.config_watch.env_file')?.textContent).toContain('/app/.env')
    expect(byTestId(panel, 'field-health.config_watch.reloaded_keys')?.textContent).toContain('LLM_MODEL')
    expect(panel.textContent).toContain('watching')
    // 这一节永远不该出现密钥值（任何供应商的 key 形态）
    expect(root.textContent).not.toMatch(/sk-[A-Za-z0-9]/)
  })

  it('服务状态逐个给出状态，密钥只以「是否配置」出现', async () => {
    const { root } = await renderDataMethods()

    expect(byTestId(root, 'field-health.services.ai_config.provider')?.textContent).toContain('deepseek')
    expect(byTestId(root, 'field-health.services.ai_config.base_url')?.textContent).toContain(
      'https://api.deepseek.com',
    )
    expect(byTestId(root, 'field-health.services.ai_config.configured')?.textContent).toMatch(/是|否/)
    for (const service of ['database', 'tencent_api', 'cache', 'scheduler']) {
      expect(
        byTestId(root, `field-health.services.${service}.status`),
        `缺 health.services.${service}.status`,
      ).not.toBeNull()
    }
  })

  it('同步报告来自因子接口的 sync 字段，不重复整张逐源表', async () => {
    const { root } = await renderDataMethods()

    const panel = byTestId(root, TESTIDS.dataSync)!
    expect(byTestId(panel, 'field-quant.sync.sources_ok')?.textContent).toContain('6')
    expect(byTestId(panel, 'field-quant.sync.sources_total')?.textContent).toContain('7')
    expect(byTestId(panel, 'field-quant.sync.finished_at')?.textContent).toContain('2026-09-30')
    // 逐源明细在「量化预测 → 数据源状态」，这里不该再摆一遍
    expect(byTestId(panel, 'field-quant.source.name')).toBeNull()
  })

  it('口径说明与图例把三个「金价」口径摊开写', async () => {
    const { root } = await renderDataMethods()

    const legend = byTestId(root, TESTIDS.dataLegend)!
    expect(legend.textContent).toContain('口径')
    expect(hasText(legend, /实时报价/)).toBe(true)
    expect(hasText(legend, /日收盘/)).toBe(true)
  })

  it('数据源接口挂掉只影响自己那一块，其余面板照常', async () => {
    mocked.sourcesApi.getStatus.mockRejectedValue(new Error('boom'))

    const { root } = await renderDataMethods()

    expect(hasText(root, '数据源状态不可用')).toBe(true)
    // 其余面板仍在
    expect(byTestId(root, TESTIDS.dataBootstrap)).not.toBeNull()
    expect(byTestId(root, TESTIDS.dataConfigWatch)).not.toBeNull()
    expect(byTestId(root, TESTIDS.dataLegend)).not.toBeNull()
  })

  it('「未到期」这类如实状态照原样展示，不当成失败', async () => {
    mocked.sourcesApi.getStatus.mockResolvedValue({
      ...fixtures.SOURCES,
      sources: [
        {
          ...fixtures.SOURCES.sources[0],
          status: 'skipped',
          status_label: '未到期',
          stale: false,
          items: null,
          error: null,
        },
      ],
    })

    const { root } = await renderDataMethods()

    expect(hasText(root, '未到期')).toBe(true)
    // 没有条目时显示「—」，不用 0 顶替
    expect(byTestId(root, 'field-sources.rows.items')?.textContent?.trim()).toBe('—')
  })
})
