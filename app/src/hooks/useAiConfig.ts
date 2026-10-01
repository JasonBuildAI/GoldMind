/**
 * AI 配置（供应商 / 模型）的唯一来源。
 *
 * 各区块的提示卡里原本**写死了某个具体型号**，而模型其实由后端的
 * `LLM_MODEL` 决定、随时可改。改了之后界面会继续宣称一个没在用的型号 ——
 * 同一事实写在两处，然后漂开。
 *
 * `/health` 的 `services.ai_config` 已经给出 `provider` / `model` / `base_url`，
 * 这里读它。取不到时**不猜**，返回 null，由调用方显示「未知」。
 */
import { useEffect, useState } from 'react'

export interface AiConfig {
  provider: string
  model: string
  search_model?: string
  base_url?: string
  configured: boolean
}

// 模块级缓存：整个页面只需要请求一次
let cache: AiConfig | null = null
let inflight: Promise<AiConfig | null> | null = null

async function loadAiConfig(): Promise<AiConfig | null> {
  if (cache) return cache
  if (inflight) return inflight

  inflight = (async () => {
    try {
      const response = await fetch('/health')
      if (!response.ok) return null
      const body = await response.json()
      const config = body?.services?.ai_config
      // status 为 error / unconfigured 时不算拿到配置
      if (!config || config.status === 'error') return null
      cache = {
        provider: config.provider ?? '',
        model: config.model ?? '',
        search_model: config.search_model,
        base_url: config.base_url,
        configured: Boolean(config.configured),
      }
      return cache
    } catch {
      return null
    } finally {
      inflight = null
    }
  })()

  return inflight
}

export function useAiConfig(): AiConfig | null {
  const [config, setConfig] = useState<AiConfig | null>(cache)

  useEffect(() => {
    let alive = true
    loadAiConfig().then((value) => {
      if (alive) setConfig(value)
    })
    return () => {
      alive = false
    }
  }, [])

  return config
}

/** 给提示卡用的显示值：拿不到就如实说「未知」，不硬编码一个型号。 */
export function modelLabel(config: AiConfig | null): string {
  if (!config) return '未知（未能从 /health 读到）'
  if (!config.model) return '未配置'
  return `${config.provider ? `${config.provider} ` : ''}${config.model}`
}
