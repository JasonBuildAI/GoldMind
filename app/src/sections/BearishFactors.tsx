import { useEffect, useRef, useState } from 'react';
import { modelLabel, useAiConfig } from '@/hooks/useAiConfig';
import PlaceholderNotice from '@/components/PlaceholderNotice';
import { isPlaceholder } from '@/lib/placeholder';
import {
  TrendingDown,
  AlertTriangle,
  Zap,
  HandCoins,
  Scale,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  Brain,
  Sparkles,
  Bot
} from 'lucide-react';
import { analysisApi, type BearishFactor } from '../services/api';

// 图标映射
const iconMap: Record<string, React.ElementType> = {
  'rate-hike': Zap,
  'profit-taking': HandCoins,
  'geopolitical-ease': Scale,
  'dollar-strength': AlertTriangle,
  'economic-growth': TrendingDown,
  'other': TrendingDown
};

// 默认看空因子（当API不可用时使用）
export default function BearishFactors() {
  // 模型名从 /health 读，不写死 —— 它由后端 MIMO_MODEL 决定
  const aiConfig = useAiConfig();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [visibleItems, setVisibleItems] = useState<Set<string>>(new Set());
  // 初始为空：没有真实数据时宁可什么都不显示，也不摆一组编造的因子。
  const [factors, setFactors] = useState<BearishFactor[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isPlaceholderData, setIsPlaceholderData] = useState(false);
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // 获取看空因子数据
  const fetchFactors = async (forceRefresh: boolean = false) => {
    try {
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const response = await analysisApi.getBearishFactors(forceRefresh);

      // 先记占位标记：后端在「正在分析」时返回的是空列表，
      // 放在长度判断里面就永远设不上，页面会把「正在分析」错报成「暂不可用」。
      setIsPlaceholderData(isPlaceholder(response.metadata));

      if (response.bearish_factors && response.bearish_factors.length > 0) {
        setFactors(response.bearish_factors);
        setLastUpdated(response.last_updated);
      }
    } catch (err: any) {
      console.error('获取看空因子失败:', err);
      // 判断是否是超时错误
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setError('AI 分析耗时较长，请稍后重试刷新。');
      } else {
        setError('获取最新分析失败。');
      }
      // 不填充任何编造的内容：保持为空，由下面的空状态如实说明。
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // 手动刷新
  const handleRefresh = async () => {
    await fetchFactors(true);
  };

  useEffect(() => {
    // 组件加载时获取数据
    fetchFactors();
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const id = entry.target.getAttribute('data-id');
          if (id && entry.isIntersecting) {
            setVisibleItems((prev) => new Set([...prev, id]));
          }
        });
      },
      { threshold: 0.2, rootMargin: '-50px' }
    );

    itemRefs.current.forEach((ref) => {
      if (ref) observer.observe(ref);
    });

    return () => observer.disconnect();
  }, [factors]);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const getImpactLabel = (impact: string) => {
    switch (impact) {
      case 'high': return { text: '高影响', color: 'text-red-400 bg-red-400/10' };
      case 'medium': return { text: '中影响', color: 'text-amber-400 bg-amber-400/10' };
      case 'low': return { text: '低影响', color: 'text-green-400 bg-green-400/10' };
      default: return { text: '中影响', color: 'text-amber-400 bg-amber-400/10' };
    }
  };

  const getIcon = (id: string) => {
    return iconMap[id] || TrendingDown;
  };

  // 计算高影响因子数量
  const highImpactCount = factors.filter(f => f.impact === 'high').length;

  // 没有数据时明确说「不可用」，而不是拿内置文案冒充分析结论
  if (!loading && factors.length === 0) {
    return (
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="card-glass rounded-2xl p-12 text-center">
            {isPlaceholderData ? (
              <>
                <p className="text-gray-300 font-medium mb-2">看跌因子正在分析中</p>
                <p className="text-gray-500 text-sm max-w-xl mx-auto">
                  后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置内容 ——
                  编造的结论与真实分析长得一样，用户分不出来。
                </p>
              </>
            ) : (
              <>
                <p className="text-gray-300 font-medium mb-2">看跌因子暂不可用</p>
                <p className="text-gray-500 text-sm max-w-xl mx-auto">
                  没能取到分析结果。这里不显示任何内置文案 ——
              与其摆一段编造的结论，不如如实说明取不到。
                </p>
                {error && (
                  <p className="text-amber-400 text-sm mt-4">{error}</p>
                )}
              </>
            )}
            {/* 让用户能主动触发一次分析 —— 也只有在点了之后才会真的调 LLM */}
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshing}
              className="mt-6 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-300 text-sm transition-colors disabled:opacity-50"
            >
              {refreshing ? (
                <>
                  <Brain className="w-4 h-4 animate-pulse" />
                  <span>Agent分析中...</span>
                </>
              ) : (
                <>
                  <Bot className="w-4 h-4" />
                  <span>调用Agent重新分析</span>
                </>
              )}
            </button>
          </div>
        </div>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col items-center justify-center py-20">
            <div className="relative">
              <div className="absolute inset-0 bg-purple-500/20 blur-xl rounded-full animate-pulse"></div>
              <Brain className="w-12 h-12 text-purple-400 animate-pulse relative z-10" />
            </div>
            <span className="mt-4 text-purple-300 font-medium">市场分析Agent正在工作...</span>
            <span className="mt-1 text-gray-400 text-sm">基于大语言模型分析24小时内新闻资讯</span>
            <span className="mt-1 text-gray-500 text-sm">预计耗时10-30秒</span>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-16">
          {/* AI Agent Badge */}
          <div className="group relative inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/30 mb-6 cursor-help">
            <Brain className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-purple-300 font-medium">市场分析Agent</span>
            <Sparkles className="w-3 h-3 text-purple-400" />

            {/* Hover Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-80 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50">
              <div className="card-glass rounded-xl p-4 border border-gray-700/50 shadow-2xl">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-700/50">
                  <Brain className="w-5 h-5 text-purple-400" />
                  <span className="text-white font-bold">市场分析Agent</span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">技术栈:</span>
                    <span className="text-gray-300">MiMo 单轮结构化推理</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">大模型:</span>
                    <span className="text-gray-300">{modelLabel(aiConfig)}</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">架构:</span>
                    <span className="text-gray-300">ReAct推理架构 + 实时搜索插件</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">功能逻辑:</span>
                    <span className="text-gray-300">基于24小时新闻与市场数据，智能提取看空因子</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">数据来源:</span>
                    <span className="text-gray-300">最近24小时新闻（RSS + 数据库）+ 腾讯/新浪实时金价 + MySQL历史数据</span>
                  </div>
                </div>
                {/* Arrow */}
                <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1">
                  <div className="w-2 h-2 bg-gray-800 border-r border-b border-gray-700/50 transform rotate-45"></div>
                </div>
              </div>
            </div>
          </div>
          <h2 className="text-4xl font-bold text-white mb-4">
            黄金面临的<span className="text-red-400">潜在风险</span>
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto mb-4">
            基于大语言模型的市场分析Agent，实时分析新闻资讯与市场数据，智能生成看空因素
          </p>

          {/* 刷新按钮和更新时间 */}
          <div className="flex items-center justify-center gap-4">
            {/* 缓存未命中时后端会先返回一份内置占位内容，必须明确标注， */}
            {/* 否则用户会把内置常量当成分析结论。 */}
            <PlaceholderNotice show={isPlaceholderData} testId="bearish-placeholder" />
            {error && (
              <span className="text-amber-400 text-sm">{error}</span>
            )}
            {lastUpdated && (
              <span className="text-gray-500 text-sm">
                更新时间: {new Date(lastUpdated).toLocaleString('zh-CN')}
              </span>
            )}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-300 text-sm transition-colors disabled:opacity-50"
            >
              {refreshing ? (
                <>
                  <Brain className="w-4 h-4 animate-pulse" />
                  <span>Agent分析中...</span>
                </>
              ) : (
                <>
                  <Bot className="w-4 h-4" />
                  <span>调用Agent重新分析</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Factors Grid */}
        <div className="space-y-6">
          {factors.map((factor, index) => {
            const Icon = getIcon(factor.id);
            const impact = getImpactLabel(factor.impact);
            const isVisible = visibleItems.has(factor.id);
            const isExpanded = expandedId === factor.id;

            return (
              <div
                key={factor.id}
                ref={(el) => {
                  if (el) itemRefs.current.set(factor.id, el);
                }}
                data-id={factor.id}
                className={`transition-all duration-700 ${
                  isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
                }`}
                style={{ transitionDelay: `${index * 100}ms` }}
              >
                <div
                  className={`card-glass rounded-2xl overflow-hidden cursor-pointer transition-all duration-300 ${
                    isExpanded ? 'border-red-500/30 border' : 'hover:border-red-500/20'
                  }`}
                  onClick={() => toggleExpand(factor.id)}
                >
                  <div className="p-6">
                    <div className="flex items-start gap-6">
                      {/* Icon */}
                      <div className="flex-shrink-0 w-14 h-14 rounded-xl bg-gradient-to-br from-red-500/20 to-red-600/10 flex items-center justify-center">
                        <Icon className="w-7 h-7 text-red-400" />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mb-2">
                          <h3 className="text-xl font-bold text-white">{factor.title}</h3>
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${impact.color} w-fit`}>
                            {impact.text}
                          </span>
                        </div>
                        <p className="text-red-400 text-sm font-medium mb-2">{factor.subtitle}</p>
                        <p className="text-gray-400 leading-relaxed">{factor.description}</p>
                      </div>

                      {/* Expand Button */}
                      <div className="flex-shrink-0">
                        <button className="w-10 h-10 rounded-full bg-gray-800/50 flex items-center justify-center hover:bg-gray-700/50 transition-colors">
                          {isExpanded ? (
                            <ChevronUp className="w-5 h-5 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-400" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Expanded Details */}
                    <div className={`overflow-hidden transition-all duration-500 ${
                      isExpanded ? 'max-h-96 mt-6 pt-6 border-t border-gray-800' : 'max-h-0'
                    }`}>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {factor.details.map((detail, idx) => (
                          <div key={idx} className="flex items-start gap-3">
                            <ArrowRight className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                            <span className="text-gray-300 text-sm">{detail}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Summary Card */}
        <div className="mt-12 card-glass rounded-2xl p-8 gradient-bearish">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div>
              <h3 className="text-2xl font-bold text-white mb-2">风险警示</h3>
              <p className="text-gray-400 max-w-2xl">
                短期来看，美联储政策预期变化、获利了结压力、地缘风险缓和等因素可能导致金价回调。
                投资者需关注这些风险信号，做好风险管理。
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-red-400">{factors.length}</div>
                <div className="text-xs text-gray-500">潜在风险因素</div>
              </div>
              <div className="w-px h-12 bg-gray-700" />
              <div className="text-center">
                <div className="text-3xl font-bold text-red-400">{highImpactCount}</div>
                <div className="text-xs text-gray-500">高影响因子</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
