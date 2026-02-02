import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { goldApi, type GoldStats, type DailyPrice, type CorrelationData, type DollarRealtime } from '@/services/api';

interface GoldDataContextType {
  // 统计数据
  stats: GoldStats | null;
  statsLoading: boolean;
  statsError: string | null;
  
  // 日线数据
  dailyPrices: DailyPrice[];
  dailyLoading: boolean;
  dailyError: string | null;
  
  // 相关性数据
  correlationData: CorrelationData[];
  correlationLoading: boolean;
  correlationError: string | null;
  
  // 实时美元指数
  dollarRealtime: DollarRealtime | null;
  
  // 刷新函数
  refreshStats: () => Promise<void>;
  refreshCharts: () => Promise<void>;
  refreshAll: () => Promise<void>;
  
  // 最后更新时间
  lastUpdated: Date | null;
}

const GoldDataContext = createContext<GoldDataContextType | undefined>(undefined);

// 缓存时间（毫秒）
const CACHE_DURATION = 5000; // 5秒内不重复请求

export function GoldDataProvider({ children }: { children: ReactNode }) {
  // 统计数据
  const [stats, setStats] = useState<GoldStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [statsLastFetch, setStatsLastFetch] = useState<number>(0);
  
  // 日线数据
  const [dailyPrices, setDailyPrices] = useState<DailyPrice[]>([]);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [dailyError, setDailyError] = useState<string | null>(null);
  const [dailyLastFetch, setDailyLastFetch] = useState<number>(0);
  
  // 相关性数据
  const [correlationData, setCorrelationData] = useState<CorrelationData[]>([]);
  const [correlationLoading, setCorrelationLoading] = useState(false);
  const [correlationError, setCorrelationError] = useState<string | null>(null);
  const [correlationLastFetch, setCorrelationLastFetch] = useState<number>(0);
  
  // 实时美元指数
  const [dollarRealtime, setDollarRealtime] = useState<DollarRealtime | null>(null);
  
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // 获取统计数据
  const refreshStats = useCallback(async (force = false) => {
    const now = Date.now();
    if (!force && now - statsLastFetch < CACHE_DURATION) {
      return; // 使用缓存
    }
    
    setStatsLoading(true);
    setStatsError(null);
    try {
      const data = await goldApi.getStats();
      setStats(data);
      setStatsLastFetch(now);
      setLastUpdated(new Date());
    } catch (err) {
      setStatsError('获取统计数据失败');
      console.error('Failed to fetch stats:', err);
    } finally {
      setStatsLoading(false);
    }
  }, [statsLastFetch]);

  // 获取图表数据（日线 + 相关性）
  const refreshCharts = useCallback(async (force = false) => {
    const now = Date.now();
    const shouldFetchDaily = force || now - dailyLastFetch >= CACHE_DURATION;
    const shouldFetchCorrelation = force || now - correlationLastFetch >= CACHE_DURATION;

    if (!shouldFetchDaily && !shouldFetchCorrelation) {
      return; // 都使用缓存
    }

    setDailyLoading(shouldFetchDaily);
    setCorrelationLoading(shouldFetchCorrelation);
    setDailyError(null);
    setCorrelationError(null);

    try {
      const promises: Promise<any>[] = [];

      if (shouldFetchDaily) {
        promises.push(goldApi.getDailyPrices());
      }
      if (shouldFetchCorrelation) {
        promises.push(goldApi.getCorrelation());
      }

      const results = await Promise.all(promises);
      let resultIndex = 0;

      if (shouldFetchDaily) {
        setDailyPrices(results[resultIndex++]);
        setDailyLastFetch(now);
      }
      if (shouldFetchCorrelation) {
        let correlation = results[resultIndex++];

        // 获取实时美元指数并更新到最后一个数据点
        try {
          const dollarRealtime: DollarRealtime = await goldApi.getDollarRealtime();
          if (correlation && correlation.length > 0 && dollarRealtime) {
            const today = new Date().toISOString().split('T')[0];
            const lastIndex = correlation.length - 1;

            if (correlation[lastIndex].date === today) {
              // 更新今天的数据
              correlation[lastIndex] = {
                ...correlation[lastIndex],
                dollar_index: dollarRealtime.price
              };
            } else {
              // 添加今天的实时数据
              correlation.push({
                date: today,
                gold_price: correlation[lastIndex].gold_price, // 保持金价不变
                dollar_index: dollarRealtime.price
              });
            }
          }
        } catch (dollarErr) {
          console.warn('获取实时美元指数失败，使用历史数据:', dollarErr);
        }

        setCorrelationData(correlation);
        setCorrelationLastFetch(now);
      }

      setLastUpdated(new Date());
    } catch (err) {
      setDailyError('获取图表数据失败');
      setCorrelationError('获取图表数据失败');
      console.error('Failed to fetch chart data:', err);
    } finally {
      setDailyLoading(false);
      setCorrelationLoading(false);
    }
  }, [dailyLastFetch, correlationLastFetch]);

  // 刷新所有数据
  const refreshAll = useCallback(async () => {
    await Promise.all([
      refreshStats(true),
      refreshCharts(true)
    ]);
  }, [refreshStats, refreshCharts]);

  // 单独刷新美元指数（实时更新）
  const refreshDollarRealtime = useCallback(async () => {
    try {
      console.log('[GoldDataContext] 开始获取实时美元指数...');
      const dollarData = await goldApi.getDollarRealtime();
      console.log('[GoldDataContext] 获取到实时美元指数:', dollarData);
      setDollarRealtime(dollarData);

      // 更新相关性数据中的美元指数
      setCorrelationData(prevData => {
        if (!prevData || prevData.length === 0) {
          console.log('[GoldDataContext] correlationData为空，不更新');
          return prevData;
        }

        const today = new Date().toISOString().split('T')[0];
        const lastIndex = prevData.length - 1;
        const newData = [...prevData];

        console.log(`[GoldDataContext] 更新前最后一个数据:`, newData[lastIndex]);
        console.log(`[GoldDataContext] 今天日期: ${today}, 最后数据日期: ${newData[lastIndex].date}`);

        if (newData[lastIndex].date === today) {
          // 更新今天的数据
          newData[lastIndex] = {
            ...newData[lastIndex],
            dollar_index: dollarData.price
          };
          console.log(`[GoldDataContext] 更新今天的美元指数为: ${dollarData.price}`);
        } else {
          // 添加今天的实时数据
          newData.push({
            date: today,
            gold_price: newData[lastIndex].gold_price,
            dollar_index: dollarData.price
          });
          console.log(`[GoldDataContext] 添加今天的美元指数数据: ${dollarData.price}`);
        }

        console.log(`[GoldDataContext] 更新后最后一个数据:`, newData[newData.length - 1]);
        return newData;
      });

      setLastUpdated(new Date());
    } catch (err) {
      console.warn('[GoldDataContext] 获取实时美元指数失败:', err);
    }
  }, []);

  // 初始加载
  useEffect(() => {
    refreshStats();
    refreshCharts();
  }, []);

  // 定时刷新统计数据和图表数据（每10秒）
  useEffect(() => {
    const interval = setInterval(() => {
      refreshStats(true);
      refreshCharts(true);
    }, 10000); // 每10秒刷新
    
    return () => clearInterval(interval);
  }, [refreshStats, refreshCharts]);

  // 定时刷新美元指数（每10秒，独立刷新）
  useEffect(() => {
    // 立即执行一次
    refreshDollarRealtime();
    
    const interval = setInterval(() => {
      refreshDollarRealtime();
    }, 10000); // 每10秒刷新
    
    return () => clearInterval(interval);
  }, [refreshDollarRealtime]);

  const value: GoldDataContextType = {
    stats,
    statsLoading,
    statsError,
    dailyPrices,
    dailyLoading,
    dailyError,
    correlationData,
    correlationLoading,
    correlationError,
    dollarRealtime,
    refreshStats,
    refreshCharts,
    refreshAll,
    lastUpdated
  };

  return (
    <GoldDataContext.Provider value={value}>
      {children}
    </GoldDataContext.Provider>
  );
}

export function useGoldData() {
  const context = useContext(GoldDataContext);
  if (context === undefined) {
    throw new Error('useGoldData must be used within a GoldDataProvider');
  }
  return context;
}
