import { useEffect, useRef, useState } from 'react';
import {
  TrendingDown,
  AlertTriangle,
  Zap,
  HandCoins,
  Scale,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  RefreshCw,
  Loader2,
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
const defaultFactors: BearishFactor[] = [
  {
    id: 'rate-hike',
    title: '美联储升息预期',
    subtitle: '降息时点可能推迟',
    description: '若美国通胀持续高位运行，美联储可能推迟降息甚至重新升息。升息将提高持有黄金的机会成本，对金价形成压制。',
    details: [
      '关税政策带来的成本传导可能使通胀持续高位',
      '摩根士丹利预计降息时点推迟至6月和9月',
      '升息预期升温导致美元走强，压制金价',
      '实际利率上升降低黄金吸引力'
    ],
    impact: 'high'
  },
  {
    id: 'profit-taking',
    title: '获利了结压力',
    subtitle: '投机性头寸平仓',
    description: '金价快速上涨后积累大量获利盘，技术性回调需求增加。投机性头寸平仓可能引发连锁反应，导致短期剧烈波动。',
    details: [
      '2025年10月金价曾单日暴跌6%',
      'ETF市场结构失衡放大波动',
      '散户与机构行为分化加剧震荡',
      '高价位吸引获利盘出逃'
    ],
    impact: 'medium'
  },
  {
    id: 'geopolitical-ease',
    title: '地缘风险缓和',
    subtitle: '避险溢价回落',
    description: '若俄乌冲突出现停火进展、中美关系缓和等地缘风险降温，黄金的避险溢价将显著回落，可能导致价格调整。',
    details: [
      '俄乌停火谈判若取得进展将降低避险需求',
      '中美高层互动释放缓和信号',
      '地缘风险溢价回落导致金价调整',
      '避险需求常态化程度有限'
    ],
    impact: 'medium'
  },
  {
    id: 'dollar-strength',
    title: '美元阶段性走强',
    subtitle: '汇率效应压制金价',
    description: '美元指数阶段性反弹对金价形成直接压制。美元与黄金通常呈现负相关关系，美元走强时金价往往承压。',
    details: [
      '2025年10月美元指数上涨3.6%压制金价',
      '美国经济韧性支撑美元',
      '美元升值使黄金对其他货币持有者更贵',
      '汇率效应直接影响黄金计价'
    ],
    impact: 'medium'
  },
  {
    id: 'economic-growth',
    title: '全球经济改善',
    subtitle: '避险需求减弱',
    description: '若全球经济回到"金发女孩"状态（适度增长、低通胀），风险资产吸引力上升，黄金避险需求将相应减弱。',
    details: [
      '花旗预计2026年美国经济回到适中成长状态',
      '全球经济增长预期改善降低避险需求',
      '风险资产吸引力上升分流资金',
      '经济向好时黄金配置价值相对下降'
    ],
    impact: 'low'
  }
];

export default function BearishFactors() {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [visibleItems, setVisibleItems] = useState<Set<string>>(new Set());
  const [factors, setFactors] = useState<BearishFactor[]>(defaultFactors);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
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

      if (response.bearish_factors && response.bearish_factors.length > 0) {
        setFactors(response.bearish_factors);
        setLastUpdated(response.last_updated);
      }
    } catch (err: any) {
      console.error('获取看空因子失败:', err);
      // 判断是否是超时错误
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setError('AI分析耗时较长，已显示默认数据。请稍后重试刷新。');
      } else {
        setError('获取最新分析失败，显示默认数据');
      }
      // 使用默认数据
      setFactors(defaultFactors);
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
                    <span className="text-gray-300">LangChain + 智谱AI GLM-4-Plus</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">大模型:</span>
                    <span className="text-gray-300">智谱AI GLM-4-Plus (支持实时搜索)</span>
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
                    <span className="text-gray-300">智谱AI实时搜索 + 腾讯财经API + MySQL历史数据</span>
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
