import { useEffect, useRef, useState } from 'react';
import { modelLabel, useAiConfig } from '@/hooks/useAiConfig';
import PlaceholderNotice from '@/components/PlaceholderNotice';
import { describeApiError } from '@/lib/apiError';
import { isPlaceholder } from '@/lib/placeholder';
import {
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Wallet,
  PieChart,
  TrendingUp,
  Target,
  ArrowRight,
  AlertCircle,
  Loader2,
  Brain,
  Sparkles,
  Bot
} from 'lucide-react';
import { investmentAdviceApi, type InvestmentAdviceResponse, type InvestmentStrategy } from '../services/api';

interface StrategyCardProps {
  strategy: InvestmentStrategy;
  index: number;
  isVisible: boolean;
}

function StrategyCard({ strategy, index, isVisible }: StrategyCardProps) {
  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low': return 'text-green-400 bg-green-400/10 border-green-400/20';
      case 'medium': return 'text-amber-400 bg-amber-400/10 border-amber-400/20';
      case 'high': return 'text-red-400 bg-red-400/10 border-red-400/20';
      default: return 'text-gray-400 bg-gray-400/10 border-gray-400/20';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'conservative': return 'border-green-500/30';
      case 'balanced': return 'border-amber-500/30';
      case 'opportunistic': return 'border-red-500/30';
      default: return 'border-gray-500/30';
    }
  };

  const getRiskLabel = (level: string) => {
    switch (level) {
      case 'low': return '低风险';
      case 'medium': return '中风险';
      case 'high': return '高风险';
      default: return '未知';
    }
  };

  return (
    <div
      className={`transition-all duration-700 ${
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
      }`}
      style={{ transitionDelay: `${index * 150}ms` }}
    >
      <div className={`card-glass rounded-2xl p-6 h-full border ${getTypeColor(strategy.type)}`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold text-white">{strategy.title}</h3>
          <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${getRiskColor(strategy.risk_level)}`}>
            {getRiskLabel(strategy.risk_level)}
          </span>
        </div>

        <p className="text-gray-400 text-sm mb-6">{strategy.description}</p>

        {/* Allocation & Timeframe */}
        <div className="flex items-center gap-4 mb-6 p-3 bg-gray-900/50 rounded-lg">
          <div className="flex-1">
            <div className="text-xs text-gray-500">建议配置</div>
            <div className="text-lg font-semibold gold-text">{strategy.allocation}</div>
          </div>
          <div className="w-px h-8 bg-gray-700" />
          <div className="flex-1">
            <div className="text-xs text-gray-500">投资周期</div>
            <div className="text-lg font-semibold text-white">{strategy.timeframe}</div>
          </div>
        </div>

        {/* Entry Strategy */}
        <div className="mb-4 p-3 bg-green-900/20 rounded-lg border border-green-500/20">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-green-300">入场策略</span>
          </div>
          <div className="space-y-1 text-xs text-gray-400">
            <p><span className="text-gray-500">价位评估:</span> {strategy.entry_strategy?.current_price_assessment || '暂无数据'}</p>
            <p><span className="text-gray-500">建议区间:</span> {strategy.entry_strategy?.recommended_entry_range || '暂无数据'}</p>
            <p><span className="text-gray-500">入场时机:</span> {strategy.entry_strategy?.entry_timing || '暂无数据'}</p>
            <p><span className="text-gray-500">建仓方案:</span> {strategy.entry_strategy?.position_building || '暂无数据'}</p>
          </div>
        </div>

        {/* Exit Strategy */}
        <div className="mb-4 p-3 bg-red-900/20 rounded-lg border border-red-500/20">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-red-400" />
            <span className="text-sm font-medium text-red-300">退出策略</span>
          </div>
          <div className="space-y-1 text-xs text-gray-400">
            <p><span className="text-gray-500">止盈目标:</span> {strategy.exit_strategy?.profit_target || '暂无数据'}</p>
            <p><span className="text-gray-500">止损设置:</span> {strategy.exit_strategy?.stop_loss || '暂无数据'}</p>
            <p><span className="text-gray-500">再平衡:</span> {strategy.exit_strategy?.rebalancing_trigger || '暂无数据'}</p>
          </div>
        </div>

        {/* Pros */}
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <span className="text-sm font-medium text-gray-300">优势</span>
          </div>
          <ul className="space-y-1">
            {strategy.pros?.map((pro, idx) => (
              <li key={idx} className="text-gray-500 text-xs pl-6">• {pro}</li>
            )) || <li className="text-gray-500 text-xs pl-6">• 暂无数据</li>}
          </ul>
        </div>

        {/* Cons */}
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <XCircle className="w-4 h-4 text-red-400" />
            <span className="text-sm font-medium text-gray-300">劣势</span>
          </div>
          <ul className="space-y-1">
            {strategy.cons?.map((con, idx) => (
              <li key={idx} className="text-gray-500 text-xs pl-6">• {con}</li>
            )) || <li className="text-gray-500 text-xs pl-6">• 暂无数据</li>}
          </ul>
        </div>

        {/* Suitable For */}
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-medium text-gray-300">适合人群</span>
          </div>
          <ul className="space-y-1">
            {strategy.suitable_for?.map((item, idx) => (
              <li key={idx} className="text-gray-500 text-xs pl-6">• {item}</li>
            )) || <li className="text-gray-500 text-xs pl-6">• 暂无数据</li>}
          </ul>
        </div>

        {/* Execution Steps */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <ArrowRight className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-gray-300">执行步骤</span>
          </div>
          <ol className="space-y-1">
            {strategy.execution_steps?.map((step, idx) => (
              <li key={idx} className="text-gray-500 text-xs pl-6">{idx + 1}. {step}</li>
            )) || <li className="text-gray-500 text-xs pl-6">1. 暂无数据</li>}
          </ol>
        </div>
      </div>
    </div>
  );
}

export default function InvestmentAdvice() {
  // 模型名从 /health 读，不写死 —— 它由后端 MIMO_MODEL 决定
  const aiConfig = useAiConfig();
  const [advice, setAdvice] = useState<InvestmentAdviceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPlaceholderData, setIsPlaceholderData] = useState(false);
  const [visibleItems, setVisibleItems] = useState<Set<string>>(new Set());
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());



  useEffect(() => {
    fetchAdvice();
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
  }, [advice]);

  const fetchAdvice = async (forceRefresh: boolean = false) => {
    try {
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const response = await investmentAdviceApi.getInvestmentAdvice(forceRefresh);
      setAdvice(response);
      setIsPlaceholderData(isPlaceholder(response.metadata));
    } catch (err: any) {
      console.error('获取投资建议失败:', err);
      // 统一翻译：429 会说清等多久，503 会用后端给的原因，
      // 而不是一律「获取最新分析失败」—— 那对限流既不准也不可操作。
      setError(
        describeApiError(err, {
          fallback: '获取最新分析失败。',
          timeout: 'AI 分析耗时较长，请稍后重试刷新。',
        }),
      );
      // 使用默认数据
      setAdvice(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = async () => {
    await fetchAdvice(true);
  };

  // 全部来自接口。没有数据时保持为空 —— 不摆任何编造的策略。
  const strategies = advice?.strategies || [];
  const corePrinciples = advice?.core_principles || [];
  const marketAssessment = advice?.market_assessment;

  // 后端在「正在分析」时会返回**空内容 + status=analyzing**（不编造策略），
  // 所以这里判的是「有没有真内容」，而不是「响应是不是 null」。
  const hasContent = Boolean(
    advice &&
      (advice.strategies?.length ||
        advice.core_principles?.length ||
        (advice.market_assessment && Object.keys(advice.market_assessment).length)),
  );

  // 没有内容时明确说「正在分析」或「不可用」，而不是拿内置策略冒充分析结论
  if (!loading && !hasContent) {
    return (
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="card-glass rounded-2xl p-12 text-center">
            {isPlaceholderData ? (
              <>
                <p className="text-gray-300 font-medium mb-2">投资建议正在分析中</p>
                <p className="text-gray-500 text-sm max-w-xl mx-auto">
                  后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一套内置策略 ——
                  编造的建议与真实分析长得一样，用户分不出来。
                </p>
              </>
            ) : (
              <>
                <p className="text-gray-300 font-medium mb-2">投资建议暂不可用</p>
                <p className="text-gray-500 text-sm max-w-xl mx-auto">
                  没能取到分析结果。这里不显示任何内置策略 ——
                  与其摆一套编造的建议，不如如实说明取不到。
                </p>
                {error && (
                  <p className="text-amber-400 text-sm mt-4">{error}</p>
                )}
              </>
            )}
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
          <div className="group relative inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-500/10 border border-green-500/30 mb-6 cursor-help">
            <Brain className="w-4 h-4 text-green-400" />
            <span className="text-sm text-green-300 font-medium">投资建议Agent</span>
            <Sparkles className="w-3 h-3 text-green-400" />

            {/* Hover Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-80 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50">
              <div className="card-glass rounded-xl p-4 border border-gray-700/50 shadow-2xl">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-700/50">
                  <Brain className="w-5 h-5 text-green-400" />
                  <span className="text-white font-bold">投资建议Agent</span>
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
                    <span className="text-gray-300">RAG检索增强生成，融合多源分析结果</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">功能逻辑:</span>
                    <span className="text-gray-300">综合分析所有Agent输出，生成个性化投资策略</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">数据来源:</span>
                    <span className="text-gray-300">市场状态 + 看涨因子 + 看跌因子 + 机构观点</span>
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
            Agent驱动的<span className="gold-text">投资策略</span>建议
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto mb-6">
            基于大语言模型的投资建议Agent，综合分析市场数据、多空因子和机构观点，
            生成个性化的投资策略建议
          </p>

          {/* Refresh Button */}
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/10 border border-green-500/30 text-green-300 hover:bg-green-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
            {advice?.metadata?.generated_at && (
              <span className="text-xs text-gray-500">
                上次更新: {new Date(advice.metadata.generated_at).toLocaleString('zh-CN')}
              </span>
            )}
          </div>

          {/* Error Message */}
          {/* 缓存未命中时后端会先返回一份内置占位内容，必须明确标注， */}
          {/* 否则用户会把内置常量当成分析结论。 */}
          <PlaceholderNotice show={isPlaceholderData} testId="advice-placeholder" />
          {error && (
            <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>

        {/* Market Assessment */}
        {marketAssessment && (
          <div className="mb-12">
            <div className="card-glass rounded-2xl p-6 border border-amber-500/30">
              <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-amber-400" />
                市场评估
              </h3>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">当前位置</div>
                  <div className="text-base font-semibold text-white">{marketAssessment.current_position}</div>
                </div>
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">风险等级</div>
                  <div className={`text-base font-semibold ${
                    marketAssessment.risk_level === 'low' ? 'text-green-400' :
                    marketAssessment.risk_level === 'high' ? 'text-red-400' : 'text-amber-400'
                  }`}>
                    {marketAssessment.risk_level === 'low' ? '低风险' :
                     marketAssessment.risk_level === 'high' ? '高风险' : '中风险'}
                  </div>
                </div>
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">建议策略</div>
                  <div className="text-base font-semibold text-white">{marketAssessment.recommended_approach}</div>
                </div>
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">关键因素</div>
                  <div className="text-xs text-gray-300 leading-tight">
                    {marketAssessment.key_considerations?.slice(0, 2).join('、')}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Strategy Cards */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
            <span className="ml-3 text-gray-400">正在生成AI投资建议...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12">
            {strategies.map((strategy, index) => (
              <div
                key={strategy.title}
                ref={(el) => {
                  if (el) itemRefs.current.set(`strategy-${index}`, el);
                }}
                data-id={`strategy-${index}`}
              >
                <StrategyCard
                  strategy={strategy}
                  index={index}
                  isVisible={visibleItems.has(`strategy-${index}`)}
                />
              </div>
            ))}
          </div>
        )}

        {/* Key Points */}
        <div className="card-glass rounded-2xl p-8 mb-12">
          <h3 className="text-2xl font-bold text-white mb-8 text-center">核心投资原则</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {corePrinciples.map((point, index) => {
              const icons = [Shield, Clock, PieChart, Wallet];
              const Icon = icons[index % icons.length];
              const isVisible = visibleItems.has(`point-${index}`);

              return (
                <div
                  key={point.title}
                  ref={(el) => {
                    if (el) itemRefs.current.set(`point-${index}`, el);
                  }}
                  data-id={`point-${index}`}
                  className={`text-center transition-all duration-700 ${
                    isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
                  }`}
                  style={{ transitionDelay: `${(index + 3) * 150}ms` }}
                >
                  <div className="w-14 h-14 rounded-xl bg-amber-500/10 flex items-center justify-center mx-auto mb-4">
                    <Icon className="w-7 h-7 text-amber-400" />
                  </div>
                  <h4 className="text-lg font-semibold text-white mb-2">{point.title}</h4>
                  <p className="text-gray-400 text-sm">{point.description}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Risk Warning */}
        <div className="card-glass rounded-2xl p-6 border border-red-500/30">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <h4 className="text-lg font-bold text-white mb-2">风险提示</h4>
              <p className="text-gray-400 text-sm leading-relaxed">
                {advice?.risk_warning ||
                  "以上分析仅供参考，不构成投资建议。黄金价格受多种因素影响，波动较大。投资者应根据自身风险承受能力、投资目标和财务状况做出独立判断。过往表现不代表未来收益，投资有风险，入市需谨慎。"}
              </p>
              {advice?.disclaimer && (
                <p className="text-gray-500 text-xs mt-3">{advice.disclaimer}</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
