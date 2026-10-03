import type { HealthResponse } from '@/services/api'

/**
 * 「数据与方法」各面板共用的取值换算。
 *
 * 这一节只陈述后端给出的事实：任何缺失都显示「—」，不填默认值、不猜数字
 * （项目红线，见 docs/00-产品方向.md 第四节）。
 */

/** 空值统一显示「—」；布尔按「是 / 否」，对象（含数组）按 JSON 原样展示，不做美化。 */
export function text(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/**
 * /health 的服务自检字段：`services.<服务>.<键>`。
 *
 * 服务或键缺失时返回 undefined，由 `text()` 兜底成「—」——
 * 取不到就如实说取不到，不假设服务在线。
 */
export function serviceValue(health: HealthResponse | null, service: string, key: string): unknown {
  const services = (health?.services ?? {}) as Record<string, Record<string, unknown> | undefined>
  return services[service]?.[key]
}
