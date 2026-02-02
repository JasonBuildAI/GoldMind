import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
    
    // 如果没有重试配置，初始化
    if (!config || !config.retry) {
      config.retry = 0;
    }
    
    // 检查是否应该重试
    const shouldRetry = config.retry < MAX_RETRIES && 
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
  open_price?: number;
  high_price?: number;
  low_price?: number;
  change_percent?: number;
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
}

export interface NewsItem {
  id: number;
  title: string;
  summary: string;
  source: string;
  url: string;
  published_at: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  created_at: string;
}

export interface MarketAnalysis {
  id: number;
  analysis_date: string;
  overall_sentiment: string;
  bullish_factors: string[];
  bearish_factors: string[];
  key_levels: {
    support: number[];
    resistance: number[];
  };
  short_term_outlook: string;
  long_term_outlook: string;
  generated_at: string;
  created_at: string;
}

export interface PricePrediction {
  id: number;
  prediction_date: string;
  target_date: string;
  predicted_price: number;
  confidence_level: string;
  prediction_type: string;
  factors_considered: string[];
  generated_at: string;
  created_at: string;
}

export interface LatestPrice {
  date: string;
  price: number;
  open_price: number;
  high_price: number;
  low_price: number;
  change_percent: number;
  volume: number;
  updated_at: string;
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

  getCorrelation: async (days: number = 30): Promise<CorrelationData[]> => {
    const response = await api.get<CorrelationData[]>(`/api/gold/prices/correlation?days=${days}`);
    return response.data;
  },

  getLatestPrice: async (): Promise<LatestPrice> => {
    const response = await api.get<LatestPrice>('/api/gold/prices/latest');
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

export const newsApi = {
  getNews: async (limit: number = 20, offset: number = 0): Promise<NewsItem[]> => {
    const response = await api.get<NewsItem[]>(`/api/news?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  getLatestNews: async (limit: number = 10): Promise<NewsItem[]> => {
    const response = await api.get<NewsItem[]>(`/api/news/latest?limit=${limit}`);
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
}

export const analysisApi = {
  getLatestAnalysis: async (): Promise<MarketAnalysis> => {
    const response = await api.get<MarketAnalysis>('/api/analysis/latest');
    return response.data;
  },

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

export const predictionApi = {
  getPredictions: async (): Promise<PricePrediction[]> => {
    const response = await api.get<PricePrediction[]>('/api/predictions');
    return response.data;
  },

  getLatestPrediction: async (): Promise<PricePrediction> => {
    const response = await api.get<PricePrediction>('/api/predictions/latest');
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
  metadata?: {
    generated_at: string;
    data_sources: string[];
    analysis_method: string;
  };
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
  metadata?: {
    cached: boolean;
    cache_source: string;
    generated_at: string;
  };
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

export const healthApi = {
  checkHealth: async (): Promise<{ status: string; database: string }> => {
    const response = await api.get('/health');
    return response.data;
  },
};

export default api;
