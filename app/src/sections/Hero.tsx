import { useEffect, useState } from 'react';
import { TrendingUp, DollarSign, Activity, Loader2, Brain, Sparkles, Bot, Zap, Target, Layers } from 'lucide-react';
import { useGoldData } from '@/contexts/GoldDataContext';

const fallbackStats = {
  current_price: 2823.0,
  start_price: 2823.0,
  ytd_return: 0,
  max_price: 2823.0,
  min_price: 2823.0,
  max_date: '2025-01-02',
  min_date: '2025-01-02',
  volatility: 0,
  market_status: '震荡',
  market_status_desc: '等待数据',
  updated_at: new Date().toISOString()
};

export default function Hero() {
  const { stats: contextStats, statsLoading, statsError } = useGoldData();
  const [stats, setStats] = useState(fallbackStats);
  const [error, setError] = useState<string | null>(null);
  const [hasInitialData, setHasInitialData] = useState(false);

  useEffect(() => {
    if (contextStats) {
      setStats(contextStats);
      setHasInitialData(true);
    }
    if (statsError) {
      setError('无法获取实时数据，显示默认数据');
    }
  }, [contextStats, statsError]);

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(price);
  };

  const getMarketStatusColor = (status: string) => {
    switch (status) {
      case '强势上涨':
      case '上涨':
        return 'text-green-400';
      case '下跌':
        return 'text-red-400';
      case '回调':
        return 'text-amber-400';
      case '高位震荡':
      case '震荡':
        return 'text-blue-400';
      default:
        return 'text-gray-400';
    }
  };

  return (
    <section className="relative min-h-[85vh] flex items-center justify-center overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 bg-gradient-to-b from-amber-900/10 via-transparent to-transparent" />
      <div className="absolute top-20 left-10 w-72 h-72 bg-amber-500/10 rounded-full blur-3xl animate-pulse-slow" />
      <div className="absolute bottom-20 right-10 w-96 h-96 bg-yellow-500/10 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1.5s' }} />
      
      {/* Grid Pattern */}
      <div 
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: `linear-gradient(rgba(212, 175, 55, 0.3) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(212, 175, 55, 0.3) 1px, transparent 1px)`,
          backgroundSize: '50px 50px'
        }}
      />

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center space-y-6">
          {/* AI Powered Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-purple-500/20 to-amber-500/20 border border-purple-500/30">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span className="text-sm bg-gradient-to-r from-purple-300 to-amber-300 bg-clip-text text-transparent font-medium">
              AI Agent 智能驱动
            </span>
            <Bot className="w-4 h-4 text-amber-400" />
          </div>

          {/* Main Title - 突出AI Agent */}
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight">
            <span className="text-white">AI Agent</span>
            <br />
            <span className="gold-text">黄金市场智能分析</span>
          </h1>

          {/* Subtitle - 强调AI能力 */}
          <p className="text-xl text-gray-400 max-w-3xl mx-auto leading-relaxed">
            基于大语言模型的多Agent协作系统，实时分析市场数据、新闻资讯与机构观点
            <br className="hidden sm:block" />
            智能生成看涨因子、看空因子、投资策略与价格预测
          </p>

          {/* AI Agent Capabilities */}
          <div className="flex flex-wrap items-center justify-center gap-3 max-w-4xl mx-auto">
            {[
              {
                icon: Brain,
                label: '市场分析Agent',
                color: 'text-purple-400',
                bg: 'bg-purple-500/10',
                border: 'border-purple-500/30',
                details: {
                  techStack: 'LangChain + 智谱AI GLM-4-Plus',
                  model: '智谱AI GLM-4-Plus (支持实时搜索)',
                  architecture: 'ReAct推理架构 + 实时搜索插件',
                  logic: '基于24小时新闻与市场数据，智能提取看涨/看空因子',
                  dataSource: '智谱AI实时搜索 + 腾讯财经API + MySQL历史数据'
                }
              },
              {
                icon: Target,
                label: '机构预测Agent',
                color: 'text-blue-400',
                bg: 'bg-blue-500/10',
                border: 'border-blue-500/30',
                details: {
                  techStack: 'LangChain + 智谱AI GLM-4-Plus',
                  model: '智谱AI GLM-4-Plus (支持实时搜索)',
                  architecture: '专用Agent架构 + 定向实时搜索',
                  logic: '实时抓取高盛、瑞银、摩根士丹利、花旗最新预测',
                  dataSource: '智谱AI实时搜索 + 机构官方报告 + 财经新闻'
                }
              },
              {
                icon: Zap,
                label: '新闻分析Agent',
                color: 'text-amber-400',
                bg: 'bg-amber-500/10',
                border: 'border-amber-500/30',
                details: {
                  techStack: 'LangChain + 智谱AI GLM-4-Plus',
                  model: '智谱AI GLM-4-Plus (支持实时搜索)',
                  architecture: '实时搜索 + 情感分析 + 实体识别',
                  logic: '24小时滚动抓取新闻，分析情感倾向与市场影响',
                  dataSource: '智谱AI实时搜索 + 新浪财经 + 腾讯财经'
                }
              },
              {
                icon: Bot,
                label: '投资建议Agent',
                color: 'text-green-400',
                bg: 'bg-green-500/10',
                border: 'border-green-500/30',
                details: {
                  techStack: 'LangChain + DeepSeek-V3 + RAG',
                  model: 'DeepSeek-V3 (671B参数)',
                  architecture: 'RAG检索增强生成，融合多源分析结果',
                  logic: '综合分析所有Agent输出，生成个性化投资策略',
                  dataSource: '市场分析Agent + 机构预测Agent + 新闻分析Agent'
                }
              },
              {
                icon: Layers,
                label: '综合分析Agent',
                color: 'text-pink-400',
                bg: 'bg-pink-500/10',
                border: 'border-pink-500/30',
                details: {
                  techStack: 'LangChain + DeepSeek-V3 + 多Agent协作',
                  model: 'DeepSeek-V3 (671B参数)',
                  architecture: '多Agent结果融合 + 深度推理生成',
                  logic: '整合所有Agent分析结果，生成全面市场认知与投资判断',
                  dataSource: '市场分析Agent + 机构预测Agent + 新闻分析Agent + 投资建议Agent'
                }
              },
            ].map((agent, index) => (
              <div
                key={index}
                className={`group relative flex items-center gap-2 px-3 py-1.5 rounded-full ${agent.bg} ${agent.border} border text-sm cursor-help transition-all duration-300 hover:scale-105`}
              >
                <agent.icon className={`w-3.5 h-3.5 ${agent.color}`} />
                <span className={`${agent.color} font-medium`}>{agent.label}</span>

                {/* Hover Tooltip */}
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-80 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50">
                  <div className="card-glass rounded-xl p-4 border border-gray-700/50 shadow-2xl">
                    <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-700/50">
                      <agent.icon className={`w-5 h-5 ${agent.color}`} />
                      <span className="text-white font-bold">{agent.label}</span>
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="flex gap-2">
                        <span className="text-gray-500 shrink-0">技术栈:</span>
                        <span className="text-gray-300">{agent.details.techStack}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-gray-500 shrink-0">大模型:</span>
                        <span className="text-gray-300">{agent.details.model}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-gray-500 shrink-0">架构:</span>
                        <span className="text-gray-300">{agent.details.architecture}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-gray-500 shrink-0">功能逻辑:</span>
                        <span className="text-gray-300">{agent.details.logic}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-gray-500 shrink-0">数据来源:</span>
                        <span className="text-gray-300">{agent.details.dataSource}</span>
                      </div>
                    </div>
                    {/* Arrow */}
                    <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1">
                      <div className="w-2 h-2 bg-gray-800 border-r border-b border-gray-700/50 transform rotate-45"></div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Loading State - 只在初始加载时显示 */}
          {statsLoading && !hasInitialData && (
            <div className="flex justify-center py-8">
              <div className="flex items-center gap-3 text-amber-400">
                <Loader2 className="w-6 h-6 animate-spin" />
                <span>正在获取实时金价...</span>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-sm">
              <span>{error}</span>
            </div>
          )}

          {/* Price Display - 有数据时一直显示 */}
          {(hasInitialData || !statsLoading) && (
            <div className="flex flex-col sm:flex-row items-center justify-center gap-6 mt-8">
              <div className="card-glass rounded-2xl p-6 min-w-[280px] relative overflow-hidden group hover:border-amber-500/30 transition-colors">
                {/* 实时标识 */}
                <div className="absolute top-3 right-3 flex items-center gap-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  <span className="text-xs text-green-400 font-medium">实时</span>
                </div>
                <div className="flex items-center gap-3 mb-2">
                  <DollarSign className="w-5 h-5 text-amber-400" />
                  <span className="text-gray-400 text-sm">纽约黄金期货</span>
                </div>
                <div className="text-4xl font-bold gold-text">
                  {formatPrice(stats.current_price)}
                </div>
                <div className="text-sm text-gray-500 mt-1">美元/盎司</div>
              </div>

              <div className="card-glass rounded-2xl p-6 min-w-[280px] relative overflow-hidden group hover:border-green-500/30 transition-colors">
                {/* 实时标识 */}
                <div className="absolute top-3 right-3 flex items-center gap-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  <span className="text-xs text-green-400 font-medium">实时</span>
                </div>
                <div className="flex items-center gap-3 mb-2">
                  <TrendingUp className="w-5 h-5 text-green-400" />
                  <span className="text-gray-400 text-sm">2025年至今涨幅</span>
                </div>
                <div className={`text-4xl font-bold ${stats.ytd_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {stats.ytd_return >= 0 ? '+' : ''}{stats.ytd_return.toFixed(2)}%
                </div>
                <div className="text-sm text-gray-500 mt-1">
                  从 {formatPrice(stats.start_price)} 起算
                </div>
              </div>
            </div>
          )}

          {/* Key Stats Grid - 有数据时一直显示 */}
          {(hasInitialData || !statsLoading) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 max-w-4xl mx-auto mt-8">
              <div className="card-glass rounded-xl p-4 relative overflow-hidden">
                {/* 24h更新标识 - 静态显示，不闪烁 */}
                <div className="absolute top-2 right-2 flex items-center gap-1">
                  <span className="inline-flex rounded-full h-1.5 w-1.5 bg-amber-500"></span>
                  <span className="text-[10px] text-amber-400 font-medium">24h更新</span>
                </div>
                <div className="text-gray-400 text-xs mb-1">期间最高</div>
                <div className="text-lg font-semibold text-white">{formatPrice(stats.max_price)}</div>
                <div className="text-xs text-gray-500">{stats.max_date}</div>
              </div>
              <div className="card-glass rounded-xl p-4 relative overflow-hidden">
                {/* 24h更新标识 - 静态显示，不闪烁 */}
                <div className="absolute top-2 right-2 flex items-center gap-1">
                  <span className="inline-flex rounded-full h-1.5 w-1.5 bg-amber-500"></span>
                  <span className="text-[10px] text-amber-400 font-medium">24h更新</span>
                </div>
                <div className="text-gray-400 text-xs mb-1">期间最低</div>
                <div className="text-lg font-semibold text-white">{formatPrice(stats.min_price)}</div>
                <div className="text-xs text-gray-500">{stats.min_date}</div>
              </div>
              <div className="card-glass rounded-xl p-4 relative overflow-hidden">
                {/* 24h更新标识 - 静态显示，不闪烁 */}
                <div className="absolute top-2 right-2 flex items-center gap-1">
                  <span className="inline-flex rounded-full h-1.5 w-1.5 bg-amber-500"></span>
                  <span className="text-[10px] text-amber-400 font-medium">24h更新</span>
                </div>
                <div className="text-gray-400 text-xs mb-1">波动区间</div>
                <div className="text-lg font-semibold text-amber-400">
                  {stats.volatility.toFixed(1)}%
                </div>
                <div className="text-xs text-gray-500">最大振幅</div>
              </div>
              <div className="card-glass rounded-xl p-4 relative overflow-hidden">
                {/* 实时标识 - 动态闪烁 */}
                <div className="absolute top-2 right-2 flex items-center gap-1">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500"></span>
                  </span>
                  <span className="text-[10px] text-green-400 font-medium">实时</span>
                </div>
                <div className="text-gray-400 text-xs mb-1">市场状态</div>
                <div className={`text-lg font-semibold ${getMarketStatusColor(stats.market_status)}`}>
                  {stats.market_status}
                </div>
                <div className="text-xs text-gray-500">{stats.market_status_desc}</div>
              </div>
            </div>
          )}

          {/* Scroll Indicator */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 animate-bounce">
            <span className="text-xs text-gray-500">向下滚动探索</span>
            <div className="w-6 h-10 rounded-full border-2 border-amber-500/30 flex justify-center pt-2">
              <div className="w-1.5 h-3 bg-amber-400 rounded-full" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
