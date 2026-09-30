import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosRequestConfig } from 'axios'

import api, { analysisApi, goldApi, institutionApi, investmentAdviceApi, marketSummaryApi } from './api'

let seen: AxiosRequestConfig[] = []

const ok = (config: AxiosRequestConfig, data: unknown = []) => ({
  data,
  status: 200,
  statusText: 'OK',
  headers: {},
  config,
})

/** 构造一个「网络层失败」的错误：没有 response，因此应当被重试。 */
function networkError(config: AxiosRequestConfig): never {
  const err = new Error('Network Error') as Error & Record<string, unknown>
  err.config = config
  err.code = 'ERR_NETWORK'
  throw err
}

/** 构造一个「服务端有响应」的错误：不应被重试。 */
function httpError(config: AxiosRequestConfig, status = 500): never {
  const err = new Error(`Request failed with status code ${status}`) as Error &
    Record<string, unknown>
  err.config = config
  err.response = { status, data: {}, statusText: 'ERR', headers: {}, config }
  throw err
}

beforeEach(() => {
  seen = []
  api.defaults.adapter = async (config) => {
    seen.push(config)
    return ok(config) as never
  }
})

afterEach(() => {
  vi.useRealTimers()
})

// --------------------------------------------------------------------------- #
// 基础配置
// --------------------------------------------------------------------------- #
describe('api 基础配置', () => {
  it('默认使用相对路径，而不是硬编码 localhost', () => {
    // 测试环境没有设置 VITE_API_URL，baseURL 必须为空（相对路径），
    // 这样开发期走 vite 代理、生产期走 nginx 反代。
    expect(api.defaults.baseURL ?? '').toBe('')
  })

  it('请求路径挂在 /api/gold 前缀下', async () => {
    await goldApi.getStats()
    expect(seen[0].url).toBe('/api/gold/stats')
  })

  it('各 API 组的端点路径正确', async () => {
    await goldApi.getDailyPrices('2025-01-01', '2025-01-31')
    await goldApi.getCorrelation(30)
    await goldApi.getDollarRealtime()
    await analysisApi.getBullishFactors()
    await analysisApi.getBearishFactors()
    await institutionApi.getInstitutionPredictions()
    await investmentAdviceApi.getInvestmentAdvice()
    await marketSummaryApi.getMarketSummary()

    const urls = seen.map((c) => c.url)
    expect(urls).toContain('/api/gold/prices/daily?start_date=2025-01-01&end_date=2025-01-31')
    expect(urls).toContain('/api/gold/prices/correlation?days=30')
    expect(urls).toContain('/api/gold/dollar-realtime')
    expect(urls).toContain('/api/gold/bullish-factors-ai?refresh=false')
    expect(urls).toContain('/api/gold/bearish-factors-ai?refresh=false')
    expect(urls).toContain('/api/gold/institution-predictions-ai?refresh=false')
    expect(urls).toContain('/api/gold/investment-advice-ai?refresh=false')
    expect(urls).toContain('/api/gold/market-summary-ai?refresh=false')
  })

  it('AI 分析接口使用更长的超时时间', async () => {
    await analysisApi.getBullishFactors()
    expect(seen[0].timeout).toBe(120000)
  })
})

// --------------------------------------------------------------------------- #
// 重试拦截器
// --------------------------------------------------------------------------- #
describe('响应重试拦截器', () => {
  it('网络错误时最多重试 2 次（共 3 次尝试）', async () => {
    vi.useFakeTimers()
    let attempts = 0
    api.defaults.adapter = async (config) => {
      attempts += 1
      return networkError(config)
    }

    const pending = goldApi.getStats().catch((e: Error) => e)
    await vi.advanceTimersByTimeAsync(5000)
    const result = await pending

    expect(attempts).toBe(3)
    expect((result as Error).message).toBe('Network Error')
  })

  it('网络错误后恢复：最终返回成功结果', async () => {
    vi.useFakeTimers()
    let attempts = 0
    api.defaults.adapter = async (config) => {
      attempts += 1
      if (attempts === 1) return networkError(config)
      return ok(config, { recovered: true }) as never
    }

    const pending = goldApi.getStats()
    await vi.advanceTimersByTimeAsync(5000)

    await expect(pending).resolves.toEqual({ recovered: true })
    expect(attempts).toBe(2)
  })

  it('服务端已有响应时不重试', async () => {
    let attempts = 0
    api.defaults.adapter = async (config) => {
      attempts += 1
      return httpError(config, 500)
    }

    await goldApi.getStats().catch(() => undefined)

    expect(attempts).toBe(1)
  })

  it('POST 一律不重试 —— 它可能触发一次付费的 LLM 分析', async () => {
    // 回归：拦截器原本不看方法，POST /refresh 在超时/网络错误时也会重试。
    // 那次请求会真实触发一次付费分析；重试可能在服务端其实已经跑完的情况下
    // 再跑一次，费用翻倍。后端那层 single_flight 只挡得住「同时进行」的那一次。
    vi.useFakeTimers()
    let attempts = 0
    api.defaults.adapter = async (config) => {
      attempts += 1
      return networkError(config)
    }

    const pending = analysisApi.refreshBullishFactors().catch((e: Error) => e)
    await vi.advanceTimersByTimeAsync(5000)
    await pending

    expect(attempts).toBe(1)
  })

  it('GET 仍然会重试（幂等，安全）', async () => {
    vi.useFakeTimers()
    let attempts = 0
    api.defaults.adapter = async (config) => {
      attempts += 1
      return networkError(config)
    }

    const pending = goldApi.getStats().catch(() => undefined)
    await vi.advanceTimersByTimeAsync(5000)
    await pending

    expect(attempts).toBe(3)
  })

  it('error.config 缺失时不抛 TypeError，原样 reject', async () => {
    // 回归：原实现无条件执行 `config.retry = 0`，
    // 当 error.config 为 undefined 时会抛
    // "TypeError: Cannot set properties of undefined"，把原始错误吞掉。
    api.defaults.adapter = async () => {
      const err = new Error('boom') as Error & Record<string, unknown>
      err.config = undefined
      throw err
    }

    const result = await goldApi.getStats().catch((e: Error) => e)

    expect(result).toBeInstanceOf(Error)
    expect((result as Error).message).toBe('boom')
  })
})

// --------------------------------------------------------------------------- #
// 数据映射
// --------------------------------------------------------------------------- #
describe('响应数据映射', () => {
  it('getAllPriceData 并发拉取日线与相关性', async () => {
    api.defaults.adapter = async (config) => {
      seen.push(config)
      if (config.url?.includes('correlation')) {
        return ok(config, [{ date: '2025-01-02', gold_price: 2600, dollar_index: 108 }]) as never
      }
      return ok(config, [{ date: '2025-01-02', price: 2600, volume: 0 }]) as never
    }

    const result = await goldApi.getAllPriceData()

    expect(result.daily).toHaveLength(1)
    expect(result.correlation).toHaveLength(1)
    expect(seen).toHaveLength(2)
  })
})
