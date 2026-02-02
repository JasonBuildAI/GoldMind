import { useEffect, useRef, useState } from 'react';
import {
  Lightbulb,
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Wallet,
  PieChart,
  RefreshCw,
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
  const [advice, setAdvice] = useState<InvestmentAdviceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleItems, setVisibleItems] = useState<Set<string>>(new Set());
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // 默认策略数据
  const defaultStrategies: InvestmentStrategy[] = [
    {
      type: 'conservative',
      title: '保守配置策略',
      description: '适合风险厌恶型投资者，追求资产保值和稳定收益',
      allocation: '资产配置的5-10%',
      timeframe: '1-3年',
      risk_level: 'low',
      entry_strategy: {
        current_price_assessment: '建议等待回调后再入场',
        recommended_entry_range: '等待金价回调至2700-2750美元区间',
        entry_timing: '分批建仓，每次回调5%时加仓',
        position_building: '分4批建仓，每批25%，间隔2-4周'
      },
      exit_strategy: {
        profit_target: '年度收益目标8-12%',
        stop_loss: '单笔亏损不超过本金的5%',
        rebalancing_trigger: '金价涨幅超过20%时减仓一半'
      },
      pros: ['风险可控，适合保守投资者', '无需频繁操作', '长期对冲通胀'],
      cons: ['短期收益有限', '资金占用时间长', '可能错过快速上涨机会'],
      suitable_for: ['风险厌恶型投资者', '长期资产配置者', '退休规划人群'],
      execution_steps: ['等待回调至目标区间', '分批建仓，控制仓位', '设置止盈止损', '定期评估调整']
    },
    {
      type: 'balanced',
      title: '均衡配置策略',
      description: '适合有一定经验的投资者，在风险和收益之间寻求平衡',
      allocation: '资产配置的8-12%',
      timeframe: '6-12个月',
      risk_level: 'medium',
      entry_strategy: {
        current_price_assessment: '可小仓位试水',
        recommended_entry_range: '2750-2800美元区间',
        entry_timing: '分批建仓，结合技术指标',
        position_building: '分3批建仓，每批33%，根据技术信号调整'
      },
      exit_strategy: {
        profit_target: '阶段收益目标15-20%',
        stop_loss: '单笔亏损不超过本金的8%',
        rebalancing_trigger: '达到目标收益或跌破关键支撑位'
      },
      pros: ['灵活应对市场变化', '收益潜力较好', '风险相对可控'],
      cons: ['需要一定的市场判断能力', '需要关注市场动态', '可能面临短期波动'],
      suitable_for: ['有一定经验的投资者', '能承受中等波动的投资者', '有时间的投资者'],
      execution_steps: ['分析技术形态', '小仓位试探', '根据走势加仓或止损', '动态调整持仓']
    },
    {
      type: 'opportunistic',
      title: '机会型策略',
      description: '适合风险承受能力强的投资者，捕捉短期机会（严格限制仓位）',
      allocation: '资产配置的3-5%（严格限制）',
      timeframe: '1-3个月',
      risk_level: 'high',
      entry_strategy: {
        current_price_assessment: '仅适合极小部分资金参与',
        recommended_entry_range: '严格等待明确突破信号',
        entry_timing: '仅在关键技术位突破时',
        position_building: '单笔投入，严格止损'
      },
      exit_strategy: {
        profit_target: '短期目标10-15%',
        stop_loss: '严格止损，亏损不超过5%',
        rebalancing_trigger: '达到目标或触发止损立即离场'
      },
      pros: ['可能获得较高短期收益', '资金利用效率高'],
      cons: ['风险极高', '需要专业知识和经验', '容易受情绪影响', '可能快速亏损'],
      suitable_for: ['专业投资者', '风险承受能力极强', '有充足时间盯盘'],
      execution_steps: ['严格筛选入场时机', '小仓位参与', '设置严格止损', '及时止盈离场']
    }
  ];

  const defaultCorePrinciples = [
    { title: '风险管理', description: '永远把风险控制放在第一位，不要投入无法承受损失的资金' },
    { title: '仓位控制', description: '黄金配置不超过总资产的15%，单品种不超过10%' },
    { title: '再平衡', description: '每季度评估一次，根据市场变化调整配置比例' },
    { title: '长期视角', description: '黄金适合长期配置，避免频繁交易' }
  ];

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
    } catch (err: any) {
      console.error('获取投资建议失败:', err);
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setError('AI分析耗时较长，已显示默认策略。请稍后重试刷新。');
      } else {
        setError('获取最新分析失败，显示默认策略');
      }
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

  const strategies = advice?.strategies || defaultStrategies;
  const corePrinciples = advice?.core_principles || defaultCorePrinciples;
  const marketAssessment = advice?.market_assessment;

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
                    <span className="text-gray-300">LangChain + DeepSeek-V3 + RAG</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">大模型:</span>
                    <span className="text-gray-300">DeepSeek-V3 (671B参数)</span>
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
                    <span className="text-gray-300">市场分析Agent + 机构预测Agent + 新闻分析Agent</span>
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
