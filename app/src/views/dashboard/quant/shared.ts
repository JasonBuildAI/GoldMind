import { formatUsd } from '@/lib/format'
import type { ForwardPosterior, QuantPredictionItem, QuantScenario } from '@/services/api'

/**
 * 量化区块的共用小件：尺度口径、方向 / 状态标签、量级格式化与 Beta 后验。
 *
 * 只服务「量化预测」与「研究」两处；跨页共用的东西才放这里，避免第三份拷贝。
 * 这里只有纯函数 —— 需要结构的地方（方向标签、状态徽标、后验表）留在各组件的
 * 模板里，TS 模块不放模板。
 */

export const HORIZONS = [1, 5, 20, 60, 250] as const

export const SCALE_SHORT: Record<number, string> = {
  1: '1 日',
  5: '1 周',
  20: '1 月',
  60: '1 季',
  250: '1 年',
}

export function horizonLabel(days: number): string {
  return SCALE_SHORT[days] ?? `${days} 个交易日`
}

/** 后端状态词的统一中文；未知状态原样显示，不猜。 */
export const STATUS_LABEL: Record<string, string> = {
  ok: '正常',
  stale: '陈旧',
  missing: '无数据',
  warming: '样本不足',
  skipped: '未到期',
  error: '不可用',
  pending: '等待中',
  running: '进行中',
  done: '已完成',
  failed: '失败',
  disabled: '未启用',
  published: '已发布',
  not_published: '未发布',
}

export function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status
}

/**
 * 行情方向：符号 + 文字一起给，颜色只是加强。
 *
 * direction_status === 'not_published' 时**不画箭头** —— 方向停发是模型的
 * 明确声明（例如 250 日样本不足），这里照实显示原因，不拿别的字段凑一个方向。
 */
export function directionText(direction: QuantPredictionItem['direction']): string {
  return direction === 'up'
    ? '▲ 看涨'
    : direction === 'down'
      ? '▼ 看跌'
      : direction === 'flat'
        ? '＝ 持平'
        : '—'
}

/** 方向配色：只做加强，语义由 ▲▼ 与文字承担。 */
export function directionClass(direction: QuantPredictionItem['direction']): string | undefined {
  return direction === 'up' ? 'is-up' : direction === 'down' ? 'is-down' : undefined
}

/** 一行结论里的方向文字：方向停发时写「未发布」，不画箭头。 */
export function directionHeadlineText(
  direction: QuantPredictionItem['direction'],
  directionStatus: string,
): string {
  if (directionStatus === 'not_published') return statusLabel(directionStatus)
  return directionText(direction)
}

/** 未校准的因子偏向：合成得分的符号 + 数值，只作对照，不代表模型结论。 */
export function factorTilt(score: number | null): string {
  if (score === null) return '—'
  const label = score > 0 ? '偏多' : score < 0 ? '偏空' : '中性'
  return `${label} ${score.toFixed(2)}`
}

export function scenarioRange(scenario: QuantScenario): string {
  if (scenario.price_low !== null && scenario.price_high !== null) {
    return `${formatUsd(scenario.price_low)} ~ ${formatUsd(scenario.price_high)}`
  }
  if (scenario.price_low !== null) return `${formatUsd(scenario.price_low)} 以上`
  if (scenario.price_high !== null) return `${formatUsd(scenario.price_high)} 以下`
  return '—'
}

export const SIGNAL_TEXT: Record<string, string> = {
  bull: '▲ 看涨',
  bear: '▼ 看跌',
  neutral: '— 中性',
}

/**
 * 按量级取舍小数位：800000 不该显示成 800000.00，
 * 铜金比 0.0016 也不该显示成 0.00（两位小数会把非零的值压成零，等同丢数）。
 */
export function formatMagnitude(abs: number): string {
  if (abs > 0 && abs < 0.01) return abs.toPrecision(3)
  return abs.toFixed(abs >= 100 ? 0 : 2)
}

/** 变化量按量级给小数位：0.12 -> +0.12；123456 -> +12.3 万。 */
export function formatChange(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '\u2212' : ''
  const abs = Math.abs(value)
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(1)} 万`
  return `${sign}${formatMagnitude(abs)}`
}

/** 仪表盘的值：正值不带符号，负值用真正的减号。 */
export function formatMonitorValue(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 10000) return formatChange(value)
  return value < 0 ? `\u2212${formatMagnitude(abs)}` : formatMagnitude(abs)
}

/** 后端 monitor.py 里明确不参与多空判断的信息型指标（只看不评）。 */
export const MONITOR_INFO_KEYS: ReadonlySet<string> = new Set([
  'usdcny',
  'cny_gold',
  'cftc_oi',
  'gvz',
  'gold_silver_ratio',
  'copper_gold_ratio',
  'cftc_net_oi_ratio',
  'gpr_daily',
  'digest_intensity',
])

export const INTERVAL_ALPHA_TEXT: Record<string, string> = {
  aci: '经验分布 + 自适应 α',
  normal: '样本不足退回解析正态',
}

// --------------------------------------------------------------------------- #
// 研究页与回测共用的小格式化：输入都是「分数值」（0.62 = 62%）
// --------------------------------------------------------------------------- #

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function num(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return value.toFixed(digits)
}

export function interval(pair: number[] | null | undefined): string {
  if (!pair || pair.length !== 2) return '—'
  return `${(pair[0] * 100).toFixed(1)}% ~ ${(pair[1] * 100).toFixed(1)}%`
}

/** 百分点差（输入是分数）：+3.2 个百分点。 */
export function pp(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  const sign = value > 0 ? '+' : value < 0 ? '\u2212' : ''
  return `${sign}${Math.abs(value * 100).toFixed(digits)} 个百分点`
}

/** Beta 后验表的一行：字段路径 → 标签 → 已格式化的值。 */
export interface PosteriorRow {
  path: string
  label: string
  value: string
}

/**
 * 前向裁决的 Beta 后验（先验 Beta(1,1)）：逐字段给展示位。
 *
 * 后端 HTTP 响应模型当前可能尚未透出该字段（`HorizonResearch` 未声明），
 * 缺失时如实说明，不摆一个假的后验。
 */
export function posteriorRows(posterior: ForwardPosterior): PosteriorRow[] {
  return [
    { path: 'prior', label: '先验', value: `Beta(${posterior.prior.join(', ')})` },
    { path: 'alpha', label: '后验 α（成功 + 先验）', value: num(posterior.alpha) },
    { path: 'beta', label: '后验 β（失败 + 先验）', value: num(posterior.beta) },
    { path: 'successes', label: '独立下注命中数', value: String(posterior.successes) },
    { path: 'independent_bets', label: '独立下注数', value: String(posterior.independent_bets) },
    { path: 'mean', label: '后验均值', value: pct(posterior.mean) },
    { path: 'ci95', label: '95% 可信区间', value: interval(posterior.ci95) },
    { path: 'threshold', label: '判决阈值', value: pct(posterior.threshold) },
    {
      path: 'probability_above_threshold',
      label: '后验均值高于阈值的概率',
      value: pct(posterior.probability_above_threshold),
    },
    { path: 'mean_crps', label: '平均 CRPS（整张分布）', value: num(posterior.mean_crps) },
    {
      path: 'crps_skill_vs_flat',
      label: 'CRPS 技能 vs 零漂移',
      value: num(posterior.crps_skill_vs_flat),
    },
  ]
}
