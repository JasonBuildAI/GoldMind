"""机构预测分析服务

## 「最近一次可核实预测」口径（2026-10-01 起）

机构观点不再要求「24 小时内发布」：没有新研报不等于机构撤回了预测，旧口径
等于每天把真实目标价丢掉一次。现在扫描 `INSTITUTION_NEWS_LOOKBACK_DAYS`
（默认 30 天）窗口，逐家提取**最近一次可核实**的预测，并记录两个溯源字段：

- `as_of_date`：该预测最近一次被核实/抓取入库的日期。优先用 LLM 从新闻
  时间戳提取的日期；提取不到就用窗口内最新新闻日期；再没有才用当天。
- `source`：线索来源 —— `web_search` / `news_scan`；迁移回填的历史行是
  `legacy`。

## 一条真实故障换来的红线

2026-10-01 06:01 的一次抓取没有找到新的机构研报，旧代码把四条真实目标价
（5400 / 5000 / 6300 / 6000）全部覆盖成了「暂无」。现在的 `save_to_database`：

1. 名称一律规范化到注册表的规范名，认不出的机构直接忽略；
2. **target_price 为空的条目绝不覆盖已有真实记录**（跳过该行更新）；
3. 只在连占位行都没有时才写一条「暂无最新预测」的空行 —— 占位行没有任何
   数字，纯粹表示「这家机构仍在跟踪，但没有可核实的预测」。

机构注册表（`INSTITUTIONS`）是机构名单的唯一真源：写入、读取、提示词与
测试全部从它派生。
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import json

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis import InstitutionView
from app.services.ai_payload import with_last_updated
from app.services.analysis_input import build_analysis_input, load_analysis_news
from app.services import llm_gate
from app.services.cache_manager import CacheManager, AI_ANALYSIS_CACHE_TTL
from app.services.llm_provider import (
    describe_completion,
    get_chat_llm,
    invoke_with_retries,
)
from app.services.news_service import format_news_for_prompt
from app.services.single_flight import single_flight
from app.services.web_search_service import get_web_search_service
from app.utils import timeutil

# 全局线程池
_executor = ThreadPoolExecutor(max_workers=2)


# --------------------------------------------------------------------------- #
# 机构注册表：唯一真源
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Institution:
    """一家被追踪的机构：规范名、logo 与全部可识别写法。"""

    key: str
    name: str
    logo: str
    aliases: Tuple[str, ...]


INSTITUTIONS: Tuple[Institution, ...] = (
    Institution(
        "goldman",
        "高盛 (Goldman Sachs)",
        "GS",
        ("高盛", "高盛集团", "goldman sachs", "goldman", "gs"),
    ),
    Institution(
        "ubs",
        "瑞银 (UBS)",
        "UBS",
        ("瑞银", "瑞银集团", "ubs", "union bank of switzerland"),
    ),
    Institution(
        "morgan_stanley",
        "摩根士丹利 (Morgan Stanley)",
        "MS",
        ("摩根士丹利", "morgan stanley", "morganstanley", "ms"),
    ),
    Institution(
        "citi",
        "花旗 (Citi)",
        "C",
        ("花旗", "花旗集团", "花旗银行", "citi", "citigroup", "citi group"),
    ),
)

CANONICAL_NAMES: Tuple[str, ...] = tuple(inst.name for inst in INSTITUTIONS)


def _normalize_text(value: Any) -> str:
    """大小写、首尾与连续空白归一 —— 只用于名称匹配。"""
    return " ".join(str(value if value is not None else "").strip().lower().split())


def match_institution(name: Any) -> Optional[Institution]:
    """把任意写法匹配到注册表条目；认不出返回 None。

    先做精确匹配（别名或规范名），再做包含匹配（「高盛集团」
    「Goldman Sachs Group」这类带后缀的写法）。包含匹配只对长度 >= 3 的
    别名生效，避免 ``gs`` / ``ms`` 这类两字母缩写出现在别的词里被误伤。
    """
    text = _normalize_text(name)
    if not text:
        return None

    for inst in INSTITUTIONS:
        for candidate in (inst.name,) + inst.aliases:
            if text == _normalize_text(candidate):
                return inst

    for inst in INSTITUTIONS:
        for alias in inst.aliases:
            alias_text = _normalize_text(alias)
            if len(alias_text) >= 3 and (alias_text in text or text in alias_text):
                return inst
    return None


def canonical_name(name: Any) -> Optional[str]:
    """任意写法 -> 规范名；认不出返回 None。"""
    inst = match_institution(name)
    return inst.name if inst else None


# 「暂无最新预测」是 `save_to_database` 在窗口期内找不到可核实预测时写的
# 占位文案。占位行只用于页面显示跟踪状态，**不是**「机构给出中性评级」。
PLACEHOLDER_INSTITUTION_REASONINGS = {"暂无最新预测"}


def usable_institution_predictions(predictions: Optional[List[Dict]]) -> List[Dict]:
    """只保留可核实的机构行；占位行（无目标价、无日期、占位理由）不算数据。

    消费方（市场总结 / 投资建议）据此决定：哪些行可以喂给 LLM、哪些机构
    可以被引用。占位行被当成评级会产出「四大投行集体中性」这类幻觉。
    """
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


# 数据库那一列是 ENUM('bullish','bearish','neutral')，前端也只认这三种。
# 但模型里它只是 String —— 也就是说**约束只在数据库层**，见 normalize_rating。
VALID_RATINGS = ("bullish", "bearish", "neutral")

# 认得出的近义写法（LLM 不总是照提示词给英文小写）
_RATING_ALIASES = {
    "bullish": "bullish", "bull": "bullish", "buy": "bullish",
    "positive": "bullish", "看涨": "bullish", "看多": "bullish", "乐观": "bullish",
    "bearish": "bearish", "bear": "bearish", "sell": "bearish",
    "negative": "bearish", "看跌": "bearish", "看空": "bearish", "悲观": "bearish",
    "neutral": "neutral", "hold": "neutral", "中性": "neutral", "观望": "neutral",
}


def normalize_rating(value: Any) -> str:
    """把 LLM 给出的评级归一化到三种取值之一。

    为什么需要：`institution_views.rating` 在模型里是 `String`，约束却只在数据库
    （`ENUM('bullish','bearish','neutral')`）。提示词里写了「rating只能是：
    bullish, bearish, neutral」，但模型并不总听话 —— 一旦返回「看涨」之类的值，
    插入会直接报错，**整批机构观点都存不进去**（一次 commit 全废）。

    这里兜住：认不出的按 neutral 处理并记一条警告，保证写入不会因为一个字段失败。
    """
    text = str(value if value is not None else "").strip().lower()
    if text in _RATING_ALIASES:
        return _RATING_ALIASES[text]
    logger.warning(f"[InstitutionPrediction] 认不出的评级 {value!r}，按 neutral 处理")
    return "neutral"


_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日")


def parse_as_of_date(value: Any, today: Optional[date] = None) -> Optional[date]:
    """解析 as_of 日期，只认能精确到「日」的写法。

    无效格式、未来日期、早于 1990 年的日期一律返回 None（由调用方走回退链）——
    宁可标不出日期，也不能把模型编的日期当成事实（红线 1）。
    """
    if isinstance(value, datetime):
        candidate: Optional[date] = value.date()
    elif isinstance(value, date):
        candidate = value
    else:
        text = str(value if value is not None else "").strip()
        if not text:
            return None
        # 兼容 "2026-02-08T10:00:00" / "2026-02-08 10:00" 这类带时间的写法
        text = text.replace("T", " ").split(" ")[0]
        candidate = None
        for fmt in _DATE_FORMATS:
            try:
                candidate = datetime.strptime(text, fmt).date()
                break
            except ValueError:
                continue
        if candidate is None:
            return None

    reference = today or timeutil.today()
    if candidate > reference or candidate.year < 1990:
        return None
    return candidate


def _coerce_target_price(value: Any) -> Optional[float]:
    """把 LLM 的 target_price 归一为有限正数；否则 None。

    字符串 "5,400" / "$5400"、数字 5400 都能过；0、负数、"暂无"、None 一律
    视为无目标价 —— 它们只可能是占位或解析残留，绝不能当成真实点位写进库。
    """
    if isinstance(value, bool):  # bool 是 int 的子类，先挡掉
        return None

    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value if value is not None else "").strip()
        text = text.replace(",", "").replace("$", "").replace("美元", "").strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None

    if not (number > 0) or number == float("inf"):
        return None
    return number


def _source_from_result(analysis_result: Dict[str, Any]) -> Optional[str]:
    """把分析结果的 data_source 映射到溯源的 source 取值。"""
    raw = _normalize_text(analysis_result.get("data_source"))
    if not raw:
        return None
    if "web" in raw or "联网" in raw or "搜索" in raw:
        return "web_search"
    return "news_scan"


def _has_real_prices(payload: Optional[Dict[str, Any]]) -> bool:
    """结果里是否至少有一条真实目标价。

    只有占位行（target_price 全为 null）的结果不值得当缓存用：2026-10-01 06:01
    的故障里，旧代码把四条 null 占位写进了缓存，页面于是再也不会回落到库里
    已经被迁移恢复的真实数据。缓存与读取都以这条判据为准。
    """
    if not payload:
        return False
    for item in payload.get("institutions") or []:
        if isinstance(item, dict) and item.get("target_price") is not None:
            return True
    return False


def build_summary_from_institutions(
    institutions: List[Dict[str, Any]], window_days: int
) -> str:
    """由结构化行**确定性**拼装「一句话汇总」，只陈述可核实的计数。

    为什么不让模型来写：2026-10-02 的缓存实测里，LLM 汇总说「瑞银看涨」，
    而同一家 UBS 的结构化记录是 neutral —— 文字与表格互相矛盾，用户无从
    分辨。模型概括不再进入响应；这里只输出「多少家有目标价、多少条在窗口内」。
    """
    priced = [item for item in institutions if item.get("target_price") is not None]
    if not priced:
        return (
            f"最近 {window_days} 天内没有找到任何可核实的机构目标价；"
            "本表只显示四家机构的跟踪状态，没有数字可展示。"
        )

    fresh = [
        item
        for item in priced
        if item.get("stale_days") is not None and item["stale_days"] <= window_days
    ]
    if fresh:
        return (
            f"最近 {window_days} 天内有 {len(fresh)} 家机构的目标价可核实；"
            f"下表共 {len(priced)} 家有可核实记录（含日期）。"
        )
    return (
        f"最近 {window_days} 天新闻中未出现新的机构目标价；"
        f"下表共 {len(priced)} 家有可核实记录（含日期）。"
    )


# 命中这些关键词的「较早新闻」会被追加进预选（机构名 / 目标价语义）。
_INSTITUTION_KEYWORDS: Tuple[str, ...] = (
    "高盛", "瑞银", "摩根士丹利", "花旗",
    "goldman", "ubs", "morgan", "citi",
    "目标价", "目标价格", "上调", "下调",
    "price target", "target price", "forecast",
)


# 输入指纹门控的键：必须与 Service._ANALYSIS_KEY 一致（守卫逐对断言）。
GATE_KEY = "institution_predictions"


class InstitutionPredictionAnalyzer:
    """用联网搜索（优先）或新闻窗口（回退）抓取四大机构最近一次可核实预测。"""

    def __init__(self):
        self._llm = None
        self.web_search_service = get_web_search_service()
        # 输入未变时跳过重算、直接复用 Service 写的同一份缓存（同 key、同 TTL）。
        self.cache = CacheManager(GATE_KEY, ttl=AI_ANALYSIS_CACHE_TTL)
        self.prompt_template = """你是一位专业的金融市场数据分析师，专注于追踪华尔街顶级投行对黄金价格的预测。

{capability_note}

你的任务是从下面的新闻材料中**提取**以下四家机构对黄金的**最近一次可核实**预测：
1. 高盛 (Goldman Sachs)
2. 瑞银 (UBS)
3. 摩根士丹利 (Morgan Stanley)
4. 花旗 (Citi)

以下是最近 {lookback_days} 天内收集的黄金相关新闻资讯（含较早的机构相关条目）：
{news_content}

要求：
- 允许使用窗口内**较早发布**的新闻 —— 要的是每家机构最近一次可核实的记录，不是「今天有没有新研报」；
- 每家的 target_price 必须来自检索到的内容，找不到就把 target_price 置为 null、
  reasoning 写「暂无最新预测」，**不要**凭印象替它编一个目标价；
- as_of 取该条预测的新闻时间戳（YYYY-MM-DD）；无法确定就留空字符串，不要猜一个日期。

对每家机构请提供：
1. **目标价格** - 具体的美元价格（数字）
2. **时间框架** - 如"2026年底"、"2026年9月"、"2026年中"、"长期展望"等
3. **评级** - bullish(看涨) / bearish(看跌) / neutral(中性)
4. **核心理由** - 一句话总结该机构的主要观点
5. **关键要点** - 4个支撑该预测的核心论据
6. **as_of** - 该预测最近一次被核实/发布的日期（YYYY-MM-DD，取自新闻时间戳；无法确定留空）

请严格按照以下 JSON 结构返回（下面是**结构骨架**，方括号里是字段含义；
不要照抄任何数字，target_price 必须是你从检索到的内容里得到的真实数字）：

{{
    "institutions": [
        {{
            "name": "机构全名，如 高盛 (Goldman Sachs)",
            "logo": "机构缩写，如 GS",
            "rating": "bullish 或 bearish 或 neutral",
            "target_price": 该机构的目标价（美元，数字；没有就 null）,
            "timeframe": "该目标价对应的时间框架",
            "reasoning": "该机构核心理由（一句话）",
            "key_points": ["要点1", "要点2", "要点3", "要点4"],
            "as_of": "YYYY-MM-DD 或空字符串"
        }}
    ],
    "analysis_summary": "四家机构预测的汇总（一句话）。必须写明：这是最近 {lookback_days} 天内各家机构最近一次可核实记录的汇总，可能是较早发布的预测。",
    "last_updated": "{current_time}"
}}

注意事项：
1. 必须返回有效 JSON
2. rating 只能是：bullish, bearish, neutral
3. target_price 必须是数字（美元）或 null
4. **如果检索内容里没有某家机构的预测，就把该机构的 target_price 置为 null、
   reasoning 写「暂无最新预测」，不要凭印象替它编一个目标价。**
   编造的机构目标价比缺一条更糟 —— 见 docs/00-产品方向.md 第四节。
5. key_points 数组应包含 4 个具体要点；确实没有预测时可给空数组。
"""

    @property
    def llm(self):
        """延迟创建 LLM 实例（供应商由 llm_provider 工厂统一决定）"""
        if self._llm is None:
            self._llm = get_chat_llm(temperature=0.7)
        return self._llm

    @property
    def lookback_days(self) -> int:
        """新闻扫描窗口（天）。配置了非法值时退回 30，不让一次错配置拖垮服务。"""
        try:
            return max(1, int(settings.INSTITUTION_NEWS_LOOKBACK_DAYS))
        except (TypeError, ValueError):
            return 30

    def fetch_recent_news(self, db: Session, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """扫描窗口内的分析新闻输入（消息板块高权威条目 + gold_news，去重合并）。"""
        window_days = self.lookback_days if days is None else max(1, int(days))
        return load_analysis_news(db, hours=window_days * 24)

    def _select_news_for_institutions(
        self,
        news: List[Dict[str, Any]],
        recent_limit: int = 15,
        keyword_limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """最近 15 条 + 最多 15 条命中机构名/目标价关键词的较早条目。

        窗口从 24 小时放宽到 30 天后，条目可能上百条。全喂给模型既贵又容易
        让关键研报淹没在行情快讯里；只取「最近一批 + 机构相关的一批」，
        窗口长度由提示词显式说明。
        """
        if not news:
            return []

        ordered = sorted(
            news, key=lambda item: item.get("published_at") or datetime.min, reverse=True
        )
        selected: List[Dict[str, Any]] = list(ordered[:recent_limit])

        extra = 0
        for item in ordered[recent_limit:]:
            if extra >= keyword_limit:
                break
            text = f"{item.get('title') or ''} {item.get('summary') or ''}".lower()
            if not any(keyword in text for keyword in _INSTITUTION_KEYWORDS):
                continue
            selected.append(item)
            extra += 1

        return selected

    def fetch_news_from_web(self) -> List[Dict[str, Any]]:
        """从网络获取最新新闻（当数据库为空时使用）"""
        import feedparser

        all_news = []

        # RSS源列表
        rss_sources = [
            ('https://finance.sina.com.cn/money/gold/gold_xh.shtml', '新浪财经'),
            ('https://www.fx168.com/gold/', 'FX168'),
            ('https://www.jin10.com/', '金十数据'),
        ]

        for url, source in rss_sources:
            try:
                # 尝试RSS
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    all_news.append({
                        'title': entry.get('title', ''),
                        'summary': entry.get('summary', '')[:200],
                        'source': source,
                        'published_at': timeutil.now_naive()
                    })
            except Exception as e:
                logger.error(f"获取 {source} 新闻失败: {e}")

        return all_news

    def analyze(self, db: Session, *, force: bool = False) -> Dict[str, Any]:
        """执行分析 - 尝试联网搜索，不可用时回退新闻窗口。

        `force=True`（用户显式刷新）跳过输入指纹门控。
        """
        # 联网搜索获取最新机构预测（默认关闭，见 LLM_SEARCH_ENABLED）
        try:
            logger.info("[InstitutionPrediction] 尝试联网搜索机构预测...")
            search_result = self.web_search_service.search_institution_predictions()

            # 必须同时确认搜索真的可用，否则「搜到空结果」与「搜索不可用」
            # 会被混为一谈，上层就无法决定是否该回退。
            if search_result.get("available") and search_result.get("institutions"):
                logger.info(f"[InstitutionPrediction] 成功获取 {len(search_result['institutions'])} 家机构预测")
                search_result["last_updated"] = timeutil.now_str()
                search_result["data_source"] = "web_search"
                return search_result
            else:
                logger.warning("[InstitutionPrediction] 搜索结果为空，使用备用方案")

        except Exception as e:
            logger.error(f"[InstitutionPrediction] 联网搜索失败: {e}")

        # 备用方案：使用传统方式分析
        return self._analyze_with_traditional_llm(db, force=force)

    def _analyze_with_traditional_llm(
        self, db: Session, *, force: bool = False
    ) -> Dict[str, Any]:
        """使用传统 LLM 分析（备用方案）。

        窗口内的新闻先经 `_select_news_for_institutions` 预选；一条都没有时
        **不调用 LLM**，直接返回空结构（红线 1：没有依据就不让模型凭记忆编）。
        """
        window_days = self.lookback_days
        packet = build_analysis_input(
            db, news_hours=window_days * 24, include_prices=False
        )
        selected = self._select_news_for_institutions(packet.news_items)

        if selected:
            news_content = format_news_for_prompt(selected, limit=30)
        else:
            # 数据库没有新闻，尝试从网络获取
            web_news = self.fetch_news_from_web()
            if web_news:
                news_content = format_news_for_prompt(web_news)
            else:
                # 没有任何新闻可依据 —— 不调 LLM，直接返回空（红线第 1 条）
                logger.warning(
                    f"[InstitutionPrediction] 最近 {window_days} 天内没有任何新闻，"
                    "不调用 LLM（没有依据可分析）"
                )
                return self.get_default_predictions()

        # 构建prompt并调用LLM
        current_time = timeutil.now_str()
        prompt = self.prompt_template.format(
            news_content=news_content,
            capability_note=packet.capability_note,
            current_time=current_time,
            lookback_days=window_days,
        )

        # 输入指纹门控（2.0.2 第 19 条）：prompt 里只有 current_time 是易变的。
        fingerprint = llm_gate.prompt_fingerprint(prompt, volatile=(current_time,))
        if not force:
            skipped = llm_gate.gate.skip_if_unchanged(GATE_KEY, fingerprint, self.cache)
            if skipped is not None:
                return skipped

        try:
            response = invoke_with_retries(self.llm, prompt)

            # 解析JSON响应
            try:
                result = json.loads(response.content)
            except json.JSONDecodeError:
                # 尝试从文本中提取JSON
                content = response.content
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end > start:
                    try:
                        result = json.loads(content[start:end])
                    except Exception:
                        logger.error(
                            "[InstitutionPrediction] JSON 解析失败"
                            f"（{describe_completion(response)}）"
                        )
                        result = self.get_default_predictions()
                else:
                    logger.error(
                        "[InstitutionPrediction] 输出里没有 JSON"
                        f"（{describe_completion(response)}）"
                    )
                    result = self.get_default_predictions()

            if isinstance(result, dict):
                result["data_source"] = "news_scan"
            # 只有真正调用并解析成功才记录指纹：失败路径下次仍要重试。
            llm_gate.gate.record(GATE_KEY, fingerprint)
            return result
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self.get_default_predictions()

    def get_default_predictions(self) -> Dict[str, Any]:
        """分析不可用时返回的结构 —— **机构列表为空**。

        这里以前返回高盛 5400 / 瑞银 5000 / 摩根士丹利 4500 / 花旗 2700 这组
        写死的目标价，还配上了「将目标价从4900美元上调至5400美元」
        「预计2026年央行月均购金70吨」之类的具体说法。

        产品方向第四节第 1 条明确写着：联网搜索不可用时「只能回退到数据库与
        RSS 新闻，**不得**凭模型印象编造机构目标价」。写死的常量同样是编造，
        而且看起来比模型编的更像真的。

        现在返回空列表 + 状态，前端据此显示「正在分析中」或「暂不可用」。
        """
        return {
            "institutions": [],
            "analysis_summary": "",
            "last_updated": timeutil.now_str(),
        }

    def _latest_news_date(self, db: Session) -> Optional[date]:
        """窗口内最新一条新闻的日期；没有新闻返回 None。"""
        news = self.fetch_recent_news(db)
        dates = [
            item["published_at"].date()
            for item in news
            if item.get("published_at")
        ]
        return max(dates) if dates else None

    def _resolve_as_of(self, inst_data: Dict[str, Any], fallback: Optional[date]) -> date:
        """as_of 回退链：LLM 提取的日期 → 窗口内最新新闻日期 → 当天。"""
        parsed = parse_as_of_date(inst_data.get("as_of") or inst_data.get("as_of_date"))
        if parsed is not None:
            return parsed
        if fallback is not None:
            return fallback
        return timeutil.today()

    def save_to_database(
        self, db: Session, analysis_result: Dict[str, Any]
    ) -> int:
        """把分析结果写入数据库，返回**真实目标价**的写入条数。

        三条语义（缺一不可）：

        1. 名称一律规范化到注册表的规范名；认不出的机构直接忽略
           （注册表是唯一真源，不支持自定义名单）。
        2. target_price 为空的条目**绝不覆盖**已有真实记录 ——
           没有新研报不等于机构撤回了预测。只有在连占位行都没有时，
           才写一条「暂无最新预测」的占位行，让页面能显示跟踪状态。
        3. 真实条目记录 as_of_date 与 source：as_of 取 LLM 从新闻时间戳
           提取的日期，无效则退回窗口内最新新闻日期，再没有就用当天。
        """
        incoming = analysis_result.get("institutions") or []
        source = _source_from_result(analysis_result)
        fallback_date = self._latest_news_date(db)
        now = timeutil.now_naive()

        by_key: Dict[str, Dict[str, Any]] = {}
        for inst_data in incoming:
            if not isinstance(inst_data, dict):
                continue
            inst = match_institution(inst_data.get("name"))
            if inst is None:
                logger.warning(
                    f"[InstitutionPrediction] 认不出的机构 {inst_data.get('name')!r}，已忽略"
                )
                continue
            by_key.setdefault(inst.key, inst_data)

        written = 0
        for inst in INSTITUTIONS:
            inst_data = by_key.get(inst.key)
            target_price = _coerce_target_price(
                inst_data.get("target_price") if inst_data else None
            )

            existing = db.query(InstitutionView).filter(
                InstitutionView.institution_name == inst.name
            ).first()

            if target_price is None:
                # 空目标价：永远不覆盖已有记录。
                if existing is not None:
                    continue
                # 连占位行都没有 → 写一条没有任何数字的占位行。
                db.add(
                    InstitutionView(
                        institution_name=inst.name,
                        logo=inst.logo,
                        rating="neutral",
                        target_price=None,
                        timeframe="",
                        reasoning="暂无最新预测",
                        key_points=[],
                        as_of_date=None,
                        source=source,
                        updated_at=now,
                    )
                )
                continue

            as_of = self._resolve_as_of(inst_data, fallback_date)
            payload = {
                "logo": inst.logo,
                "rating": normalize_rating(inst_data.get("rating")),
                "target_price": target_price,
                "timeframe": inst_data.get("timeframe") or "",
                "reasoning": inst_data.get("reasoning") or "",
                "key_points": inst_data.get("key_points") or [],
                "as_of_date": as_of,
                "source": source,
                "updated_at": now,
            }

            if existing is not None:
                for field, value in payload.items():
                    setattr(existing, field, value)
            else:
                db.add(InstitutionView(institution_name=inst.name, **payload))
            written += 1

        db.commit()
        return written


class InstitutionPredictionService:
    """机构预测服务类 - 优化版（支持实时搜索和缓存）"""

    _ANALYSIS_KEY = "institution_predictions"

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = InstitutionPredictionAnalyzer()
        self.cache = CacheManager("institution_predictions", ttl=AI_ANALYSIS_CACHE_TTL)  # 与调度器的刷新间隔对齐，见该常量的说明
        self.web_search_service = get_web_search_service()

    @with_last_updated
    def get_institution_predictions(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        获取机构预测 - 快速响应版本（<50ms）

        读取顺序：
        1. use_cache=False → 扫描分析 + 写库（空目标价不覆盖）→ 从库重新组装；
        2. 文件缓存里有**非空**机构列表 → 直接返回。空结果不再被当成有效缓存 ——
           旧代码把一次「什么都没找到」的抓取也缓存下来，页面于是再也不会回落到
           库里的真实数据；
        3. 从数据库按四家规范行组装（不再要求「2 小时内更新」）——
           旧数据标注 as_of_date 与滞后天数，比「暂无」诚实也有用；
        4. 库里连行都没有 → 返回默认结构并触发后台分析。

        Args:
            use_cache: 是否使用缓存（默认True，立即返回缓存数据）

        Returns:
            机构预测分析结果
        """
        # 如果强制刷新，直接执行实时搜索
        if not use_cache:
            logger.info("[InstitutionPrediction] 强制刷新，执行实时搜索...")
            try:
                analysis = self.analyzer.analyze(self.db, force=True)
                self.analyzer.save_to_database(self.db, analysis)
                result = self._assemble_from_database(
                    metadata={
                        "cached": False,
                        "cache_source": "realtime_search",
                        "generated_at": timeutil.now_iso(),
                        "message": "已重新扫描新闻窗口；空目标价不会覆盖已有真实预测",
                    },
                )
                if _has_real_prices(result):
                    self.cache.set(result)
                return result
            except Exception as e:
                logger.error(f"[InstitutionPrediction] 实时搜索失败: {e}")
                # 失败时回落到缓存 / 数据库组装，而不是让页面空着

        # 1. 首先尝试文件缓存（最快，支持多进程共享）
        cached_data = self.cache.get()
        if _has_real_prices(cached_data):
            # 缓存里可能还留着「模型概括」时代的旧摘要；结构化行就在缓存里，
            # 直接按同一套确定性规则重算，保证文字与表格永不矛盾。
            cached_data["analysis_summary"] = build_summary_from_institutions(
                cached_data.get("institutions") or [], self.analyzer.lookback_days
            )
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": timeutil.now_iso()
            }
            return cached_data

        # 2. 从数据库组装四家规范行（不再要求「2 小时内更新」）
        result = self._assemble_from_database(
            metadata={
                "cached": True,
                "cache_source": "database",
                "generated_at": timeutil.now_iso()
            }
        )
        if result["institutions"]:
            if _has_real_prices(result):
                self.cache.set(result)
            return result

        # 3. 无缓存时，返回默认数据并触发后台更新
        #
        # 用 analyzer.get_default_predictions()，而不是本类里那份 _get_default_response()：
        # 后者把 target_price 写成了字符串（"2,900美元"），而契约是数字。
        # 前端拿它做 Math.min(...)，结果是 NaN —— 页面显示
        # 「目标价集中在 NaN-NaN 美元区间」。
        default_data = self.analyzer.get_default_predictions()
        default_data["metadata"] = {
            "cached": False,
            "status": "analyzing",
            "message": "AI分析进行中，首次加载可能需要1-2分钟",
        }
        self._trigger_background_analysis()
        return default_data

    def _assemble_from_database(
        self,
        metadata: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """按机构注册表顺序，从四家规范行组装响应。

        - 只读规范行：历史遗留的别名行（`Goldman Sachs` 这类）忽略；
        - `stale_days` 在这里用 timeutil 计算（红线 5：时间只走一个时区）；
        - **汇总始终由结构化行确定性拼装**，不采用 LLM 概括 ——
          模型文字可能与本表矛盾（实测缓存「瑞银看涨」而 UBS 行是 neutral），
          用户无从分辨，宁可只陈述可核实的事实。
        """
        session = db or self.db
        window_days = self.analyzer.lookback_days
        today = timeutil.today()

        rows = session.query(InstitutionView).filter(
            InstitutionView.institution_name.in_(CANONICAL_NAMES)
        ).all()
        by_name = {row.institution_name: row for row in rows}

        institutions: List[Dict[str, Any]] = []

        for inst in INSTITUTIONS:
            row = by_name.get(inst.name)
            if row is None:
                continue

            stale_days: Optional[int] = None
            if row.as_of_date is not None:
                stale_days = max(0, (today - row.as_of_date).days)

            institutions.append(
                {
                    "name": inst.name,
                    "logo": row.logo or inst.logo,
                    "rating": row.rating or "neutral",
                    "target_price": row.target_price,
                    "timeframe": row.timeframe or "",
                    "reasoning": row.reasoning or "",
                    "key_points": row.key_points or [],
                    "as_of_date": row.as_of_date.isoformat() if row.as_of_date else None,
                    "stale_days": stale_days,
                    "source": row.source,
                }
            )

        if not institutions:
            return {
                "institutions": [],
                "analysis_summary": "",
                "last_updated": timeutil.now_str(),
                "metadata": metadata,
            }

        return {
            "institutions": institutions,
            "analysis_summary": build_summary_from_institutions(institutions, window_days),
            # 用项目时区的当前时间，而不是 `updated_at` ——
            # 那一列是数据库的 `func.now()`（库服务器时间）生成的，
            # 容器里通常是 UTC，展示给用户会差 8 小时（红线 5）。
            "last_updated": timeutil.now_str(),
            "metadata": metadata,
        }

    def _trigger_background_analysis(self, *, force: bool = False) -> None:
        """触发后台分析（不阻塞，同一服务同时只跑一个）。"""
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            return
        try:
            _executor.submit(self._guarded_background_task, force)
        except Exception as e:
            single_flight.end(self._ANALYSIS_KEY)
            logger.error(f"[InstitutionPrediction] 触发后台分析失败: {e}")

    def _guarded_background_task(self, force: bool = False) -> None:
        """执行后台任务，结束后释放单飞占位。"""
        try:
            self._background_analysis_task(force=force)
        finally:
            single_flight.end(self._ANALYSIS_KEY)

    def _background_analysis_task(self, *, force: bool = False) -> None:
        """后台分析任务：分析 → 写库 → 从库组装 → 缓存组装后的结果。"""
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                analysis = self.analyzer.analyze(db, force=force)
                written = self.analyzer.save_to_database(db, analysis)
                result = self._assemble_from_database(
                    metadata={
                        "cached": True,
                        "cache_source": "database",
                        "generated_at": timeutil.now_iso(),
                    },
                    db=db,
                )
                if _has_real_prices(result):
                    self.cache.set(result)
                logger.info(
                    f"[InstitutionPrediction] 后台分析完成（真实目标价 {written} 条），"
                    f"时间: {timeutil.now()}"
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[InstitutionPrediction] 后台分析失败: {e}")

    def refresh_analysis_sync(self, *, force: bool = False) -> Dict[str, Any]:
        """同步刷新分析（阻塞，仅用于定时任务）。

        若同服务已有分析在跑（例如启动预热触发的后台任务），直接跳过 ——
        它产出的就是同一份结果，重复执行只是多花一次 LLM 费用。
        默认受输入指纹门控：输入没变就不重算（force=True 可绕过）。
        """
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            logger.warning("[InstitutionPrediction] 已有分析在执行，跳过本次刷新")
            cached = self.cache.get() or {}
            if cached.get("institutions"):
                cached["analysis_summary"] = build_summary_from_institutions(
                    cached["institutions"], self.analyzer.lookback_days
                )
            return cached
        try:
            analysis = self.analyzer.analyze(self.db, force=force)
            self.analyzer.save_to_database(self.db, analysis)
            result = self._assemble_from_database(
                metadata={
                    "cached": True,
                    "cache_source": "database",
                    "generated_at": timeutil.now_iso(),
                },
            )
            if _has_real_prices(result):
                self.cache.set(result)
            return result
        finally:
            single_flight.end(self._ANALYSIS_KEY)

    async def refresh_analysis_async(self, *, force: bool = True) -> Dict[str, Any]:
        """异步刷新分析 —— 用户显式刷新（POST /refresh），默认不受指纹门控限制。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(self.refresh_analysis_sync, force=force)
        )

    def _get_logo(self, name: str) -> str:
        """根据机构名称获取 logo（注册表派生；认不出给 BANK）。"""
        inst = match_institution(name)
        return inst.logo if inst else "BANK"
