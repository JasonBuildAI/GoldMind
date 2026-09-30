"""机构预测分析服务"""
from typing import List, Dict, Any
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from concurrent.futures import ThreadPoolExecutor
import asyncio

from app.services.news_service import format_news_for_prompt
from app.utils import timeutil
from app.models.news import GoldNews
from app.models.analysis import InstitutionView
from app.config import settings
from app.services.cache_manager import CacheManager, AI_ANALYSIS_CACHE_TTL
from app.services.single_flight import single_flight
from app.services.llm_provider import get_chat_llm
from app.services.web_search_service import get_web_search_service
import json
from loguru import logger

# 全局线程池
_executor = ThreadPoolExecutor(max_workers=2)

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

class InstitutionPredictionAnalyzer:
    """使用MiMo 联网搜索抓取四大机构最新预测"""

    def __init__(self):
        self._llm = None
        self.web_search_service = get_web_search_service()
        self.prompt_template = """你是一位专业的金融市场数据分析师，专注于追踪华尔街顶级投行对黄金价格的最新预测。

你的任务是搜索并整理以下四家主流机构对黄金的最新预测：
1. 高盛 (Goldman Sachs)
2. 瑞银 (UBS)
3. 摩根士丹利 (Morgan Stanley)
4. 花旗 (Citi)

以下是从24小时内收集的黄金相关新闻资讯：
{news_content}

请根据以上新闻，**提取**这四家机构的最新黄金预测（新闻里没有就如实说明，不要推断）。对于每家机构，请提供：

1. **目标价格** - 具体的美元价格（数字）
2. **时间框架** - 如"2026年底"、"2026年9月"、"2026年中"、"长期展望"等
3. **评级** - bullish(看涨) / bearish(看跌) / neutral(中性)
4. **核心理由** - 一句话总结该机构的主要观点
5. **关键要点** - 4个支撑该预测的核心论据

请严格按照以下 JSON 结构返回（下面是**结构骨架**，方括号里是字段含义；
不要照抄任何数字，target_price 必须是你从检索到的内容里得到的真实数字）：

{{
    "institutions": [
        {{
            "name": "机构全名，如 高盛 (Goldman Sachs)",
            "logo": "机构缩写，如 GS",
            "rating": "bullish 或 bearish 或 neutral",
            "target_price": 该机构的目标价（美元，数字）,
            "timeframe": "该目标价对应的时间框架",
            "reasoning": "该机构核心理由（一句话）",
            "key_points": ["要点1", "要点2", "要点3", "要点4"]
        }}
    ],
    "analysis_summary": "四家机构预测的汇总（一句话）",
    "last_updated": "{current_time}"
}}

注意事项：
1. 必须返回有效 JSON
2. rating 只能是：bullish, bearish, neutral
3. target_price 必须是数字（美元）
4. **如果检索内容里没有某家机构的最新预测，就把该机构的 target_price 置为 null、
   reasoning 写「暂无最新预测」，不要凭印象替它编一个目标价。**
   编造的机构目标价比缺一条更糟 —— 见 docs/00-产品方向.md 第四节。
5. key_points 数组必须包含 4 个具体要点
"""

    @property
    def llm(self):
        """延迟创建 LLM 实例（供应商由 llm_provider 工厂统一决定）"""
        if self._llm is None:
            self._llm = get_chat_llm(temperature=0.7, max_tokens=4096)
        return self._llm

    def fetch_recent_news(self, db: Session, hours: int = 24) -> List[GoldNews]:
        """获取最近24小时内的新闻"""
        since = timeutil.now_naive() - timedelta(hours=hours)
        return db.query(GoldNews).filter(
            and_(
                GoldNews.published_at >= since,
                GoldNews.published_at <= timeutil.now_naive()
            )
        ).order_by(GoldNews.published_at.desc()).all()

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

    def analyze(self, db: Session) -> Dict[str, Any]:
        """执行分析 - 使用 MiMo 联网搜索"""
        # 使用MiMo 联网搜索获取最新机构预测
        try:
            logger.info("[InstitutionPrediction] 使用 MiMo 联网搜索机构预测...")
            search_result = self.web_search_service.search_institution_predictions()
            
            # 必须同时确认搜索真的可用，否则「搜到空结果」与「搜索不可用」
            # 会被混为一谈，上层就无法决定是否该回退。
            if search_result.get("available") and search_result.get("institutions"):
                logger.info(f"[InstitutionPrediction] 成功获取 {len(search_result['institutions'])} 家机构预测")
                search_result["last_updated"] = timeutil.now_str()
                search_result["data_source"] = "MiMo 联网搜索"
                return search_result
            else:
                logger.warning("[InstitutionPrediction] 搜索结果为空，使用备用方案")
                
        except Exception as e:
            logger.error(f"[InstitutionPrediction] MiMo 搜索失败: {e}")
        
        # 备用方案：使用传统方式分析
        return self._analyze_with_traditional_llm(db)
    
    def _analyze_with_traditional_llm(self, db: Session) -> Dict[str, Any]:
        """使用传统LLM分析（备用方案）"""
        # 1. 获取24小时内新闻
        news = self.fetch_recent_news(db, hours=24)

        # 如果数据库没有新闻，尝试从网络获取
        if not news:
            web_news = self.fetch_news_from_web()
            if web_news:
                news_content = format_news_for_prompt(web_news, limit=15)
            else:
                # 没有任何新闻可依据 —— 不调 LLM，直接返回空（红线第 1 条）
                logger.warning(
                    "[InstitutionPrediction] 24 小时内没有任何新闻，"
                    "不调用 LLM（没有依据可分析）"
                )
                return self.get_default_predictions()
        else:
            news_content = format_news_for_prompt(news, limit=15)

        # 2. 构建prompt并调用LLM
        current_time = timeutil.now_str()
        prompt = self.prompt_template.format(
            news_content=news_content,
            current_time=current_time
        )

        # 3. 调用LLM
        try:
            response = self.llm.invoke(prompt)

            # 4. 解析JSON响应
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
                    except:
                        result = self.get_default_predictions()
                else:
                    result = self.get_default_predictions()

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

    def save_to_database(self, db: Session, analysis_result: Dict[str, Any]) -> None:
        """将分析结果保存到数据库"""
        institutions = analysis_result.get("institutions", [])

        for inst_data in institutions:
            rating = normalize_rating(inst_data.get("rating"))

            # 检查是否已存在相同机构的预测
            existing = db.query(InstitutionView).filter(
                InstitutionView.institution_name == inst_data["name"]
            ).first()

            if existing:
                # 更新现有记录
                existing.rating = rating
                existing.target_price = inst_data.get("target_price", 0)
                existing.timeframe = inst_data.get("timeframe", "")
                existing.reasoning = inst_data.get("reasoning", "")
                existing.key_points = inst_data.get("key_points", [])
                existing.updated_at = timeutil.now_naive()
            else:
                # 创建新记录
                new_view = InstitutionView(
                    institution_name=inst_data["name"],
                    logo=inst_data.get("logo", ""),
                    rating=rating,
                    target_price=inst_data.get("target_price", 0),
                    timeframe=inst_data.get("timeframe", ""),
                    reasoning=inst_data.get("reasoning", ""),
                    key_points=inst_data.get("key_points", [])
                )
                db.add(new_view)

        db.commit()

class InstitutionPredictionService:
    """机构预测服务类 - 优化版（支持实时搜索和缓存）"""

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = InstitutionPredictionAnalyzer()
        self.cache = CacheManager("institution_predictions", ttl=AI_ANALYSIS_CACHE_TTL)  # 与调度器的刷新间隔对齐，见该常量的说明
        self.web_search_service = get_web_search_service()

    def get_institution_predictions(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        获取机构预测 - 快速响应版本（<50ms）

        优化策略：
        1. 优先从文件缓存读取（<10ms）
        2. 其次检查数据库缓存
        3. 无缓存时返回默认数据并触发后台分析
        4. use_cache=False时直接执行实时搜索

        Args:
            use_cache: 是否使用缓存（默认True，立即返回缓存数据）

        Returns:
            机构预测分析结果
        """
        # 如果强制刷新，直接执行实时搜索
        if not use_cache:
            logger.info("[InstitutionPrediction] 强制刷新，执行实时搜索...")
            try:
                result = self.analyzer.analyze(self.db)
                self.analyzer.save_to_database(self.db, result)
                self.cache.set(result)
                result["metadata"] = {
                    "cached": False,
                    "cache_source": "realtime_search",
                    "generated_at": timeutil.now_iso(),
                    "message": "基于MiMo 联网搜索的最新数据"
                }
                return result
            except Exception as e:
                logger.error(f"[InstitutionPrediction] 实时搜索失败: {e}")
                # 如果实时搜索失败，返回缓存数据
                pass
        
        # 1. 首先尝试文件缓存（最快，支持多进程共享）
        cached_data = self.cache.get()
        if cached_data:
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": timeutil.now_iso()
            }
            return cached_data

        # 2. 检查数据库中是否有最近2小时内的数据
        two_hours_ago = timeutil.now_naive() - timedelta(hours=2)
        recent_views = self.db.query(InstitutionView).filter(
            InstitutionView.updated_at >= two_hours_ago
        ).all()

        if len(recent_views) >= 4:
            # 使用数据库缓存数据
            result = {
                "institutions": [
                    {
                        "name": v.institution_name,
                        "logo": v.logo or self._get_logo(v.institution_name),
                        "rating": v.rating,
                        "target_price": v.target_price,
                        "timeframe": v.timeframe,
                        "reasoning": v.reasoning,
                        "key_points": v.key_points or []
                    }
                    for v in recent_views[:4]
                ],
                "analysis_summary": "基于最新市场数据的机构预测",
                # 用项目时区的当前时间，而不是 `updated_at` ——
                # 那一列是数据库的 `func.now()`（库服务器时间）生成的，
                # 容器里通常是 UTC，展示给用户会差 8 小时（红线 5）。
                "last_updated": timeutil.now_str(),
                "metadata": {
                    "cached": True,
                    "cache_source": "database",
                    "generated_at": timeutil.now_iso()
                }
            }
            # 更新文件缓存
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

    _ANALYSIS_KEY = "institution_predictions"

    def _trigger_background_analysis(self) -> None:
        """触发后台分析（不阻塞，同一服务同时只跑一个）。"""
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            return
        try:
            _executor.submit(self._guarded_background_task)
        except Exception as e:
            single_flight.end(self._ANALYSIS_KEY)
            logger.error(f"[InstitutionPrediction] 触发后台分析失败: {e}")

    def _guarded_background_task(self) -> None:
        """执行后台任务，结束后释放单飞占位。"""
        try:
            self._background_analysis_task()
        finally:
            single_flight.end(self._ANALYSIS_KEY)

    def _background_analysis_task(self) -> None:
        """后台分析任务"""
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                result = self.analyzer.analyze(db)
                self.analyzer.save_to_database(db, result)
                # 更新文件缓存
                self.cache.set(result)
                logger.info(f"[InstitutionPrediction] 后台分析完成，时间: {timeutil.now()}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[InstitutionPrediction] 后台分析失败: {e}")

    def refresh_analysis_sync(self) -> Dict[str, Any]:
        """同步刷新分析（阻塞，仅用于定时任务）。

        若同服务已有分析在跑（例如启动预热触发的后台任务），直接跳过 ——
        它产出的就是同一份结果，重复执行只是多花一次 LLM 费用。
        """
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            logger.warning("[InstitutionPrediction] 已有分析在执行，跳过本次刷新")
            return self.cache.get() or {}
        try:
            result = self.analyzer.analyze(self.db)
            self.analyzer.save_to_database(self.db, result)
            self.cache.set(result)
            return result
        finally:
            single_flight.end(self._ANALYSIS_KEY)

    async def refresh_analysis_async(self) -> Dict[str, Any]:
        """异步刷新分析（非阻塞）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self.refresh_analysis_sync)

    def _get_logo(self, name: str) -> str:
        """根据机构名称获取logo"""
        logo_map = {
            "高盛": "GS",
            "Goldman": "GS",
            "瑞银": "UBS",
            "UBS": "UBS",
            "摩根士丹利": "MS",
            "Morgan Stanley": "MS",
            "花旗": "C",
            "Citi": "C"
        }

        for key, value in logo_map.items():
            if key in name:
                return value

        return "BANK"
