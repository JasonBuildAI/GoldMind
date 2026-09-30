import { useEffect, useRef, useState } from 'react';
import { modelLabel, useAiConfig } from '@/hooks/useAiConfig';
import PlaceholderNotice from '@/components/PlaceholderNotice';
import { describeApiError } from '@/lib/apiError';
import { isPlaceholder } from '@/lib/placeholder';
import { TrendingUp, TrendingDown, Minus, Target, Calendar, Brain, Sparkles, Bot } from 'lucide-react';
import { institutionApi, type InstitutionPrediction } from '../services/api';

// 默认机构预测（当API不可用时使用）
export default function InstitutionalViews() {
  // 模型名从 /health 读，不写死 —— 它由后端 MIMO_MODEL 决定
  const aiConfig = useAiConfig();
  const [visibleItems, setVisibleItems] = useState<Set<number>>(new Set());
  // 初始为空：没有真实数据时宁可什么都不显示，也不摆编造的机构目标价。
  const [institutions, setInstitutions] = useState<InstitutionPrediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isPlaceholderData, setIsPlaceholderData] = useState(false);
  const itemRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // 获取机构预测数据
  const fetchPredictions = async (forceRefresh: boolean = false) => {
    try {
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const response = await institutionApi.getInstitutionPredictions(forceRefresh);

      // 先记占位标记：后端在「正在分析」时返回的是空列表，
      // 放在长度判断里面就永远设不上，页面会把「正在分析」错报成「暂不可用」。
      setIsPlaceholderData(isPlaceholder(response.metadata));

      if (response.institutions && response.institutions.length > 0) {
        setInstitutions(response.institutions);
        setLastUpdated(response.last_updated);
      }
    } catch (err: any) {
      console.error('获取机构预测失败:', err);
      // 判断是否是超时错误
      // 统一翻译：429 会说清等多久，503 会用后端给的原因，
      // 而不是一律「获取最新分析失败」—— 那对限流既不准也不可操作。
      setError(
        describeApiError(err, {
          fallback: '获取最新分析失败。',
          timeout: 'AI 分析耗时较长，请稍后重试刷新。',
        }),
      );
      // 不填充任何编造的机构目标价：保持为空，由下面的空状态如实说明。
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // 手动刷新
  const handleRefresh = async () => {
    await fetchPredictions(true);
  };

  useEffect(() => {
    // 组件加载时获取数据
    fetchPredictions();
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const index = parseInt(entry.target.getAttribute('data-index') || '0');
          if (entry.isIntersecting) {
            setVisibleItems((prev) => new Set([...prev, index]));
          }
        });
      },
      { threshold: 0.2, rootMargin: '-50px' }
    );

    itemRefs.current.forEach((ref) => {
      if (ref) observer.observe(ref);
    });

    return () => observer.disconnect();
  }, [institutions]);

  const getRatingConfig = (rating: string) => {
    switch (rating) {
      case 'bullish':
        return {
          icon: TrendingUp,
          label: '看涨',
          color: 'text-green-400',
          bgColor: 'bg-green-400/10',
          borderColor: 'border-green-400/30'
        };
      case 'bearish':
        return {
          icon: TrendingDown,
          label: '看跌',
          color: 'text-red-400',
          bgColor: 'bg-red-400/10',
          borderColor: 'border-red-400/30'
        };
      default:
        return {
          icon: Minus,
          label: '中性',
          color: 'text-amber-400',
          bgColor: 'bg-amber-400/10',
          borderColor: 'border-amber-400/30'
        };
    }
  };

  // 计算各类机构数量
  const bullishCount = institutions.filter(i => i.rating === 'bullish').length;
  const bearishCount = institutions.filter(i => i.rating === 'bearish').length;
  const neutralCount = institutions.filter(i => i.rating === 'neutral').length;

  // 获取机构名称列表
  const getInstitutionNamesByRating = (rating: string) => {
    return institutions
      .filter(i => i.rating === rating)
      .map(i => i.name.split(' ')[0])
      .join('、');
  };

  // 没有数据时明确说「不可用」。机构目标价是最不能编的东西 ——
  // 产品方向第四节明确写了「不得凭模型印象编造机构目标价」。
  if (!loading && institutions.length === 0) {
    return (
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="card-glass rounded-2xl p-12 text-center">
            {isPlaceholderData ? (
              <>
                <p className="text-gray-300 font-medium mb-2">机构观点正在分析中</p>
                <p className="text-gray-500 text-sm max-w-xl mx-auto">
                  后端已开始分析，首次通常需要 1-2 分钟。这里不会先摆一份内置内容 ——
                  编造的结论与真实分析长得一样，用户分不出来。
                </p>
              </>
            ) : (
              <>
                <p className="text-gray-300 font-medium mb-2">机构观点暂不可用</p>
                <p className="text-gray-500 text-sm max-w-xl mx-auto">
                  没能取到机构观点。这里不显示任何目标价 ——
              编造机构目标价比留空更糟。
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

  if (loading) {
    return (
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col items-center justify-center py-20">
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full animate-pulse"></div>
              <Brain className="w-12 h-12 text-blue-400 animate-pulse relative z-10" />
            </div>
            <span className="mt-4 text-blue-300 font-medium">机构预测Agent正在工作...</span>
            <span className="mt-1 text-gray-400 text-sm">基于大语言模型实时抓取四大机构最新预测</span>
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
          <div className="group relative inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/30 mb-6 cursor-help">
            <Brain className="w-4 h-4 text-blue-400" />
            <span className="text-sm text-blue-300 font-medium">机构预测Agent</span>
            <Sparkles className="w-3 h-3 text-blue-400" />

            {/* Hover Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 w-80 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50">
              <div className="card-glass rounded-xl p-4 border border-gray-700/50 shadow-2xl">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-700/50">
                  <Brain className="w-5 h-5 text-blue-400" />
                  <span className="text-white font-bold">机构预测Agent</span>
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
                    <span className="text-gray-300">专用Agent架构 + 定向实时搜索</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">功能逻辑:</span>
                    <span className="text-gray-300">实时抓取高盛、瑞银、摩根士丹利、花旗最新预测</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-gray-500 shrink-0">数据来源:</span>
                    <span className="text-gray-300">最近24小时新闻（RSS + 数据库）+ 库内机构观点</span>
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
            华尔街<span className="gold-text">主流机构</span>观点汇总
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto mb-4">
            基于大语言模型的机构预测Agent，实时抓取高盛、瑞银、摩根士丹利、花旗四大机构最新预测
          </p>

          {/* 刷新按钮和更新时间 */}
          <div className="flex items-center justify-center gap-4">
            {/* 缓存未命中时后端会先返回一份内置占位内容，必须明确标注， */}
            {/* 否则用户会把内置常量当成分析结论。 */}
            <PlaceholderNotice show={isPlaceholderData} testId="institutions-placeholder" />
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
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-300 text-sm transition-colors disabled:opacity-50"
            >
              {refreshing ? (
                <>
                  <Brain className="w-4 h-4 animate-pulse" />
                  <span>Agent分析中...</span>
                </>
              ) : (
                <>
                  <Bot className="w-4 h-4" />
                  <span>调用Agent重新抓取</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Institution Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {institutions.map((inst, index) => {
            const rating = getRatingConfig(inst.rating);
            const RatingIcon = rating.icon;
            const isVisible = visibleItems.has(index);

            return (
              <div
                key={inst.name}
                ref={(el) => {
                  if (el) itemRefs.current.set(index, el);
                }}
                data-index={index}
                className={`transition-all duration-700 ${
                  isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
                }`}
                style={{ transitionDelay: `${index * 150}ms` }}
              >
                <div className="card-glass rounded-2xl p-6 h-full hover:border-amber-500/30 transition-all duration-300">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-6">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-amber-500/20 to-amber-600/10 flex items-center justify-center">
                        <span className="text-xl font-bold gold-text">{inst.logo}</span>
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-white">{inst.name}</h3>
                        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${rating.bgColor} ${rating.color} mt-1`}>
                          <RatingIcon className="w-3.5 h-3.5" />
                          {rating.label}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Target Price */}
                  <div className="flex items-center gap-6 mb-6 p-4 bg-gray-900/50 rounded-xl">
                    <div className="flex items-center gap-3">
                      <Target className="w-5 h-5 text-amber-400" />
                      <div>
                        <div className="text-xs text-gray-500">目标价格</div>
                        <div className="text-2xl font-bold gold-text">${inst.target_price.toLocaleString()}</div>
                      </div>
                    </div>
                    <div className="w-px h-12 bg-gray-700" />
                    <div className="flex items-center gap-3">
                      <Calendar className="w-5 h-5 text-amber-400" />
                      <div>
                        <div className="text-xs text-gray-500">时间框架</div>
                        <div className="text-lg font-semibold text-white">{inst.timeframe}</div>
                      </div>
                    </div>
                  </div>

                  {/* Reasoning */}
                  <div className="mb-4">
                    <p className="text-gray-300 text-sm leading-relaxed">{inst.reasoning}</p>
                  </div>

                  {/* Key Points */}
                  <div className="space-y-2">
                    {inst.key_points.map((point, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-2 flex-shrink-0" />
                        <span className="text-gray-400 text-sm">{point}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Consensus Summary */}
        <div className="mt-12 card-glass rounded-2xl p-8">
          <h3 className="text-2xl font-bold text-white mb-6 text-center">机构共识分析</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="text-4xl font-bold text-green-400 mb-2">{bullishCount}</div>
              <div className="text-white font-medium mb-1">看涨机构</div>
              <div className="text-gray-500 text-sm">{getInstitutionNamesByRating('bullish') || '-'}</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-amber-400 mb-2">{neutralCount}</div>
              <div className="text-white font-medium mb-1">中性机构</div>
              <div className="text-gray-500 text-sm">{getInstitutionNamesByRating('neutral') || '-'}</div>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-red-400 mb-2">{bearishCount}</div>
              <div className="text-white font-medium mb-1">谨慎机构</div>
              <div className="text-gray-500 text-sm">{getInstitutionNamesByRating('bearish') || '-'}</div>
            </div>
          </div>
          <div className="mt-8 pt-6 border-t border-gray-800 text-center">
            <p className="text-gray-400">
              <span className="text-amber-400 font-semibold">共识观点：</span>
              多数机构看好黄金长期走势，目标价集中在{Math.min(...institutions.map(i => i.target_price)).toLocaleString()}-{Math.max(...institutions.map(i => i.target_price)).toLocaleString()}美元区间。
              短期可能因美联储政策预期变化而震荡，但结构性买盘（央行购金、ETF流入）将为金价提供坚实支撑。
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
