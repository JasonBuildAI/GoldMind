import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, Dot } from 'recharts';
import { TrendingUp, BarChart3, Loader2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useGoldData } from '@/contexts/GoldDataContext';
import type { GoldPriceResponse } from '@/services/api';

// 闪烁的实时数据点组件
const RealtimeDot = (props: any) => {
  const { cx, cy, index, ...restProps } = props;
  if (cx == null || cy == null) return null;
  
  return (
    <g>
      {/* 外圈闪烁动画 */}
      <circle cx={cx} cy={cy} r={8} fill="#00FF00" opacity={0.3}>
        <animate attributeName="r" values="8;12;8" dur="1.5s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.3;0;0.3" dur="1.5s" repeatCount="indefinite" />
      </circle>
      {/* 中圈 */}
      <circle cx={cx} cy={cy} r={5} fill="#00FF00" opacity={0.6} />
      {/* 内圈高亮 */}
      <circle cx={cx} cy={cy} r={3} fill="#00FF00" />
    </g>
  );
};

interface PriceData {
  date: string;
  price: number;
  volume: number;
}

interface CorrelationDataLocal {
  date: string;
  dateLabel: string;
  gold_price: number;
  dollar_index: number;
}

const fallbackData: GoldPriceResponse = {
  daily: [
    { date: '2025-01-02', price: 2682, volume: 40141 },
    { date: '2025-02-01', price: 2800, volume: 3443 },
    { date: '2025-03-01', price: 3100, volume: 2649 },
    { date: '2025-04-01', price: 3350, volume: 2187 },
    { date: '2025-05-01', price: 3420, volume: 4519 },
    { date: '2025-06-01', price: 3480, volume: 3116 },
    { date: '2025-07-01', price: 3620, volume: 1822 },
    { date: '2025-08-01', price: 3700, volume: 2237 },
    { date: '2025-09-01', price: 3950, volume: 2554 },
    { date: '2025-10-01', price: 4100, volume: 2504 },
    { date: '2025-11-01', price: 4250, volume: 2800 },
    { date: '2025-12-01', price: 4400, volume: 3000 },
    { date: '2026-01-02', price: 4560, volume: 3500 },
    { date: '2026-01-28', price: 5361, volume: 4000 },
  ],
  correlation: [
    { date: '2025-01-15', gold_price: 2682, dollar_index: 108.2 },
    { date: '2025-02-15', gold_price: 2900, dollar_index: 107.5 },
    { date: '2025-03-15', gold_price: 3200, dollar_index: 105.8 },
    { date: '2025-04-15', gold_price: 3380, dollar_index: 104.2 },
    { date: '2025-05-15', gold_price: 3450, dollar_index: 103.5 },
    { date: '2025-06-15', gold_price: 3550, dollar_index: 102.8 },
    { date: '2025-07-15', gold_price: 3650, dollar_index: 101.5 },
    { date: '2025-08-15', gold_price: 3820, dollar_index: 100.2 },
    { date: '2025-09-15', gold_price: 4020, dollar_index: 99.5 },
    { date: '2025-10-15', gold_price: 4170, dollar_index: 100.8 },
    { date: '2025-11-15', gold_price: 4320, dollar_index: 101.5 },
    { date: '2025-12-15', gold_price: 4480, dollar_index: 102.2 },
    { date: '2026-01-15', gold_price: 4900, dollar_index: 101.8 },
  ]
};

// 格式化日期标签
const formatDateLabel = (dateStr: string) => {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}/${date.getDate()}`;
};

export default function PriceChart() {
  const { 
    dailyPrices, 
    correlationData: contextCorrelationData,
    dailyLoading,
    correlationLoading,
    dailyError,
    correlationError
  } = useGoldData();
  
  const [dailyData, setDailyData] = useState<PriceData[]>([]);
  const [correlationData, setCorrelationData] = useState<CorrelationDataLocal[]>([]);
  const [activeTab, setActiveTab] = useState('daily');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);

  // 从上下文同步数据
  useEffect(() => {
    if (dailyPrices.length > 0) {
      const dailyFormatted: PriceData[] = dailyPrices
        .map(item => ({
          date: item.date,
          price: item.price,
          volume: item.volume || 0
        }))
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
      setDailyData(dailyFormatted);
      setUsingFallback(false);
    }
  }, [dailyPrices]);

  useEffect(() => {
    if (contextCorrelationData.length > 0) {
      const correlationFormatted: CorrelationDataLocal[] = contextCorrelationData
        .map(item => ({
          date: item.date,
          dateLabel: formatDateLabel(item.date),
          gold_price: item.gold_price,
          dollar_index: item.dollar_index
        }))
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
      setCorrelationData(correlationFormatted);
    }
  }, [contextCorrelationData]);

  // 同步加载状态 - 只在初始加载时显示loading，有数据后刷新不显示
  useEffect(() => {
    // 只有在没有数据且正在加载时才显示loading
    const hasData = dailyData.length > 0 || correlationData.length > 0;
    const isLoading = dailyLoading || correlationLoading;
    
    // 如果有数据，永远不显示loading（保持图表显示）
    // 如果没有数据且正在加载，显示loading
    if (!hasData && isLoading) {
      setLoading(true);
    } else if (!isLoading) {
      setLoading(false);
    }
    // 如果有数据且正在加载，保持loading为false（不显示loading动画）
  }, [dailyLoading, correlationLoading, dailyData.length, correlationData.length]);

  // 同步错误状态
  useEffect(() => {
    if (dailyError || correlationError) {
      setError('加载数据失败，使用本地缓存数据');
      // 使用备用数据
      setDailyData(fallbackData.daily.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()));
      setCorrelationData(fallbackData.correlation.map(item => ({
        ...item,
        dateLabel: formatDateLabel(item.date)
      })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()));
      setUsingFallback(true);
    }
  }, [dailyError, correlationError]);

  const formatPrice = (price: number) => {
    return `$${price.toLocaleString()}`;
  };

  // 日线 tooltip
  const DailyTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="card-glass rounded-lg p-3 border border-amber-500/30">
          <p className="text-gray-300 text-sm mb-1">{label}</p>
          <p className="text-amber-400 font-semibold text-lg">
            {formatPrice(payload[0].value)}
          </p>
        </div>
      );
    }
    return null;
  };

  // 相关性 tooltip
  const CorrelationTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="card-glass rounded-lg p-3 border border-amber-500/30">
          <p className="text-gray-300 text-sm mb-2">{label}</p>
          <p className="text-amber-400 font-semibold">
            黄金: {formatPrice(payload[0].value)}
          </p>
          <p className="text-blue-400 font-semibold">
            美元指数: {payload[1].value.toFixed(2)}
          </p>
        </div>
      );
    }
    return null;
  };

  // 计算Y轴范围
  const getYDomain = (data: any[], key: string) => {
    if (data.length === 0) return [0, 100];
    const values = data.map(d => d[key]).filter(v => typeof v === 'number');
    if (values.length === 0) return [0, 100];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.1;
    return [Math.max(0, min - padding), max + padding];
  };

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/30 mb-6">
            <BarChart3 className="w-4 h-4 text-amber-400" />
            <span className="text-sm text-amber-200">价格走势分析</span>
          </div>
          <h2 className="text-4xl font-bold text-white mb-4">
            黄金价格<span className="gold-text">历史走势</span>
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto">
            从2025年初至今，黄金价格经历了波澜壮阔的上涨行情，年度涨幅接近80%
          </p>
        </div>

        {/* Loading State - 只在初始加载时显示 */}
        {loading && dailyData.length === 0 && correlationData.length === 0 && (
          <div className="card-glass rounded-2xl p-12 flex flex-col items-center justify-center">
            <Loader2 className="w-10 h-10 text-amber-400 animate-spin mb-4" />
            <p className="text-gray-400">正在加载数据...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="card-glass rounded-2xl p-6 mb-8 border border-amber-500/30 bg-amber-500/5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <p className="text-amber-400 font-medium">{error}</p>
                <p className="text-gray-500 text-sm">已切换到本地缓存数据，数据可能不是最新的</p>
              </div>
            </div>
          </div>
        )}

        {/* Data Source Badge - 显示实时数据状态，包括刷新指示器 */}
        {(dailyData.length > 0 || correlationData.length > 0) && (
          <div className="flex justify-end mb-6">
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs ${
              usingFallback 
                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                : 'bg-green-500/10 text-green-400 border border-green-500/30'
            }`}>
              {usingFallback ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  <span>本地缓存数据</span>
                </>
              ) : (
                <>
                  {/* 数据刷新时显示旋转动画 */}
                  {(dailyLoading || correlationLoading) ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                    </span>
                  )}
                  <span>{(dailyLoading || correlationLoading) ? '更新中...' : '实时数据'}</span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Chart Container - 有数据时一直显示 */}
        {(dailyData.length > 0 || correlationData.length > 0) && (
          <div className="card-glass rounded-2xl p-6">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
                <TabsList className="bg-gray-900/50 border border-gray-800">
                  <TabsTrigger value="daily" className="data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400">
                    <TrendingUp className="w-4 h-4 mr-2" />
                    日线走势
                  </TabsTrigger>
                  <TabsTrigger value="correlation" className="data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400">
                    <BarChart3 className="w-4 h-4 mr-2" />
                    黄金vs美元
                  </TabsTrigger>
                </TabsList>
                
                <div className="flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-amber-500" />
                    <span className="text-gray-400">黄金价格</span>
                  </div>
                  {activeTab === 'correlation' && (
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-blue-500" />
                      <span className="text-gray-400">美元指数</span>
                    </div>
                  )}
                </div>
              </div>

              {/* 日线走势 */}
              <TabsContent value="daily" className="mt-0">
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={dailyData}>
                      <defs>
                        <linearGradient id="goldGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#D4AF37" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#D4AF37" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" opacity={0.3} />
                      <XAxis 
                        dataKey="date" 
                        stroke="#666"
                        tick={{ fill: '#888', fontSize: 11 }}
                        tickFormatter={(value) => {
                          const date = new Date(value);
                          const year = date.getFullYear();
                          const month = date.getMonth() + 1;
                          const day = date.getDate();
                          return `${year}/${month}/${day}`;
                        }}
                        interval="preserveStartEnd"
                        minTickGap={50}
                        angle={-30}
                        textAnchor="end"
                        height={50}
                      />
                      <YAxis 
                        stroke="#666"
                        tick={{ fill: '#888', fontSize: 12 }}
                        tickFormatter={(value) => `$${(value / 1000).toFixed(1)}K`}
                        domain={getYDomain(dailyData, 'price')}
                      />
                      <Tooltip content={<DailyTooltip />} />
                      <Area 
                        type="monotone" 
                        dataKey="price" 
                        stroke="#D4AF37" 
                        strokeWidth={2}
                        fill="url(#goldGradient)"
                        dot={(props: any) => {
                          const { index, key, ...restProps } = props;
                          // 只显示最后一个点的闪烁效果
                          if (dailyData.length > 0 && index === dailyData.length - 1) {
                            return <RealtimeDot key={`dot-${index}`} {...restProps} index={index} />;
                          }
                          return null;
                        }}
                        activeDot={{ r: 6, fill: '#D4AF37', stroke: '#fff', strokeWidth: 2 }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </TabsContent>

              {/* 黄金vs美元 */}
              <TabsContent value="correlation" className="mt-0">
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={correlationData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" opacity={0.3} />
                      <XAxis 
                        dataKey="date" 
                        stroke="#666"
                        tick={{ fill: '#888', fontSize: 11 }}
                        tickFormatter={(value) => {
                          const date = new Date(value);
                          const year = date.getFullYear();
                          const month = date.getMonth() + 1;
                          const day = date.getDate();
                          return `${year}/${month}/${day}`;
                        }}
                        interval="preserveStartEnd"
                        minTickGap={50}
                        angle={-30}
                        textAnchor="end"
                        height={50}
                      />
                      <YAxis 
                        yAxisId="left"
                        stroke="#666"
                        tick={{ fill: '#888', fontSize: 12 }}
                        tickFormatter={(value) => `$${(value / 1000).toFixed(1)}K`}
                        domain={getYDomain(correlationData, 'gold_price')}
                      />
                      <YAxis 
                        yAxisId="right"
                        orientation="right"
                        stroke="#666"
                        tick={{ fill: '#888', fontSize: 12 }}
                        domain={[95, 110]}
                      />
                      <Tooltip content={<CorrelationTooltip />} />
                      <Line 
                        yAxisId="left"
                        type="monotone" 
                        dataKey="gold_price" 
                        stroke="#D4AF37" 
                        strokeWidth={2}
                        dot={(props: any) => {
                          const { index, key, ...restProps } = props;
                          // 只显示最后一个点的闪烁效果
                          if (correlationData.length > 0 && index === correlationData.length - 1) {
                            return <RealtimeDot key={`dot-${index}`} {...restProps} index={index} />;
                          }
                          return null;
                        }}
                        activeDot={{ r: 6, fill: '#D4AF37', stroke: '#fff', strokeWidth: 2 }}
                        name="黄金价格"
                      />
                      <Line 
                        yAxisId="right"
                        type="monotone" 
                        dataKey="dollar_index" 
                        stroke="#3B82F6" 
                        strokeWidth={2}
                        dot={(props: any) => {
                          const { index, key, cx, cy, ...restProps } = props;
                          // 只显示最后一个点的闪烁效果（蓝色版本）
                          if (correlationData.length > 0 && index === correlationData.length - 1) {
                            return (
                              <g key={`dollar-dot-${index}`}>
                                {/* 外圈闪烁动画 */}
                                <circle cx={cx} cy={cy} r={8} fill="#00FF00" opacity={0.3}>
                                  <animate attributeName="r" values="8;12;8" dur="1.5s" repeatCount="indefinite" />
                                  <animate attributeName="opacity" values="0.3;0;0.3" dur="1.5s" repeatCount="indefinite" />
                                </circle>
                                {/* 中圈 */}
                                <circle cx={cx} cy={cy} r={5} fill="#00FF00" opacity={0.6} />
                                {/* 内圈高亮 */}
                                <circle cx={cx} cy={cy} r={3} fill="#00FF00" />
                              </g>
                            );
                          }
                          return null;
                        }}
                        activeDot={{ r: 6, fill: '#3B82F6', stroke: '#fff', strokeWidth: 2 }}
                        name="美元指数"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
    </section>
  );
}
