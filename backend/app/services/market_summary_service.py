"""黄金市场综合分析服务 - 使用DeepSeek进行全方位市场总结"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
import asyncio
import json
import logging

from app.config import settings
from app.services.cache_manager import CacheManager

logger = logging.getLogger(__name__)

# 延迟导入langchain_openai
ChatOpenAI = None

def _get_chat_openai():
    """延迟加载ChatOpenAI类"""
    global ChatOpenAI
    if ChatOpenAI is None:
        from langchain_openai import ChatOpenAI as _ChatOpenAI
        ChatOpenAI = _ChatOpenAI
    return ChatOpenAI

# 全局线程池
_executor = ThreadPoolExecutor(max_workers=2)


class MarketSummaryAnalyzer:
    """使用DeepSeek分析所有市场数据，生成综合市场总结"""

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        """延迟创建LLM实例"""
        if self._llm is None:
            ChatOpenAIClass = _get_chat_openai()
            self._llm = ChatOpenAIClass(
                model=settings.MODEL_NAME,
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                temperature=0.7,
                max_tokens=4096
            )
        return self._llm

    def analyze(
        self,
        db: Session,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict],
        recent_news: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        分析所有市场数据，生成综合总结

        Args:
            db: 数据库会话
            market_status: 市场状态描述
            bullish_factors: 看涨因子列表
            bearish_factors: 看跌因子列表
            institution_predictions: 机构预测列表
            recent_news: 最近新闻列表（可选）

        Returns:
            综合市场分析结果
        """
        # 构建分析提示
        prompt = self._build_analysis_prompt(
            market_status,
            bullish_factors,
            bearish_factors,
            institution_predictions,
            recent_news
        )

        try:
            # 调用DeepSeek进行分析
            response = self.llm.invoke(prompt)
            analysis_text = response.content

            # 解析分析结果
            result = self._parse_analysis_result(analysis_text)
            return result

        except Exception as e:
            logger.error(f"DeepSeek分析失败: {e}")
            # 返回默认结构
            return self._get_default_analysis()

    def _build_analysis_prompt(
        self,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict],
        recent_news: List[Dict] = None
    ) -> str:
        """构建分析提示词"""

        # 整理看涨因子
        bullish_text = "\n".join([
            f"- {factor.get('title', '')}: {factor.get('description', '')} (影响强度: {factor.get('impact', '中')})"
            for factor in bullish_factors[:8]
        ]) if bullish_factors else "暂无数据"

        # 整理看跌因子
        bearish_text = "\n".join([
            f"- {factor.get('title', '')}: {factor.get('description', '')} (影响强度: {factor.get('impact', '中')})"
            for factor in bearish_factors[:8]
        ]) if bearish_factors else "暂无数据"

        # 整理机构预测
        institution_text = "\n".join([
            f"- {pred.get('name', '')}: 目标价${pred.get('target_price', 'N/A')}, "
            f"评级: {pred.get('rating', 'N/A')}, 时间框架: {pred.get('timeframe', 'N/A')}, "
            f"理由: {pred.get('reasoning', 'N/A')[:100]}..."
            for pred in institution_predictions[:6]
        ]) if institution_predictions else "暂无数据"

        # 整理新闻
        news_text = ""
        if recent_news:
            news_text = "\n".join([
                f"- [{news.get('sentiment', 'neutral')}] {news.get('title', '')}"
                for news in recent_news[:10]
            ])
        else:
            news_text = "暂无数据"

        prompt = f"""你是一位资深的黄金市场分析师，拥有20年以上的贵金属市场研究经验。

请基于以下全面的市场数据，生成一份详尽的黄金市场综合分析报告。

## 市场状态
{market_status}

## 看涨因素（核心支撑逻辑）
{bullish_text}

## 看跌因素（主要风险因素）
{bearish_text}

## 机构预测汇总
{institution_text}

## 最新市场新闻
{news_text}

---

请生成以下格式的JSON分析报告（确保是有效的JSON格式）：

{{
  "core_bullish_logic": [
    "提炼后的核心看涨逻辑1",
    "提炼后的核心看涨逻辑2",
    "提炼后的核心看涨逻辑3",
    "提炼后的核心看涨逻辑4",
    "提炼后的核心看涨逻辑5"
  ],
  "main_risks": [
    "提炼后的主要风险1",
    "提炼后的主要风险2",
    "提炼后的主要风险3",
    "提炼后的主要风险4",
    "提炼后的主要风险5"
  ],
  "market_consensus": [
    "市场共识要点1",
    "市场共识要点2",
    "市场共识要点3",
    "市场共识要点4"
  ],
  "institution_targets": [
    {{
      "institution": "机构名称",
      "target": 目标价格数字,
      "probability": "高/中/低",
      "timeframe": "时间框架"
    }}
  ],
  "current_price": 当前金价数字,
  "comprehensive_judgment": {{
    "bullish_summary": "看多理由的详细总结，约100字",
    "bearish_summary": "看空/风险因素的详细总结，约100字",
    "neutral_summary": "中性/平衡观点的详细总结，约100字"
  }},
  "core_view": "核心观点总结，一句话概括市场走势判断",
  "investment_recommendation": "投资建议总结，约50字",
  "confidence_level": "高/中/低",
  "time_horizon": "短期/中期/长期"
}}

要求：
1. 基于真实数据进行分析，不要编造信息
2. 提炼要点要简洁有力，每条不超过30字
3. 机构目标价要基于提供的预测数据
4. 综合判断要有深度洞察，体现专业性
5. 核心观点要鲜明，给出明确的市场方向判断
6. 必须返回有效的JSON格式"""

        return prompt

    def _parse_analysis_result(self, analysis_text: str) -> Dict[str, Any]:
        """解析DeepSeek返回的分析结果"""
        try:
            # 提取JSON部分
            json_start = analysis_text.find('{')
            json_end = analysis_text.rfind('}')

            if json_start != -1 and json_end != -1:
                json_str = analysis_text[json_start:json_end + 1]
                result = json.loads(json_str)
                return result
            else:
                raise ValueError("未找到JSON内容")

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            return self._get_default_analysis()
        except Exception as e:
            logger.error(f"解析分析结果失败: {e}")
            return self._get_default_analysis()

    def _get_default_analysis(self) -> Dict[str, Any]:
        """获取默认分析结果"""
        return {
            "core_bullish_logic": [
                "美联储降息周期降低持有黄金的机会成本",
                "全球央行持续购金，去美元化趋势加速",
                "美元信用动摇，美债规模持续扩大",
                "地缘政治风险支撑避险需求",
                "供需失衡，矿产金产量增长有限"
            ],
            "main_risks": [
                "美联储升息预期可能推迟降息时点",
                "高价位积累大量获利盘，回调压力增加",
                "地缘风险缓和可能导致避险溢价回落",
                "美元阶段性走强压制金价",
                "全球经济改善可能减弱避险需求"
            ],
            "market_consensus": [
                "多数机构看好长期走势",
                "短期可能因政策预期变化而震荡",
                "结构性买盘为金价提供支撑",
                "2026年或呈现高位震荡格局"
            ],
            "institution_targets": [
                {"institution": "高盛", "target": 5400, "probability": "高", "timeframe": "2026年底"},
                {"institution": "瑞银", "target": 5000, "probability": "高", "timeframe": "2026年9月"},
                {"institution": "摩根士丹利", "target": 4500, "probability": "中", "timeframe": "2026年中"}
            ],
            "current_price": 5067,
            "comprehensive_judgment": {
                "bullish_summary": "从基本面来看，黄金上涨的逻辑较为坚实。美联储降息预期、全球央行购金等因素形成支撑。",
                "bearish_summary": "短期波动风险不容忽视。政策预期变化、获利了结压力可能导致金价回调。",
                "neutral_summary": "建议采用分批建仓策略，控制仓位在总资产15%以内，做好风险管理。"
            },
            "core_view": "黄金处于长期牛市通道，2026年大概率维持高位震荡偏强格局。",
            "investment_recommendation": "建议投资者根据自身风险偏好，适度配置黄金资产。",
            "confidence_level": "中",
            "time_horizon": "中期"
        }


class MarketSummaryService:
    """市场综合分析服务 - 支持缓存优化"""

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = MarketSummaryAnalyzer()
        self.cache = CacheManager("market_summary", ttl=7200)  # 2小时

    def _get_realtime_price(self) -> float:
        """获取实时金价"""
        try:
            from app.services.gold_service import GoldService
            gold_service = GoldService(self.db)
            stats = gold_service.get_statistics()
            if stats:
                return stats.get("current_price", 5067)
        except Exception as e:
            print(f"[MarketSummary] 获取实时价格失败: {e}")
        return 5067

    def get_market_summary(
        self,
        market_status: str = "",
        bullish_factors: List[Dict] = None,
        bearish_factors: List[Dict] = None,
        institution_predictions: List[Dict] = None,
        recent_news: List[Dict] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        获取市场综合分析 - 快速响应版本（<50ms）

        Args:
            market_status: 市场状态
            bullish_factors: 看涨因子
            bearish_factors: 看跌因子
            institution_predictions: 机构预测
            recent_news: 最近新闻
            use_cache: 是否使用缓存

        Returns:
            市场综合分析结果
        """
        # 获取实时金价（用于覆盖结果中的价格）
        realtime_price = self._get_realtime_price()

        # 如果强制刷新，直接执行DeepSeek分析
        if not use_cache:
            print("[MarketSummary] 强制刷新，执行DeepSeek实时分析...")
            try:
                result = self.analyzer.analyze(
                    self.db,
                    market_status,
                    bullish_factors or [],
                    bearish_factors or [],
                    institution_predictions or [],
                    recent_news or []
                )
                # 用实时价格覆盖AI生成的价格
                result["current_price"] = realtime_price
                self.cache.set(result)
                result["metadata"] = {
                    "cached": False,
                    "cache_source": "deepseek_realtime",
                    "generated_at": datetime.now().isoformat(),
                    "data_sources": ["实时金价数据", "看涨因子", "看跌因子", "机构预测", "24小时新闻"],
                    "analysis_method": "DeepSeek LLM 综合分析"
                }
                return result
            except Exception as e:
                print(f"[MarketSummary] DeepSeek分析失败: {e}")
                pass

        # 1. 首先尝试文件缓存
        cached_data = self.cache.get()
        if cached_data:
            # 用实时价格覆盖缓存中的价格
            cached_data["current_price"] = realtime_price
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": datetime.now().isoformat(),
                "data_sources": ["实时金价数据", "看涨因子", "看跌因子", "机构预测", "24小时新闻"],
                "analysis_method": "DeepSeek LLM 综合分析"
            }
            return cached_data

        # 2. 无缓存时，返回默认数据并触发后台分析
        default_data = self._get_default_response()
        # 用实时价格覆盖默认价格
        default_data["current_price"] = realtime_price

        # 触发后台分析
        self._trigger_background_analysis(
            market_status,
            bullish_factors or [],
            bearish_factors or [],
            institution_predictions or [],
            recent_news or []
        )

        return default_data

    def _get_default_response(self) -> Dict[str, Any]:
        """获取默认响应"""
        return {
            "core_bullish_logic": [
                "美联储降息周期降低持有黄金的机会成本",
                "全球央行持续购金，去美元化趋势加速",
                "美元信用动摇，美债规模持续扩大",
                "地缘政治风险支撑避险需求",
                "供需失衡，矿产金产量增长有限"
            ],
            "main_risks": [
                "美联储升息预期可能推迟降息时点",
                "高价位积累大量获利盘，回调压力增加",
                "地缘风险缓和可能导致避险溢价回落",
                "美元阶段性走强压制金价",
                "全球经济改善可能减弱避险需求"
            ],
            "market_consensus": [
                "多数机构看好长期走势",
                "短期可能因政策预期变化而震荡",
                "结构性买盘为金价提供支撑",
                "2026年或呈现高位震荡格局"
            ],
            "institution_targets": [
                {"institution": "高盛", "target": 5400, "probability": "高", "timeframe": "2026年底"},
                {"institution": "瑞银", "target": 5000, "probability": "高", "timeframe": "2026年9月"},
                {"institution": "摩根士丹利", "target": 4500, "probability": "中", "timeframe": "2026年中"}
            ],
            "current_price": 5067,
            "comprehensive_judgment": {
                "bullish_summary": "从基本面来看，黄金上涨的逻辑较为坚实。美联储降息预期、全球央行购金等因素形成支撑。",
                "bearish_summary": "短期波动风险不容忽视。政策预期变化、获利了结压力可能导致金价回调。",
                "neutral_summary": "建议采用分批建仓策略，控制仓位在总资产15%以内，做好风险管理。"
            },
            "core_view": "黄金处于长期牛市通道，2026年大概率维持高位震荡偏强格局。",
            "investment_recommendation": "建议投资者根据自身风险偏好，适度配置黄金资产。",
            "confidence_level": "中",
            "time_horizon": "中期",
            "metadata": {
                "cached": True,
                "cache_source": "default",
                "generated_at": datetime.now().isoformat()
            }
        }

    def _trigger_background_analysis(
        self,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict],
        recent_news: List[Dict]
    ):
        """触发后台分析任务"""
        def analyze_in_background():
            try:
                print("[MarketSummary] 后台分析启动...")
                result = self.analyzer.analyze(
                    self.db,
                    market_status,
                    bullish_factors,
                    bearish_factors,
                    institution_predictions,
                    recent_news
                )
                self.cache.set(result)
                print("[MarketSummary] 后台分析完成，结果已缓存")
            except Exception as e:
                print(f"[MarketSummary] 后台分析失败: {e}")

        # 在线程池中执行
        _executor.submit(analyze_in_background)
