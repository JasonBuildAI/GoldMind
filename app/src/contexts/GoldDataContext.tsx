import { describeApiError } from '@/lib/apiError';
import { createContext, useContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
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

// 轮询间隔（毫秒）。从 10 秒放宽到 30 秒：一个打开的看板原先每 10 秒
// 拉 stats / daily / correlation / dollar 各一次（外加首屏约 15 个区块请求、
// 开发态 StrictMode 再翻倍），首分钟就逼近后端 60 次/分钟的限流上限；
// 一旦 429，整片报错，过一会儿刷新又好。30 秒档位下空闲请求 ≤ 8 次/分钟。
const POLL_INTERVAL = 30000;

/** 标签页被切到后台时跳过本轮 —— 没人看的数据不值得占用限流额度。 */
function isPageHidden(): boolean {
  return typeof document !== 'undefined' && document.hidden;
}

export function GoldDataProvider({ children }: { children: ReactNode }) {
  // 统计数据
  const [stats, setStats] = useState<GoldStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);
  // 「上次取值时间」放 ref 而不是 state：它只是缓存判据，不参与渲染。
  // 用 state 会让 refreshStats/refreshCharts 每次取数后换一个函数身份，
  // 定时器随之被清掉重建 —— 节拍漂移，重订阅的中间态还可能丢一次轮询。
  const statsLastFetch = useRef<number>(0);
  
  // 日线数据
  const [dailyPrices, setDailyPrices] = useState<DailyPrice[]>([]);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [dailyError, setDailyError] = useState<string | null>(null);
  const dailyLastFetch = useRef<number>(0);
  
  // 相关性数据
  const [correlationData, setCorrelationData] = useState<CorrelationData[]>([]);
  const [correlationLoading, setCorrelationLoading] = useState(false);
  const [correlationError, setCorrelationError] = useState<string | null>(null);
  const correlationLastFetch = useRef<number>(0);
  
  // 实时美元指数
  const [dollarRealtime, setDollarRealtime] = useState<DollarRealtime | null>(null);
  
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // 获取统计数据
  const refreshStats = useCallback(async (force = false) => {
    const now = Date.now();
    if (!force && now - statsLastFetch.current < CACHE_DURATION) {
      return; // 使用缓存
    }
    
    setStatsLoading(true);
    setStatsError(null);
    try {
      const data = await goldApi.getStats();
      setStats(data);
      statsLastFetch.current = now;
      setLastUpdated(new Date());
    } catch (err) {
      // 统一翻译：原先固定写「获取统计数据失败」，把 429 限流、后端 503、
      // 断网都显示成同一句，用户既不知道发生了什么，也不知道该做什么。
      setStatsError(describeApiError(err, { fallback: '获取统计数据失败。' }));
      console.error('Failed to fetch stats:', err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // 获取图表数据（日线 + 相关性）
  const refreshCharts = useCallback(async (force = false) => {
    const now = Date.now();
    const shouldFetchDaily = force || now - dailyLastFetch.current >= CACHE_DURATION;
    const shouldFetchCorrelation = force || now - correlationLastFetch.current >= CACHE_DURATION;

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
        dailyLastFetch.current = now;
      }
      if (shouldFetchCorrelation) {
        const correlation = results[resultIndex++];

        // 获取实时美元指数并更新到最后一个数据点
        try {
          const dollarRealtime: DollarRealtime = await goldApi.getDollarRealtime();
          if (correlation && correlation.length > 0 && dollarRealtime) {
            // 用**行情自带的交易日**比较，不要用 UTC 日期。
            // `toISOString()` 取的是 UTC：东八区 00:00-08:00 之间它给出的是昨天，
            // 于是「最后一个点是不是今天」永远判 false，实时美元指数静默不更新。
            const quoteDate = dollarRealtime.date;
            const lastIndex = correlation.length - 1;

            if (quoteDate && correlation[lastIndex].date === quoteDate) {
              // 只有当最后一点确实是「今天」时，才用实时值更新它
              correlation[lastIndex] = {
                ...correlation[lastIndex],
                dollar_index: dollarRealtime.price
              };
            }
            // 否则不追加数据点。
            // 原实现会 push 一个日期为「今天」、金价却取自上一个历史交易日的点，
            // 等于在相关性图上凭空造出一个假数据点（旧金价配新美元指数），
            // 会误导对金价/美元负相关关系的判断。实时美元指数已由
            // dollarRealtime 单独暴露，不需要伪造历史序列。
          }
        } catch (dollarErr) {
          console.warn('获取实时美元指数失败，使用历史数据:', dollarErr);
        }

        setCorrelationData(correlation);
        correlationLastFetch.current = now;
      }

      setLastUpdated(new Date());
    } catch (err) {
      const message = describeApiError(err, { fallback: '获取图表数据失败。' });
      setDailyError(message);
      setCorrelationError(message);
      console.error('Failed to fetch chart data:', err);
    } finally {
      setDailyLoading(false);
      setCorrelationLoading(false);
    }
  }, []);

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
      const dollarData = await goldApi.getDollarRealtime();
      setDollarRealtime(dollarData);

      // 更新相关性数据中的美元指数
      setCorrelationData(prevData => {
        if (!prevData || prevData.length === 0) {
          return prevData;
        }

        // 同上：用行情自带的交易日，而不是 UTC 日期
        const quoteDate = dollarData.date;
        const lastIndex = prevData.length - 1;
        const newData = [...prevData];

        if (quoteDate && newData[lastIndex].date === quoteDate) {
          // 只有当最后一点确实是「今天」时，才用实时值更新它
          newData[lastIndex] = {
            ...newData[lastIndex],
            dollar_index: dollarData.price
          };
        }
        // 否则不追加数据点，理由同 refreshCharts：
        // 不要为「今天」伪造一个带着旧金价的数据点。

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

  // 定时刷新统计数据和图表数据（每 30 秒；页面隐藏时暂停，恢复时立即补一次）
  useEffect(() => {
    const tick = () => {
      if (isPageHidden()) return;
      refreshStats(true);
      refreshCharts(true);
    };
    const interval = setInterval(tick, POLL_INTERVAL);
    // 切回来的那一刻补一次：不必干等下一个 30 秒，用户看到的是新数据
    const onVisibilityChange = () => {
      if (!isPageHidden()) tick();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [refreshStats, refreshCharts]);

  // 定时刷新美元指数（同一档位；页面隐藏时同样暂停）
  useEffect(() => {
    // 立即执行一次
    refreshDollarRealtime();

    const tick = () => {
      if (isPageHidden()) return;
      refreshDollarRealtime();
    };
    const interval = setInterval(tick, POLL_INTERVAL);
    const onVisibilityChange = () => {
      if (!isPageHidden()) tick();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
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
