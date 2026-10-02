import axios from 'axios';
import type { AxiosRequestConfig, AxiosResponse } from 'axios';

import type { ApiMetadata } from '@/lib/placeholder';

// 默认走相对路径：
//   - 开发期由 vite 的 server.proxy 把 /api 转发到后端
//   - 生产期（Docker）由 nginx 的 location /api/ 反代到 backend:8000
// 不要硬编码 http://localhost:8000：Docker 部署时浏览器解析不了容器主机名，
// 而且 Vite 是在构建期内联 VITE_API_URL 的，运行时注入无效。
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30秒超时（增加以应对AI分析耗时）
  headers: {
    'Content-Type': 'application/json',
  },
});

// --------------------------------------------------------------------------- #
// 重试与在飞去重
// --------------------------------------------------------------------------- #
//
// 为什么要对 429 / 5xx 也重试：限流是**瞬态**失败 —— 窗口滑过去就好。
// 旧实现只重试「连响应都没拿到」的错误，429 直接判死：看板整片红，
// 过一会儿刷新又好了。退避 + 抖动把重试错峰，429 优先听服务端的
// Retry-After（它知道窗口还有多久），比我们拍一个间隔准。
const MAX_RETRIES = 2; // 首发之外最多再试 2 次 = 最多 3 次尝试
const BASE_RETRY_DELAY_MS = 500;
const MAX_RETRY_DELAY_MS = 10000;

type RetryConfig = AxiosRequestConfig & { retry?: number };

/** 429 优先按 Retry-After（秒）等待；普通失败走指数退避 + 抖动。 */
function expectedRetryDelayMs(error: {
  response?: {
    status?: number;
    headers?: Record<string, unknown>;
    data?: { retry_after?: number };
  };
}, retryNumber: number): number {
  const headers = error.response?.headers ?? {};
  if (error.response?.status === 429) {
    const raw =
      headers['retry-after'] ??
      headers['Retry-After'] ??
      error.response?.data?.retry_after;
    const seconds = Number(raw);
    if (Number.isFinite(seconds) && seconds > 0) {
      return Math.min(seconds * 1000, MAX_RETRY_DELAY_MS);
    }
  }
  const backoff = Math.min(BASE_RETRY_DELAY_MS * 2 ** (retryNumber - 1), MAX_RETRY_DELAY_MS);
  // ±25% 抖动：多个区块同时重试时错开，别第二次又一起撞上限流窗口
  return backoff * (0.75 + Math.random() * 0.5);
}

/**
 * 只有幂等请求才允许重试 —— 并且要排除「会触发付费 LLM 分析」的 GET。
 *
 * `GET ...-ai?refresh=true` 与 `POST .../refresh` 一样会真花钱：重试可能在
 * 服务端其实已经跑完的情况下再买一次。后端限流就按这条口径把两者归进
 * 同一档（见 `backend/app/main.py` 的 `_is_ai_path`），前端保持同一判据。
 */
function isRetryableRequest(config: RetryConfig): boolean {
  const method = (config.method || 'get').toLowerCase();
  if (!(method === 'get' || method === 'head' || method === 'options')) {
    return false;
  }
  return !/([?&])refresh=(true|1)(&|$)/i.test(config.url || '');
}

/** 网络层失败、超时、408/429/5xx 可重试；501 与其余 4xx 是确定性失败。 */
function isRetryableError(error: { code?: string; response?: { status?: number } }): boolean {
  if (!error.response) {
    return true; // 无响应：断网 / 连接被拒 / CORS 预检失败
  }
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return true;
  }
  const status = error.response.status ?? 0;
  if (status === 408 || status === 425 || status === 429) {
    return true;
  }
  return status >= 500 && status <= 599 && status !== 501;
}

/**
 * 同一时刻、同一 URL 的 GET 只发一次。
 *
 * 开发态 StrictMode 会把 effect 跑两遍，轮询与手动刷新也会撞车；
 * 请求量翻倍后最容易顶到限流上限。并发的调用方共享同一个 Promise
 * （成功/失败结果一致），请求结束后立刻从表里清掉。
 */
const inflightGets = new Map<string, Promise<unknown>>();

function getJson<T>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
  const key = `${config?.baseURL ?? API_BASE_URL}|${config?.timeout ?? ''}|${url}`;
  const existing = inflightGets.get(key);
  if (existing) {
    return existing as Promise<AxiosResponse<T>>;
  }
  const request = api.get<T>(url, config).finally(() => {
    if (inflightGets.get(key) === request) {
      inflightGets.delete(key);
    }
  });
  inflightGets.set(key, request);
  return request;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config as RetryConfig | undefined;

    // 没有 config 就无法重试（例如请求还没构造完成就失败了）。
    // 原实现会继续往下执行 `config.retry = 0`，抛
    // "TypeError: Cannot set properties of undefined"，把原始错误吞掉，
    // 调用方看到的是一个与被调接口毫无关系的错误。
    if (!config) {
      console.error('API Error:', error.message);
      return Promise.reject(error);
    }

    // 如果没有重试配置，初始化
    if (!config.retry) {
      config.retry = 0;
    }
    
    // **只重试幂等且不含付费语义的请求。** POST /refresh 与
    // GET ...?refresh=true 会真实触发一次**付费**的 LLM 分析：
    // 超时后重试可能在服务端其实已经跑完的情况下再跑一次，费用直接翻倍。
    // 后端那层 single_flight 只挡得住「同时进行」的那一次，
    // 挡不住「第一次已完成、第二次随后到达」。
    const shouldRetry =
      isRetryableRequest(config) && config.retry < MAX_RETRIES && isRetryableError(error);
    
    if (shouldRetry) {
      config.retry += 1;
      const delay = expectedRetryDelayMs(error, config.retry);
      console.warn(
        `API 请求失败，${Math.round(delay)}ms 后重试 (${config.retry}/${MAX_RETRIES}):`,
        error.message,
      );
      
      await new Promise(resolve => setTimeout(resolve, delay));
      return api(config);
    }
    
    console.error('API Error:', error.message);
    return Promise.reject(error);
  }
);

export interface DailyPrice {
  date: string;
  price: number;
  volume: number;
  // 这里原本还声明了 open_price? / high_price? / low_price? / change_percent?，
  // 但 /api/gold/prices/daily 从不返回它们，前端也从不读它们 ——
  // 留着只会让人以为接口提供了 OHLC。真需要的话先让后端发出来。
}

export interface CorrelationData {
  date: string;
  gold_price: number;
  dollar_index: number;
}

export interface GoldStats {
  current_price: number;
  start_price: number;
  ytd_return: number;
  max_price: number;
  min_price: number;
  max_date: string;
  min_date: string;
  volatility: number;
  market_status: string;
  market_status_desc: string;
  updated_at: string;
  /** 数据来源（人类可读），例如「腾讯财经-纽约黄金」或「数据库历史数据」 */
  data_source: string;
  /** 是否真的取到了实时价；false 表示价格来自数据库里的历史记录 */
  is_realtime: boolean;
}

export interface GoldPriceResponse {
  daily: DailyPrice[];
  correlation: CorrelationData[];
}

export interface DollarRealtime {
  price: number;
  previous_close: number;
  change_percent: number;
  updated_at: string;
  /**
   * 这条行情所属的交易日，由**数据源**给出（后端的 `values[10]`）。
   *
   * 必须用它来判断「最后一个数据点是不是今天」，不能用
   * `new Date().toISOString().split('T')[0]` —— 那是 **UTC** 日期：
   * 东八区在 00:00-08:00 之间算出来的是昨天，实时美元指数就静默地不更新了，
   * 相关性图上今天那个点会一直显示旧值。
   */
  date: string;
  source: string;
}

export const goldApi = {
  getDailyPrices: async (startDate?: string, endDate?: string): Promise<DailyPrice[]> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const response = await getJson<DailyPrice[]>(`/api/gold/prices/daily?${params}`);
    return response.data;
  },

  getCorrelation: async (days: number = 180): Promise<CorrelationData[]> => {
    const response = await getJson<CorrelationData[]>(`/api/gold/prices/correlation?days=${days}`);
    return response.data;
  },

  getStats: async (): Promise<GoldStats> => {
    const response = await getJson<GoldStats>('/api/gold/stats');
    return response.data;
  },

  getAllPriceData: async (): Promise<GoldPriceResponse> => {
    const [daily, correlation] = await Promise.all([
      goldApi.getDailyPrices(),
      goldApi.getCorrelation(),
    ]);
    return { daily, correlation };
  },

  getDollarRealtime: async (): Promise<DollarRealtime> => {
    const response = await getJson<DollarRealtime>('/api/gold/dollar-realtime');
    return response.data;
  },
};

export interface BullishFactor {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  details: string[];
  impact: 'high' | 'medium' | 'low';
}

export interface BullishFactorsResponse {
  bullish_factors: BullishFactor[];
  analysis_summary: string;
  last_updated: string;
  /** 后端用它说明这份内容是真实分析还是占位内容（status === 'analyzing'） */
  metadata?: ApiMetadata;
}

export interface BearishFactor {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  details: string[];
  impact: 'high' | 'medium' | 'low';
}

export interface BearishFactorsResponse {
  bearish_factors: BearishFactor[];
  analysis_summary: string;
  last_updated: string;
  metadata?: ApiMetadata;
}

export const analysisApi = {
  getBullishFactors: async (refresh: boolean = false): Promise<BullishFactorsResponse> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await getJson<BullishFactorsResponse>(`/api/gold/bullish-factors-ai?refresh=${refresh}`, {
      timeout: 120000,
    });
    return response.data;
  },

  refreshBullishFactors: async (): Promise<{ success: boolean; message: string; data: BullishFactorsResponse }> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await api.post('/api/gold/bullish-factors-ai/refresh', null, {
      timeout: 120000,
    });
    return response.data;
  },

  getBearishFactors: async (refresh: boolean = false): Promise<BearishFactorsResponse> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await getJson<BearishFactorsResponse>(`/api/gold/bearish-factors-ai?refresh=${refresh}`, {
      timeout: 120000,
    });
    return response.data;
  },

  refreshBearishFactors: async (): Promise<{ success: boolean; message: string; data: BearishFactorsResponse }> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await api.post('/api/gold/bearish-factors-ai/refresh', null, {
      timeout: 120000,
    });
    return response.data;
  },
};

export interface InstitutionPrediction {
  name: string;
  logo: string;
  rating: 'bullish' | 'bearish' | 'neutral';
  target_price: number;
  timeframe: string;
  reasoning: string;
  key_points: string[];
  /** 该预测最近一次被核实/抓取入库的日期（YYYY-MM-DD）；占位行没有日期 */
  as_of_date?: string | null;
  /** 距今天数（后端用项目时区计算）；没有日期时为 null */
  stale_days?: number | null;
  /** 线索来源：web_search / news_scan / legacy */
  source?: string | null;
}

export interface InstitutionPredictionsResponse {
  institutions: InstitutionPrediction[];
  analysis_summary: string;
  last_updated: string;
  metadata?: ApiMetadata;
}

export const institutionApi = {
  getInstitutionPredictions: async (refresh: boolean = false): Promise<InstitutionPredictionsResponse> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await getJson<InstitutionPredictionsResponse>(`/api/gold/institution-predictions-ai?refresh=${refresh}`, {
      timeout: 120000,
    });
    return response.data;
  },

  refreshInstitutionPredictions: async (): Promise<{ success: boolean; message: string; data: InstitutionPredictionsResponse }> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await api.post('/api/gold/institution-predictions-ai/refresh', null, {
      timeout: 120000,
    });
    return response.data;
  },
};

export interface EntryStrategy {
  current_price_assessment: string;
  recommended_entry_range: string;
  entry_timing: string;
  position_building: string;
}

export interface ExitStrategy {
  profit_target: string;
  stop_loss: string;
  rebalancing_trigger: string;
}

export interface InvestmentStrategy {
  type: 'conservative' | 'balanced' | 'opportunistic';
  title: string;
  description: string;
  allocation: string;
  timeframe: string;
  risk_level: 'low' | 'medium' | 'high';
  entry_strategy: EntryStrategy;
  exit_strategy: ExitStrategy;
  pros: string[];
  cons: string[];
  suitable_for: string[];
  execution_steps: string[];
}

export interface CorePrinciple {
  title: string;
  description: string;
}

export interface MarketAssessment {
  current_position: string;
  risk_level: 'low' | 'medium' | 'high';
  recommended_approach: string;
  key_considerations: string[];
}

export interface InvestmentAdviceResponse {
  market_assessment: MarketAssessment;
  strategies: InvestmentStrategy[];
  core_principles: CorePrinciple[];
  risk_warning: string;
  disclaimer: string;
  metadata?: ApiMetadata;
}

export const investmentAdviceApi = {
  getInvestmentAdvice: async (refresh: boolean = false): Promise<InvestmentAdviceResponse> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await getJson<InvestmentAdviceResponse>(`/api/gold/investment-advice-ai?refresh=${refresh}`, {
      timeout: 120000,
    });
    return response.data;
  },

  refreshInvestmentAdvice: async (): Promise<{ success: boolean; message: string; data: InvestmentAdviceResponse }> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await api.post('/api/gold/investment-advice-ai/refresh', null, {
      timeout: 120000,
    });
    return response.data;
  },
};

// 市场综合分析接口
export interface MarketSummaryResponse {
  core_bullish_logic: string[];
  main_risks: string[];
  market_consensus: string[];
  institution_targets: {
    institution: string;
    target: number;
    probability: string;
    timeframe: string;
  }[];
  current_price: number;
  comprehensive_judgment: {
    bullish_summary: string;
    bearish_summary: string;
    neutral_summary: string;
  };
  core_view: string;
  investment_recommendation: string;
  confidence_level: string;
  time_horizon: string;
  metadata?: ApiMetadata;
}

export const marketSummaryApi = {
  getMarketSummary: async (refresh: boolean = false): Promise<MarketSummaryResponse> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await getJson<MarketSummaryResponse>(`/api/gold/market-summary-ai?refresh=${refresh}`, {
      timeout: 120000,
    });
    return response.data;
  },

  refreshMarketSummary: async (): Promise<{ success: boolean; message: string; data: MarketSummaryResponse }> => {
    // AI 分析可能需要较长时间，设置 120 秒超时
    const response = await api.post('/api/gold/market-summary-ai/refresh', null, {
      timeout: 120000,
    });
    return response.data;
  },
};

// --------------------------------------------------------------------------- //
// 量化预测（backend/app/services/quant）
//
// 这一组接口的原则与后端一致：算不出来的字段是 null，`status` 与 `reason`
// 说明为什么。前端不补默认值 —— 页面宁可显示「不可用」。
// --------------------------------------------------------------------------- //
export type QuantFactorStatus = 'ok' | 'stale' | 'missing' | 'warming'

export interface QuantFactorContribution {
  key: string
  name: string
  category: string
  category_name: string
  weight: number
  sign: number
  value: number | null
  obs_date: string | null
  z: number | null
  signed_z: number | null
  contribution: number | null
  status: QuantFactorStatus
  reason: string | null
}

export interface QuantFactorSnapshot extends QuantFactorContribution {
  unit: string
  source: string
  description: string
  age_days: number | null
  max_age_days: number
}

export interface QuantCategoryStatus {
  key: string
  name: string
  total: number
  available: number
}

export interface QuantSourceStatus {
  name: string
  label: string | null
  status: string
  error: string | null
  reason: string | null
}

export interface QuantSyncStatus {
  started_at: string | null
  finished_at: string | null
  sources_ok: number | null
  sources_total: number | null
}

export interface QuantFactorsResponse {
  model_version: string
  as_of: string | null
  available_factors: number
  total_factors: number
  categories: QuantCategoryStatus[]
  factors: QuantFactorSnapshot[]
  sources: QuantSourceStatus[]
  sync: QuantSyncStatus
  unavailable_reason: string | null
}

export interface QuantScenario {
  key: 'base' | 'bull' | 'bear'
  label: string
  probability: number
  price_low: number | null
  price_high: number | null
  trigger: string
  invalidation: string
}

export interface QuantDecompositionDriver {
  key: string
  name: string
  log_contribution: number | null
}

export interface QuantDecompositionBlock {
  key: 'anchor' | 'demand' | 'risk' | 'residual'
  name: string
  usd: number | null
  share_pct: number | null
  drivers: QuantDecompositionDriver[]
}

export interface QuantDecomposition {
  status: string
  reason: string | null
  as_of: string | null
  market_price: number | null
  fair_value: number | null
  deviation_pct: number | null
  r2: number | null
  samples: number
  blocks: QuantDecompositionBlock[]
}

export interface QuantPredictionItem {
  horizon_days: number
  scale_label: string | null
  scale: string | null
  scale_description: string | null
  // 该尺度的主输出口径（1 年是「公允价值偏离 + 校准区间」）
  headline: string | null
  status: string
  reason: string | null
  // 'flat' = 校准后的期望收益恰为 0（样本不足时不写方向，这里不会混进得分的符号）
  direction: 'up' | 'down' | 'flat' | null
  direction_label: string | null
  as_of: string | null
  base_price: number | null
  target_price: number | null
  expected_return: number | null
  uncertainty: number | null
  probability_up: number | null
  // 区间是自适应的：名义 80% 只是起点，实际水平 = 1 − interval_alpha。
  // 'aci' = 经验分布 + 自适应 α，'normal' = 样本不足时退回的解析正态。
  distribution_mode: string | null
  interval_alpha: number | null
  interval_nominal: number | null
  // 期望收益是否被护栏夹过（封顶改的是用户看到的数字，必须能看见）
  expected_capped: boolean
  range_low: number | null
  range_high: number | null
  scenarios: QuantScenario[]
  scenario_reason: string | null
  score: number | null
  model_version: string
  available_factors: number
  total_factors: number
  factors: QuantFactorContribution[]
}

export interface QuantPredictionsResponse {
  model_version: string
  as_of: string | null
  fair_value: QuantDecomposition
  predictions: QuantPredictionItem[]
}

export interface QuantFactorPerformance {
  key: string
  name: string
  category: string
  category_name: string
  weight: number
  sign: number
  samples: number
  hit_rate: number | null
  ic: number | null
  rank_ic: number | null
}

export interface QuantAccuracyRow {
  horizon_days: number
  evaluated_at: string | null
  window_start: string | null
  window_end: string | null
  sample_size: number
  accuracy: number | null
  baseline_up_accuracy: number | null
  baseline_momentum_accuracy: number | null
  brier_score: number | null
  metrics: QuantAccuracyMetrics
  factors: QuantFactorPerformance[]
  reason: string | null
}

export interface QuantRegimeBlock {
  label: string
  window_start: string | null
  window_end: string | null
  sample_size: number
  accuracy: number | null
  baseline_up_accuracy: number | null
  baseline_momentum_accuracy: number | null
  reason: string | null
}

export interface QuantAccuracyMetrics {
  interval_nominal_80?: number
  interval_coverage_80?: number | null
  // 未校准的因子偏向（合成得分符号）在同一段历史里的成绩，与本模型并排对照
  score_direction_accuracy?: number | null
  regimes?: {
    split_date?: string
    note?: string
    pre?: QuantRegimeBlock
    post?: QuantRegimeBlock
  }
  reason?: string
  [key: string]: unknown
}

export interface QuantAccuracyResponse {
  model_version: string
  latest: QuantAccuracyRow[]
  history: QuantAccuracyRow[]
}

export interface QuantRefreshResponse {
  success: boolean
  message: string
  sources: QuantSourceStatus[]
  factor_status: Record<string, unknown>
  predictions: QuantPredictionItem[]
  evaluations: QuantAccuracyRow[]
}

export interface QuantMonitorRow {
  key: string
  name: string
  frequency: string
  source: string
  value: number | null
  unit: string
  change: number | null
  obs_date: string | null
  signal: 'bull' | 'bear' | 'neutral' | null
  signal_label: string
  note: string
  status: string
  reason: string | null
}

export interface QuantMonitorResponse {
  as_of: string | null
  rows: QuantMonitorRow[]
}

export interface ResearchPeriod {
  label: string
  window_start: string | null
  window_end: string | null
  sample_size: number
  accuracy: number | null
  baseline_up_accuracy: number | null
  baseline_momentum_accuracy: number | null
  brier_score: number | null
  brier_skill_score: number | null
  brier_skill_p_value: number | null
  accuracy_diff_vs_up: number | null
  accuracy_ci95: number[] | null
  p_value_vs_up: number | null
  interval_coverage_80: number | null
  interval_coverage_ci95: number[] | null
  effective_sample_size: number | null
  // 独立下注口径（stride = 尺度）：重叠样本折算后还剩多少可信度
  independent_bets: number | null
  independent_bet_stride: number | null
  accuracy_independent_bets: number | null
  interval_coverage_80_independent_bets: number | null
  reason: string | null
}

/** 判决窗口（前向留出期）够不够判：次数与「还差多少个交易日」都由后端算好。 */
export interface ForwardWindowReadiness {
  window_start: string
  observations: number
  independent_bets: number
  required_bets: number
  decidable: boolean
  shortfall_bets: number
  approx_trading_days_needed: number
}

export interface ResearchReliabilityBin {
  lo: number | null
  hi: number | null
  count: number
  mean_predicted: number | null
  frequency: number | null
}

export interface ResearchFactor {
  key: string
  name: string
  category: string
  category_name: string
  weight: number
  sign: number
  samples: number
  hit_rate: number | null
  ic: number | null
  rank_ic: number | null
}

export interface HorizonResearch {
  horizon_days: number
  label: string
  headline: string
  periods: {
    development: ResearchPeriod
    holdout: ResearchPeriod
    forward: ResearchPeriod
    full: ResearchPeriod
  }
  forward_readiness: ForwardWindowReadiness
  reliability_bins: ResearchReliabilityBin[]
  factors: ResearchFactor[]
}

export interface ResearchVerdict {
  status: 'candidate' | 'no_edge' | 'unavailable' | string
  label: string
  detail: string
}

export interface QuantResearchResponse {
  model_version: string
  status: string
  reason: string | null
  as_of: string | null
  holdout_start: string
  active_holdout_start: string
  generated_at: string
  cached: boolean
  verdict: ResearchVerdict
  horizons: HorizonResearch[]
}

export const quantApi = {
  getFactors: async (category?: string): Promise<QuantFactorsResponse> => {
    const url = category
      ? `/api/gold/quant/factors?category=${encodeURIComponent(category)}`
      : '/api/gold/quant/factors'
    const response = await getJson<QuantFactorsResponse>(url)
    return response.data
  },

  getPredictions: async (horizonDays?: number): Promise<QuantPredictionsResponse> => {
    const url = horizonDays
      ? `/api/gold/quant/predictions?horizon_days=${horizonDays}`
      : '/api/gold/quant/predictions'
    const response = await getJson<QuantPredictionsResponse>(url)
    return response.data
  },

  getAccuracy: async (): Promise<QuantAccuracyResponse> => {
    const response = await getJson<QuantAccuracyResponse>('/api/gold/quant/accuracy')
    return response.data
  },

  getMonitor: async (): Promise<QuantMonitorResponse> => {
    const response = await getJson<QuantMonitorResponse>('/api/gold/quant/monitor')
    return response.data
  },

  // 研究页：技能总览 / 可靠性 / 因子拆解 / 预注册裁决；首次约数秒，后端缓存 1 小时
  getResearch: async (): Promise<QuantResearchResponse> => {
    const response = await getJson<QuantResearchResponse>('/api/gold/quant/research', {
      timeout: 60000,
    })
    return response.data
  },

  // 抓取全部数据源 + 重算 + 回测，后端限流同付费档，超时给足
  refresh: async (): Promise<QuantRefreshResponse> => {
    const response = await api.post<QuantRefreshResponse>('/api/gold/quant/refresh', null, {
      timeout: 180000,
    })
    return response.data
  },
}

// --------------------------------------------------------------------------- //
// 消息板块：高权威黄金消息精选（评分由后端确定性计算，不调用 LLM）
// --------------------------------------------------------------------------- //
export interface DigestRelatedItem {
  title: string
  source: string
  url: string
  published_at: string
}

export interface DigestItem {
  rank: number
  id: number
  title: string
  summary: string
  source: string
  tier: number
  tier_label: string
  url: string
  published_at: string
  age_hours: number
  importance: number
  confidence: number
  signals: string[]
  coverage_count: number
  related: DigestRelatedItem[]
}

export interface DigestWindow {
  key: string
  label: string
  hours: number
  total_clusters: number
  items: DigestItem[]
}

export interface DigestFetchSource {
  name: string
  status: string
  entries: number
  kept: number
  new: number
  error?: string | null
}

export interface DigestFetchReport {
  fetched_at: string
  total_sources: number
  ok_sources: number
  failed_sources: number
  entries: number
  kept: number
  new_items: number
  duplicates: number
  skipped_no_title: number
  skipped_no_url: number
  skipped_no_time: number
  skipped_filtered: number
  skipped_unstorable: number
  sources: DigestFetchSource[]
}

export interface DigestResponse {
  generated_at: string
  has_data: boolean
  unavailable_reason: string | null
  last_fetch: DigestFetchReport | null
  windows: DigestWindow[]
}

export interface DigestRefreshResponse extends DigestFetchReport {
  success: boolean
}

export const newsDigestApi = {
  getDigest: async (): Promise<DigestResponse> => {
    const response = await api.get<DigestResponse>('/api/gold/news/digest')
    return response.data
  },

  // 全源抓取可能需要十几秒（13 个来源并发、单源 10 秒超时），超时给足
  refresh: async (): Promise<DigestRefreshResponse> => {
    const response = await api.post<DigestRefreshResponse>('/api/gold/news/digest/refresh', null, {
      timeout: 120000,
    })
    return response.data
  },
}

export default api;
