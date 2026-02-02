import { useEffect, useRef, useState } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  Scale, 
  TrendingUp, 
  Target,
  ArrowRight,
  Sparkles,
  RefreshCw,
  Loader2,
  AlertTriangle,
  Brain,
  Bot
} from 'lucide-react';
import { marketSummaryApi, type MarketSummaryResponse } from '../services/api';
import { useGoldData } from '@/contexts/GoldDataContext';

interface SummaryPoint {
  type: 'bullish' | 'bearish' | 'neutral';
  title: string;
  points: string[];
}

// 默认数据
const defaultSummaryData: SummaryPoint[] = [
  {
    type: 'bullish',
    title: '核心看涨逻辑',
    points: [
      '美联储降息周期降低持有黄金的机会成本',
      '全球央行持续购金，去美元化趋势加速',
      '美元信用动摇，美债规模突破38万亿美元',
      '地缘政治风险支撑避险需求',
      '供需失衡，矿产金产量增长有限'
    ]
  },
  {
    type: 'bearish',
    title: '主要风险因素',
    points: [
      '美联储升息预期可能推迟降息时点',
      '高价位积累大量获利盘，回调压力增加',
      '地缘风险缓和可能导致避险溢价回落',
      '美元阶段性走强压制金价',
      '全球经济改善可能减弱避险需求'
    ]
  },
  {
    type: 'neutral',
    title: '市场共识',
    points: [
      '多数机构看好长期走势，目标4500-5400美元',
      '短期可能因政策预期变化而震荡',
      '结构性买盘为金价提供坚实支撑',
      '2026年或呈现高位震荡偏强格局'
    ]
  }
];

const defaultPriceTargets = [
  { institution: '高盛', target: 5400, probability: '高', timeframe: '2026年底' },
  { institution: '瑞银', target: 5000, probability: '高', timeframe: '2026年9月' },
  { institution: '摩根士丹利', target: 4500, probability: '中', timeframe: '2026年中' },
  { institution: '当前价格', target: 5067, probability: '-', timeframe: '实时' }
];

const defaultComprehensiveJudgment = {
  bullish_summary: '从基本面来看，黄金上涨的逻辑更为坚实。美联储降息周期、全球央行持续购金、美元信用动摇等结构性因素形成共振，为金价提供长期支撑。机构普遍看好2026年金价走势，目标价集中在4500-5400美元区间。',
  bearish_summary: '尽管长期趋势向好，但短期波动风险不容忽视。美联储政策预期变化、获利了结压力、地缘风险缓和等因素可能导致金价回调。建议采用分批建仓策略，控制仓位在总资产15%以内，做好风险管理。',
  neutral_summary: '市场处于多空博弈阶段，建议保持谨慎乐观态度，关注关键技术水平。'
};

const defaultCoreView = '黄金处于长期牛市通道，2026年大概率维持高位震荡偏强格局。建议投资者根据自身风险偏好，适度配置黄金资产，分享本轮黄金牛市红利。';

export default function Summary() {
  const [summary, setSummary] = useState<MarketSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleItems, setVisibleItems] = useState<Set<string>>(new Set());
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  
  // 使用 GoldDataContext 获取实时价格
  const { stats: goldStats } = useGoldData();

  useEffect(() => {
    fetchSummary();
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
  }, [summary]);

  const fetchSummary = async (forceRefresh: boolean = false) => {
    try {
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const response = await marketSummaryApi.getMarketSummary(forceRefresh);
      setSummary(response);
    } catch (err: any) {
      console.error('获取市场综合分析失败:', err);
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setError('AI分析耗时较长，已显示默认数据。请稍后重试刷新。');
      } else {
        setError('获取最新分析失败，显示默认数据');
      }
      // 使用默认数据
      setSummary(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = async () => {
    await fetchSummary(true);
  };

  // 使用API数据或默认数据
  const summaryData: SummaryPoint[] = summary ? [
    {
      type: 'bullish',
      title: '核心看涨逻辑',
      points: summary.core_bullish_logic || defaultSummaryData[0].points
    },
    {
      type: 'bearish',
      title: '主要风险因素',
      points: summary.main_risks || defaultSummaryData[1].points
    },
    {
      type: 'neutral',
      title: '市场共识',
      points: summary.market_consensus || defaultSummaryData[2].points
    }
  ] : defaultSummaryData;

  // 使用 GoldDataContext 的实时价格，如果没有则使用 summary 的数据
  const realtimePrice = goldStats?.current_price || summary?.current_price || 5067;
  
  const priceTargets = summary?.institution_targets ? [
    ...summary.institution_targets.map(t => ({
      institution: t.institution,
      target: t.target,
      probability: t.probability,
      timeframe: t.timeframe
    })),
    { 
      institution: '当前价格', 
      target: realtimePrice, 
      probability: '-', 
      timeframe: '实时' 
    }
  ] : defaultPriceTargets;

  const comprehensiveJudgment = summary?.comprehensive_judgment || defaultComprehensiveJudgment;
  const coreView = summary?.core_view || defaultCoreView;

  const getTypeStyles = (type: string) => {
    switch (type) {
      case 'bullish':
        return {
          borderColor: 'border-green-500/30',
          iconColor: 'text-green-400',
          bgColor: 'bg-green-500/10',
          icon: TrendingUp
        };
      case 'bearish':
        return {
          borderColor: 'border-red-500/30',
          iconColor: 'text-red-400',
          bgColor: 'bg-red-500/10',
          icon: XCircle
        };
      default:
        return {
          borderColor: 'border-amber-500/30',
          iconColor: 'text-amber-400',
          bgColor: 'bg-amber-500/10',
          icon: Scale
        };
    }
  };

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-16">
          {/* AI Agent Badge */}
          <div className="group relative inline-flex items-center gap-2 px-4 py-2 rounded-full bg-pink-500/10 border border-pink-500/30 mb-6 cursor-help">
            <Brain className="w-4 h-4 text-pink-400" />
            <span className="text-sm text-pink-300 font-medium">综合分析Agent</span>
            <Sparkles className="w-3 h-3 text-pink-400" />

            {/* Hover Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-80 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50">
              <div className="card-glass rounded-xl p-4 border border-gray-700/50 shadow-2xl">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-700/50">
                  <Brain className="w-5 h-5 text-pink-400" />
                  <span className="text-white font-bold">综合分析Agent</span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">技术栈:</span>
                    <span className="text-gray-300">LangChain + DeepSeek-V3 + 多Agent协作</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">大模型:</span>
                    <span className="text-gray-300">DeepSeek-V3 (671B参数)</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">架构:</span>
                    <span className="text-gray-300">多Agent结果融合 + 深度推理生成</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">功能逻辑:</span>
                    <span className="text-gray-300">整合所有Agent分析结果，生成全面市场认知与投资判断</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">数据来源:</span>
                    <span className="text-gray-300">市场分析Agent + 机构预测Agent + 新闻分析Agent + 投资建议Agent</span>
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
            黄金市场<span className="gold-text">综合分析</span>
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto mb-6">
            基于大语言模型的综合分析Agent，整合多空因素、机构观点和市场数据，
            生成全面的市场认知和投资判断
          </p>

          {/* Refresh Button */}
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500/10 border border-purple-500/30 text-purple-300 hover:bg-purple-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
            {summary?.metadata?.generated_at && (
              <span className="text-xs text-gray-500">
                上次更新: {new Date(summary.metadata.generated_at).toLocaleString('zh-CN')}
              </span>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>

        {/* Summary Cards */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
            <span className="ml-3 text-gray-400">正在生成AI市场分析...</span>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12">
              {summaryData.map((item, index) => {
                const styles = getTypeStyles(item.type);
                const Icon = styles.icon;
                const isVisible = visibleItems.has(`summary-${index}`);

                return (
                  <div
                    key={item.title}
                    ref={(el) => {
                      if (el) itemRefs.current.set(`summary-${index}`, el);
                    }}
                    data-id={`summary-${index}`}
                    className={`transition-all duration-700 ${
                      isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
                    }`}
                    style={{ transitionDelay: `${index * 150}ms` }}
                  >
                    <div className={`card-glass rounded-2xl p-6 h-full border ${styles.borderColor}`}>
                      <div className="flex items-center gap-3 mb-6">
                        <div className={`w-12 h-12 rounded-xl ${styles.bgColor} flex items-center justify-center`}>
                          <Icon className={`w-6 h-6 ${styles.iconColor}`} />
                        </div>
                        <h3 className="text-xl font-bold text-white">{item.title}</h3>
                      </div>

                      <ul className="space-y-3">
                        {item.points.map((point, idx) => (
                          <li key={idx} className="flex items-start gap-3">
                            <ArrowRight className={`w-4 h-4 ${styles.iconColor} mt-1 flex-shrink-0`} />
                            <span className="text-gray-300 text-sm leading-relaxed">{point}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Price Targets */}
            <div className="card-glass rounded-2xl p-8 mb-12">
              <div className="flex items-center gap-3 mb-8">
                <Target className="w-6 h-6 text-amber-400" />
                <h3 className="text-2xl font-bold text-white">机构目标价汇总</h3>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
                {priceTargets.map((item) => (
                  <div key={item.institution} className="text-center">
                    <div className="text-gray-400 text-sm mb-2">{item.institution}</div>
                    <div className={`text-3xl font-bold ${
                      item.institution === '当前价格' ? 'gold-text' : 'text-white'
                    }`}>
                      ${item.target.toLocaleString()}
                    </div>
                    <div className="text-gray-500 text-xs mt-1">{item.timeframe}</div>
                    {item.probability !== '-' && (
                      <div className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs mt-2 ${
                        item.probability === '高' 
                          ? 'bg-green-400/10 text-green-400' 
                          : item.probability === '中'
                          ? 'bg-amber-400/10 text-amber-400'
                          : 'bg-red-400/10 text-red-400'
                      }`}>
                        置信度: {item.probability}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Final Verdict */}
            <div className="card-glass rounded-2xl p-8 gold-border">
              <div className="text-center mb-8">
                <h3 className="text-2xl font-bold text-white mb-2">综合判断</h3>
                <div className="w-20 h-1 gold-gradient mx-auto rounded-full" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                  <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                    看多理由占优
                  </h4>
                  <p className="text-gray-400 text-sm leading-relaxed">
                    {comprehensiveJudgment.bullish_summary}
                  </p>
                </div>
                <div>
                  <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Scale className="w-5 h-5 text-amber-400" />
                    短期波动难免
                  </h4>
                  <p className="text-gray-400 text-sm leading-relaxed">
                    {comprehensiveJudgment.bearish_summary}
                  </p>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-gray-800 text-center">
                <p className="text-lg text-gray-300">
                  <span className="gold-text font-semibold">核心观点：</span>
                  {coreView}
                </p>
                {summary?.investment_recommendation && (
                  <p className="text-gray-400 text-sm mt-3">
                    {summary.investment_recommendation}
                  </p>
                )}
                {summary?.confidence_level && (
                  <div className="mt-4 inline-flex items-center gap-2">
                    <span className="text-gray-500 text-xs">置信度:</span>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      summary.confidence_level === '高' 
                        ? 'bg-green-400/10 text-green-400' 
                        : summary.confidence_level === '中'
                        ? 'bg-amber-400/10 text-amber-400'
                        : 'bg-red-400/10 text-red-400'
                    }`}>
                      {summary.confidence_level}
                    </span>
                    {summary.time_horizon && (
                      <>
                        <span className="text-gray-500 text-xs ml-2">时间框架:</span>
                        <span className="text-gray-400 text-xs">{summary.time_horizon}</span>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
