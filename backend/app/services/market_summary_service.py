"""黄金市场综合分析服务 - 使用 LLM 进行全方位市场总结"""
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
import asyncio
import json
import logging
import re

from app.services.news_service import NEWS_PROMPT_LIMIT, format_news_for_prompt
from app.utils import timeutil
from app.config import settings
from app.services.cache_manager import CacheManager, AI_ANALYSIS_CACHE_TTL
from app.services.single_flight import single_flight
from app.services.institution_prediction_service import (
    INSTITUTIONS,
    _normalize_text,
    match_institution,
)
from app.services.llm_provider import (
    describe_completion,
    get_chat_llm,
    retry_on_content_filter,
)
from loguru import logger

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# 机构数据的诚实性守卫
#
# `institution_predictions` 里「暂无最新预测」的占位行（target_price 为空、
# rating 缺省为 neutral、reasoning 是固定文案）只表示「窗口期内没有可核实
# 预测」，**不代表**机构给出中性评级。把占位行当评级喂给 LLM，会产出
# 「四大投行集体中性」这类不存在的机构判断 —— 缓存里真实发生过。
# --------------------------------------------------------------------------- #

PLACEHOLDER_INSTITUTION_REASONINGS = {"暂无最新预测"}

# 泛指机构的词：无法映射到具体机构时也按「不可核实」处理。
# 「机构」从严保留在表内：宁可少展示一条要点，不展示无法核实的机构判断。
GENERIC_INSTITUTION_TERMS = ("投行", "机构", "华尔街", "wall street")


def usable_institution_predictions(
    predictions: Optional[List[Dict]],
) -> List[Dict]:
    """只保留可核实的机构行；占位行（无目标价、无日期、占位理由）不算数据。"""
    usable: List[Dict] = []
    for pred in predictions or []:
        if not isinstance(pred, dict):
            continue
        reasoning = str(pred.get("reasoning") or "").strip()
        if (
            pred.get("target_price") is not None
            or pred.get("as_of_date")
            or (reasoning and reasoning not in PLACEHOLDER_INSTITUTION_REASONINGS)
        ):
            usable.append(pred)
    return usable


def _text_of(item: Any) -> str:
    """把要点条目（字符串 / 字典 / 列表）拼成可扫描的文本。"""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return " ".join(_text_of(value) for value in item.values())
    if isinstance(item, (list, tuple)):
        return " ".join(_text_of(value) for value in item)
    return "" if item is None else str(item)


def _alias_matcher(alias: str):
    """把注册表别名编译成扫描器；两字母拉丁缩写不参与（误报多于收益）。"""
    normalized = _normalize_text(alias)
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in normalized)
    if not normalized or (not has_cjk and len(normalized) < 3):
        return None
    if has_cjk:
        return ("substring", normalized)
    return ("regex", re.compile(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])"))


def _build_institution_alias_matchers():
    matchers = []
    for inst in INSTITUTIONS:
        for alias in inst.aliases:
            matcher = _alias_matcher(alias)
            if matcher is not None:
                matchers.append((matcher[0], matcher[1], inst.key))
    return tuple(matchers)


_INSTITUTION_ALIAS_MATCHERS = _build_institution_alias_matchers()


def _institutions_mentioned(text: str) -> set:
    normalized = _normalize_text(text)
    mentioned = set()
    for kind, matcher, key in _INSTITUTION_ALIAS_MATCHERS:
        if kind == "substring":
            if matcher in normalized:
                mentioned.add(key)
        elif matcher.search(normalized):
            mentioned.add(key)
    return mentioned


def _entry_is_verifiable(text: str, allowed_keys: set) -> bool:
    """条目里的机构指称必须全部可核实；泛指机构（投行/机构）同样不行。"""
    mentioned = _institutions_mentioned(text)
    if mentioned:
        return mentioned <= allowed_keys
    normalized = _normalize_text(text)
    return not any(term in normalized for term in GENERIC_INSTITUTION_TERMS)


def sanitize_institution_claims(
    result: Dict[str, Any],
    institution_predictions: Optional[List[Dict]],
) -> Dict[str, Any]:
    """机构数据缺失时清掉 LLM 输出里的机构判断；有数据时只保留可核实机构。

    - `institution_targets`：仅保留名称可匹配到「可核实机构」的条目；
      数据缺失时结果必然为空数组。
    - 列表字段（核心看涨逻辑 / 主要风险 / 市场共识）：删除提及不可核实机构
      或泛指机构的条目。宁可少一条要点，不展示无法核实的内容。
    """
    cleaned = dict(result) if isinstance(result, dict) else {}

    allowed_keys = set()
    for pred in usable_institution_predictions(institution_predictions):
        inst = match_institution(pred.get("name"))
        if inst is not None:
            allowed_keys.add(inst.key)

    for field in ("core_bullish_logic", "main_risks", "market_consensus"):
        items = cleaned.get(field)
        if isinstance(items, list):
            cleaned[field] = [
                item
                for item in items
                if _entry_is_verifiable(_text_of(item), allowed_keys)
            ]

    targets = cleaned.get("institution_targets")
    kept = []
    for target in targets if isinstance(targets, list) else []:
        claimed = target.get("institution") if isinstance(target, dict) else target
        inst = match_institution(claimed)
        if inst is not None and inst.key in allowed_keys:
            kept.append(target)
    cleaned["institution_targets"] = kept

    return cleaned


# 全局线程池
_executor = ThreadPoolExecutor(max_workers=2)

class MarketSummaryAnalyzer:
    """使用 LLM 分析所有市场数据，生成综合市场总结"""

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        """延迟创建 LLM 实例（供应商由 llm_provider 工厂统一决定）"""
        if self._llm is None:
            self._llm = get_chat_llm(temperature=0.7)
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
            # 调用 LLM 进行分析
            response = retry_on_content_filter(self.llm, prompt)
            analysis_text = response.content

            # 解析分析结果；提示词之外再用确定性规则兜一道机构数据诚实性
            result = self._parse_analysis_result(analysis_text, response)
            return sanitize_institution_claims(result, institution_predictions)

        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
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

        # 整理机构预测：只喂可核实行 —— 占位行（rating 缺省 neutral、理由
        # 「暂无最新预测」）代表的不是观点，喂进去只会被误读成机构评级。
        usable_institutions = usable_institution_predictions(institution_predictions)
        institution_text = "\n".join([
            f"- {pred.get('name', '')}: 目标价${pred.get('target_price', 'N/A')}, "
            f"评级: {pred.get('rating', 'N/A')}, 时间框架: {pred.get('timeframe', 'N/A')}, "
            f"理由: {pred.get('reasoning', 'N/A')[:100]}..."
            for pred in usable_institutions[:6]
        ]) if usable_institutions else "暂无数据"

        # 整理新闻（统一入口）
        #
        # 原实现打的是 `news.get('sentiment')`，而入库时 sentiment 一律是
        # NEUTRAL（见 news_service.save_news）—— 把恒定值喂给模型只是噪音，
        # 还容易让它以为做过情感分析。换成发布时间，那才是有信息量的字段。
        news_text = (
            format_news_for_prompt(recent_news, limit=NEWS_PROMPT_LIMIT)
            if recent_news
            else "暂无数据"
        )

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
3. 机构目标价要基于提供的预测数据；未提供可核实预测的机构，不得描述其评级、方向或目标价
4. 若「机构预测汇总」为「暂无数据」，institution_targets 必须为空数组，所有字段都不得出现机构名称、机构评级或机构共识判断
5. 综合判断要有深度洞察，体现专业性
6. 核心观点要鲜明，给出明确的市场方向判断
7. 必须返回有效的JSON格式"""

        return prompt

    def _parse_analysis_result(
        self, analysis_text: str, response: Any = None
    ) -> Dict[str, Any]:
        """解析 LLM 返回的分析结果（response 仅用于失败时记录 finish_reason）"""
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
            logger.error(f"JSON解析错误: {e}（{describe_completion(response)}）")
            return self._get_default_analysis()
        except Exception as e:
            logger.error(f"解析分析结果失败: {e}（{describe_completion(response)}）")
            return self._get_default_analysis()

    def _get_default_analysis(self) -> Dict[str, Any]:
        """分析不可用时返回的结构 —— **内容为空**。

        这里以前返回写死的机构目标价（高盛 5400 / 瑞银 5000 / 摩根士丹利 4500）、
        一个凭空的 current_price=5067，以及一整段综合判断文案。
        """
        return {
            "core_bullish_logic": [],
            "main_risks": [],
            "market_consensus": [],
            "institution_targets": [],
            "current_price": None,
            "comprehensive_judgment": {},
            "core_view": "",
            "investment_recommendation": "",
            "confidence_level": "",
            "time_horizon": "",
        }

class MarketSummaryService:
    """市场综合分析服务 - 支持缓存优化"""

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = MarketSummaryAnalyzer()
        self.cache = CacheManager("market_summary", ttl=AI_ANALYSIS_CACHE_TTL)

    def _get_realtime_price(self) -> float:
        """获取实时金价"""
        try:
            from app.services.gold_service import GoldService
            gold_service = GoldService(self.db)
            stats = gold_service.get_statistics()
            if stats:
                # 不要在这里兜一个写死的数字：取不到就该是 None，
                # 否则 5067 会被当成真实金价写进 prompt 与响应。
                return stats.get("current_price")
        except Exception as e:
            logger.error(f"[MarketSummary] 获取实时价格失败: {e}")
        return None

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

        # 如果强制刷新，直接执行实时 LLM 分析
        if not use_cache:
            logger.info("[MarketSummary] 强制刷新，执行实时 LLM 分析...")
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
                    "cache_source": "llm_realtime",
                    "generated_at": timeutil.now_iso(),
                    "data_sources": ["实时金价数据", "看涨因子", "看跌因子", "机构预测", "24小时新闻"],
                    "analysis_method": "LLM 综合分析"
                }
                return result
            except Exception as e:
                logger.error(f"[MarketSummary] 实时分析失败: {e}")
                pass

        # 1. 首先尝试文件缓存
        cached_data = self.cache.get()
        if cached_data:
            # 缓存可能是在机构数据不可用时生成的；按当前输入重新清洗，不能把
            # 「四大投行集体中性」这类无法核实的判断继续对外展示。
            cached_data = sanitize_institution_claims(cached_data, institution_predictions)
            # 用实时价格覆盖缓存中的价格
            cached_data["current_price"] = realtime_price
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": timeutil.now_iso(),
                "data_sources": ["实时金价数据", "看涨因子", "看跌因子", "机构预测", "24小时新闻"],
                "analysis_method": "LLM 综合分析"
            }
            return cached_data

        # 2. 无缓存时，返回空内容 + 状态并触发后台分析。
        #
        # 这里以前返回一份写死的综合判断（还带着机构目标价与 current_price=5067），
        # 而那份内容与 MarketSummaryAnalyzer._get_default_analysis() 是**同一批
        # 数据的两份拷贝** —— 改一处忘一处就会不一致。现在只有一处定义，且为空。
        default_data = self.analyzer._get_default_analysis()
        default_data["metadata"] = {
            "cached": False,
            "status": "analyzing",
            "message": "AI分析进行中，首次加载可能需要1-2分钟",
        }
        # 实时价是真实取到的，可以填进去（取不到时 realtime_price 为 None）
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

    _ANALYSIS_KEY = "market_summary"

    def _trigger_background_analysis(
        self,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict],
        recent_news: List[Dict]
    ) -> None:
        """触发后台分析（不阻塞，同一服务同时只跑一个）。"""
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            return
        try:
            _executor.submit(
                self._guarded_background_task,
                market_status,
                bullish_factors,
                bearish_factors,
                institution_predictions,
                recent_news
            )
        except Exception as e:
            single_flight.end(self._ANALYSIS_KEY)
            logger.error(f"[MarketSummary] 触发后台分析失败: {e}")

    def _guarded_background_task(
        self,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict],
        recent_news: List[Dict]
    ) -> None:
        """执行后台分析，结束后释放单飞占位。

        这里必须新建数据库会话：原实现直接用 self.db（请求级会话），
        而本方法运行在另一个线程里，请求结束时那个会话可能已经关闭。
        """
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            logger.info("[MarketSummary] 后台分析启动...")
            result = self.analyzer.analyze(
                db,
                market_status,
                bullish_factors,
                bearish_factors,
                institution_predictions,
                recent_news
            )
            self.cache.set(result)
            logger.info("[MarketSummary] 后台分析完成，结果已缓存")
        except Exception as e:
            logger.error(f"[MarketSummary] 后台分析失败: {e}")
        finally:
            db.close()
            single_flight.end(self._ANALYSIS_KEY)
