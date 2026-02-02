import { useEffect, useRef, useState } from 'react';
import { 
  TrendingUp, 
  Landmark, 
  Globe, 
  Scale, 
  Shield, 
  DollarSign,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Loader2,
  Brain,
  Sparkles,
  Bot
} from 'lucide-react';
import { analysisApi, type BullishFactor } from '../services/api';

// 图标映射
const iconMap: Record<string, React.ElementType> = {
  'fed-policy': Landmark,
  'central-bank': Scale,
  'dollar-credit': DollarSign,
  'geopolitical': Globe,
  'supply-demand': Shield,
  'other': Shield
};

// 默认看涨因子（当API不可用时使用）
const defaultFactors: BullishFactor[] = [
  {
    id: 'fed-policy',
    title: '美联储降息周期',
    subtitle: '货币政策转向宽松',
    description: '美联储从2024年9月开启降息周期，至今已累计降息六次。降息导致实际利率下行，黄金作为非孳息资产的吸引力大幅增强。',
    details: [
      '2024年9月启动本轮降息周期，已累计降息150个基点',
      '实际利率下行降低持有黄金的机会成本',
      '市场预计2026年将继续降息，支撑金价上行',
      '美联储政策独立性受扰，加剧市场不确定性'
    ],
    impact: 'high'
  },
  {
    id: 'central-bank',
    title: '全球央行持续购金',
    subtitle: '去美元化趋势加速',
    description: '2025年全球央行购金量达1136吨，连续第二年突破千吨级规模。新兴市场央行是购金主力军，推动储备多元化。',
    details: [
      '2025年央行购金1136吨，连续第二年超千吨',
      '波兰央行批准购买150吨黄金计划',
      '哈萨克斯坦、巴西、土耳其等国大幅增持',
      '全球央行外汇储备中美元占比降至58%'
    ],
    impact: 'high'
  },
  {
    id: 'dollar-credit',
    title: '美元信用动摇',
    subtitle: '美债规模突破38万亿美元',
    description: '美国政府债务规模超过38万亿美元，占GDP比重飙升至124%。每年需支付1.1万亿美元利息，引发对财政可持续性的担忧。',
    details: [
      '美国国债规模突破38万亿美元创历史新高',
      '债务占GDP比重达124%，远超警戒线',
      '年利息支出高达1.1万亿美元',
      '美元在全球外汇储备中占比持续下降'
    ],
    impact: 'high'
  },
  {
    id: 'geopolitical',
    title: '地缘政治风险',
    subtitle: '避险需求持续升温',
    description: '俄乌冲突、中东局势紧张、美国关税战等地缘政治"黑天鹅"事件频发，避险资金疯狂涌入黄金市场。',
    details: [
      '俄乌冲突持续，停火谈判进展缓慢',
      '中东局势紧张，伊朗核设施遇袭',
      '美国发起大规模关税战，全球贸易局势紧张',
      '美欧围绕格陵兰岛的博弈加剧'
    ],
    impact: 'medium'
  },
  {
    id: 'supply-demand',
    title: '供需失衡支撑',
    subtitle: '矿产金产量见顶',
    description: '2025年前三季度全球黄金总产量仅2717吨，同比仅增16吨。供需缺口达584吨，供应端刚性约束支撑价格。',
    details: [
      '2025年前三季度全球黄金产量2717吨，增幅极小',
      '黄金生产成本上升至1536美元/盎司',
      '供需缺口584吨，支撑价格上行',
      '优质资源枯竭限制长期供应增长'
    ],
    impact: 'medium'
  }
];

export default function BullishFactors() {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [visibleItems, setVisibleItems] = useState<Set<string>>(new Set());
  const [factors, setFactors] = useState<BullishFactor[]>(defaultFactors);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // 获取看涨因子数据
  const fetchFactors = async (forceRefresh: boolean = false) => {
    try {
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const response = await analysisApi.getBullishFactors(forceRefresh);

      if (response.bullish_factors && response.bullish_factors.length > 0) {
        setFactors(response.bullish_factors);
        setLastUpdated(response.last_updated);
      }
    } catch (err: any) {
      console.error('获取看涨因子失败:', err);
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
    return iconMap[id] || Shield;
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
                    <span className="text-gray-300">基于24小时新闻与市场数据，智能提取看涨因子</span>
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
            黄金上涨的<span className="text-green-400">核心驱动力</span>
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto mb-4">
            基于大语言模型的市场分析Agent，实时分析新闻资讯与市场数据，智能生成看涨因素
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
                    isExpanded ? 'gold-border' : 'hover:border-amber-500/30'
                  }`}
                  onClick={() => toggleExpand(factor.id)}
                >
                  <div className="p-6">
                    <div className="flex items-start gap-6">
                      {/* Icon */}
                      <div className="flex-shrink-0 w-14 h-14 rounded-xl bg-gradient-to-br from-green-500/20 to-green-600/10 flex items-center justify-center">
                        <Icon className="w-7 h-7 text-green-400" />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mb-2">
                          <h3 className="text-xl font-bold text-white">{factor.title}</h3>
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${impact.color} w-fit`}>
                            {impact.text}
                          </span>
                        </div>
                        <p className="text-green-400 text-sm font-medium mb-2">{factor.subtitle}</p>
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
                            <ArrowRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
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
        <div className="mt-12 card-glass rounded-2xl p-8 gradient-bullish">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div>
              <h3 className="text-2xl font-bold text-white mb-2">看涨逻辑总结</h3>
              <p className="text-gray-400 max-w-2xl">
                美联储降息周期、全球央行持续购金、美元信用动摇、地缘政治风险等多重因素形成共振，
                为黄金价格提供强劲的长期上涨动力。
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-green-400">{factors.length}</div>
                <div className="text-xs text-gray-500">核心看涨因素</div>
              </div>
              <div className="w-px h-12 bg-gray-700" />
              <div className="text-center">
                <div className="text-3xl font-bold text-green-400">{highImpactCount}</div>
                <div className="text-xs text-gray-500">高影响因子</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
