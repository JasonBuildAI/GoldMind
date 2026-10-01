import { describe, expect, it } from 'vitest'

import { modelLabel, type AiConfig } from './useAiConfig'

/**
 * 各区块提示卡里原本**写死了某个具体型号**，而模型由后端的
 * `LLM_MODEL` 决定、随时可改 —— 改了之后界面会继续宣称一个没在用的型号。
 * 现在从 `/health` 读，取不到时如实说「未知」而不是猜一个。
 */
describe('modelLabel', () => {
  it('有配置时显示「供应商 + 型号」', () => {
    const config: AiConfig = {
      provider: 'some-provider',
      model: 'some-model',
      configured: true,
    }

    expect(modelLabel(config)).toBe('some-provider some-model')
  })

  it('换了模型就跟着变，不会停留在写死的型号上', () => {
    const config: AiConfig = {
      provider: 'some-provider',
      model: 'some-other-model',
      configured: true,
    }

    expect(modelLabel(config)).toContain('some-other-model')
    expect(modelLabel(config)).not.toContain('some-model ')
  })

  it('拿不到配置时如实说「未知」，不猜一个型号', () => {
    expect(modelLabel(null)).toContain('未知')
    expect(modelLabel(null)).not.toContain('some-model')
  })

  it('型号为空时显示「未配置」', () => {
    const config: AiConfig = { provider: 'some-provider', model: '', configured: false }

    expect(modelLabel(config)).toBe('未配置')
  })
})
