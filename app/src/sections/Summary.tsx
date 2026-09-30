import { useEffect, useRef, useState } from 'react';
import { modelLabel, useAiConfig } from '@/hooks/useAiConfig';
import PlaceholderNotice from '@/components/PlaceholderNotice';
import { describeApiError } from '@/lib/apiError';
import { isPlaceholder } from '@/lib/placeholder';
import { 
  CheckCircle2, 
  XCircle, 
  Scale, 
  TrendingUp, 
  Target,
  ArrowRight,
  Sparkles,
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
export default function Summary() {
  // 模型名从 /health 读，不写死 —— 它由后端 MIMO_MODEL 决定
  const aiConfig = useAiConfig();
  const [summary, setSummary] = useState<MarketSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPlaceholderData, setIsPlaceholderData] = useState(false);
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
      setIsPlaceholderData(isPlaceholder(response.metadata));
    } catch (err: any) {
      console.error('获取市场综合分析失败:', err);
      // 统一翻译：429 会说清等多久，503 会用后端给的原因，
      // 而不是一律「获取最新分析失败」—— 那对限流既不准也不可操作。
      setError(
        describeApiError(err, {
          fallback: '获取最新分析失败。',
          timeout: 'AI 分析耗时较长，请稍后重试刷新。',
        }),
      );
      // 不填充任何编造的内容：保持为 null，由空状态如实说明。
      setSummary(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = async () => {
    await fetchSummary(true);
  };

  // 全部来自接口。没有数据时保持为空 —— 不摆任何编造的结论或数字。
  const summaryData: SummaryPoint[] = summary ? [
    {
      type: 'bullish',
      title: '核心看涨逻辑',
      points: summary.core_bullish_logic || []
    },
    {
      type: 'bearish',
      title: '主要风险因素',
      points: summary.main_risks || []
    },
    {
      type: 'neutral',
      title: '市场共识',
      points: summary.market_consensus || []
    }
  ] : [];

  // 取不到价格时就是 null。原实现在这里写死了 5067 ——
  // 那是一个凭空的数字，会被当成「当前价格」展示在目标价表里。
  const realtimePrice = goldStats?.current_price ?? summary?.current_price ?? null;

  const priceTargets = summary?.institution_targets
    ? [
        ...summary.institution_targets.map(t => ({
          institution: t.institution,
          target: t.target,
          probability: t.probability,
          timeframe: t.timeframe
        })),
        ...(realtimePrice === null
          ? []
          : [{
              institution: '当前价格',
              target: realtimePrice,
              probability: '-',
              timeframe: '实时'
            }])
      ]
    : [];

  const comprehensiveJudgment = summary?.comprehensive_judgment || null;
  const coreView = summary?.core_view || '';

  // 有没有真内容：后端在「正在分析」时返回空列表 + status=analyzing
  const hasSummaryContent = Boolean(
    summary &&
      (summaryData.some((s) => s.points.length > 0) ||
        priceTargets.length > 0 ||
        coreView ||
        (comprehensiveJudgment &&
          Object.keys(comprehensiveJudgment).length > 0)),
  );

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
                    <span className="text-gray-300">MiMo 单轮结构化推理</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">大模型:</span>
                    <span className="text-gray-300">{modelLabel(aiConfig)}</span>
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
                    <span className="text-gray-300">看涨因子 + 看跌因子 + 机构观点 + 投资建议</span>
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
          {/* 缓存未命中时后端会先返回一份内置占位内容，必须明确标注， */}
          {/* 否则用户会把内置常量当成分析结论。 */}
          <PlaceholderNotice show={isPlaceholderData} testId="summary-placeholder" />
          {error && (
            <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>

        {/* 无内容状态：不摆任何编造的结论。
            「正在分析」时后端返回的是空内容 + status=analyzing，所以这里
            既要看响应是否存在，也要看里面有没有真东西。 */}
        {!loading && !hasSummaryContent && (
          <div data-testid="summary-unavailable" className="card-glass rounded-2xl p-12 text-center">
            {isPlaceholderData ? (
              <>
                <p className="text-gray-300 font-medium mb-2">市场总结正在分析中</p>
                <p className="text-gray-500 text-sm max-w-xl mx-auto">
                  后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一段内置文案 ——
                  编造的结论与真实分析长得一样，用户分不出来。
                </p>
              </>
            ) : (
              <>
                <p className="text-gray-300 font-medium mb-2">市场总结暂不可用</p>
                <p className="text-gray-500 text-sm max-w-xl mx-auto">
                  没能取到分析结果。这里不显示任何内置文案 ——
                  与其摆一段编造的综合判断，不如如实说明取不到。
                </p>
              </>
            )}
          </div>
        )}

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

              {/* 逐段判空：接口没给哪一段就不渲染哪一段，不用写死的文案补位 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {comprehensiveJudgment?.bullish_summary && (
                  <div>
                    <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      <CheckCircle2 className="w-5 h-5 text-green-400" />
                      看多理由占优
                    </h4>
                    <p className="text-gray-400 text-sm leading-relaxed">
                      {comprehensiveJudgment.bullish_summary}
                    </p>
                  </div>
                )}
                {comprehensiveJudgment?.bearish_summary && (
                  <div>
                    <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      <Scale className="w-5 h-5 text-amber-400" />
                      短期波动难免
                    </h4>
                    <p className="text-gray-400 text-sm leading-relaxed">
                      {comprehensiveJudgment.bearish_summary}
                    </p>
                  </div>
                )}
              </div>

              {coreView && (
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
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
