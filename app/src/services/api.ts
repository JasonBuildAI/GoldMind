import axios from 'axios';

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

// 请求重试配置
const MAX_RETRIES = 2;
const RETRY_DELAY = 1000;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;

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
    
    // 检查是否应该重试
    //
    // **只重试幂等请求。** POST 不重试：
    // `POST /api/gold/*/refresh` 会真实触发一次**付费**的 LLM 分析，
    // 超时后重试可能在服务端其实已经跑完的情况下再跑一次，费用直接翻倍。
    // 后端那层 single_flight 只挡得住「同时进行」的那一次，
    // 挡不住「第一次已完成、第二次随后到达」。
    const method = (config.method || 'get').toLowerCase();
    const isIdempotent = method === 'get' || method === 'head' || method === 'options';

    const shouldRetry = isIdempotent &&
      config.retry < MAX_RETRIES && 
      (!error.response || error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK');
    
    if (shouldRetry) {
      config.retry += 1;
      console.warn(`API请求失败，正在重试 (${config.retry}/${MAX_RETRIES}):`, error.message);
      
      // 延迟后重试
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY * config.retry));
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
    
    const response = await api.get<DailyPrice[]>(`/api/gold/prices/daily?${params}`);
    return response.data;
  },

  getCorrelation: async (days: number = 180): Promise<CorrelationData[]> => {
    const response = await api.get<CorrelationData[]>(`/api/gold/prices/correlation?days=${days}`);
    return response.data;
  },

  getStats: async (): Promise<GoldStats> => {
    const response = await api.get<GoldStats>('/api/gold/stats');
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
    const response = await api.get<DollarRealtime>('/api/gold/dollar-realtime');
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
    const response = await api.get<BullishFactorsResponse>(`/api/gold/bullish-factors-ai?refresh=${refresh}`, {
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
    const response = await api.get<BearishFactorsResponse>(`/api/gold/bearish-factors-ai?refresh=${refresh}`, {
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
    const response = await api.get<InstitutionPredictionsResponse>(`/api/gold/institution-predictions-ai?refresh=${refresh}`, {
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
    const response = await api.get<InvestmentAdviceResponse>(`/api/gold/investment-advice-ai?refresh=${refresh}`, {
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
    const response = await api.get<MarketSummaryResponse>(`/api/gold/market-summary-ai?refresh=${refresh}`, {
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

export default api;
