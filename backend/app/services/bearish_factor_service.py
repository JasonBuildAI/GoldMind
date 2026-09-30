"""看空因子分析服务 - 优化版（支持MiMo 联网搜索）"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from concurrent.futures import ThreadPoolExecutor
import time
import threading
import asyncio
from functools import partial

from app.utils import timeutil
from app.models.news import GoldNews
from app.models.analysis import MarketFactor, FactorType, ImpactLevel
from app.config import settings
from app.services.cache_manager import CacheManager
from app.services.single_flight import single_flight
from app.services.llm_provider import get_chat_llm
from app.services.web_search_service import get_web_search_service
import json
from loguru import logger

# 全局线程池（所有服务共享）
_executor = ThreadPoolExecutor(max_workers=4)

# 内存缓存
_cache = {}
_cache_lock = threading.Lock()
_cache_ttl = 7200  # 2小时


class BearishFactorAnalyzer:
    """使用MiMo 联网搜索分析黄金市场看空因子"""

    def __init__(self):
        self._llm = None
        self.web_search_service = get_web_search_service()
        self.prompt_template = """你是一位专业的黄金市场分析师，专注于分析影响黄金价格下跌的因素。

当前金价数据：
- 当前价格: {current_price} 美元/盎司
- 今日涨跌: {price_change}%
- 2025年至今涨幅: {ytd_change}%

以下是从24小时内收集的黄金相关新闻资讯：
{news_content}

请根据以上新闻，分析当前黄金市场的看空因素。你需要识别出5个最重要的看空因子，每个因子应包含：

1. 美联储政策相关（升息预期、推迟降息等）
2. 技术性回调/获利了结压力
3. 地缘政治风险缓和
4. 美元走强因素
5. 全球经济改善/避险需求减弱

请严格按照以下JSON格式返回分析结果：

{{
    "bearish_factors": [
        {{
            "id": "rate-hike",
            "title": "美联储升息预期",
            "subtitle": "降息时点可能推迟",
            "description": "详细描述该因素如何压制金价...",
            "details": [
                "具体要点1",
                "具体要点2",
                "具体要点3",
                "具体要点4"
            ],
            "impact": "high"
        }},
        {{
            "id": "profit-taking",
            "title": "获利了结压力",
            "subtitle": "投机性头寸平仓",
            "description": "详细描述...",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "medium"
        }},
        {{
            "id": "geopolitical-ease",
            "title": "地缘风险缓和",
            "subtitle": "避险溢价回落",
            "description": "详细描述...",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "medium"
        }},
        {{
            "id": "dollar-strength",
            "title": "美元阶段性走强",
            "subtitle": "汇率效应压制金价",
            "description": "详细描述...",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "medium"
        }},
        {{
            "id": "economic-growth",
            "title": "全球经济改善",
            "subtitle": "避险需求减弱",
            "description": "详细描述...",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "low"
        }}
    ],
    "analysis_summary": "基于24小时新闻的综合分析总结...",
    "last_updated": "{current_time}"
}}

注意事项：
1. 必须返回有效的JSON格式
2. 每个因子的id必须是以下之一：rate-hike, profit-taking, geopolitical-ease, dollar-strength, economic-growth
3. impact只能是：high, medium, low
4. description应该基于新闻内容进行总结
5. details数组必须包含4个具体要点
6. 如果没有相关新闻支撑某个因子，请基于当前市场常识合理推断
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

    def get_current_gold_data(self, db: Session) -> Dict[str, Any]:
        """获取当前金价数据"""
        from app.models.gold_price import GoldPrice

        # 获取最新价格
        latest = db.query(GoldPrice).order_by(GoldPrice.date.desc()).first()

        # 获取2025年第一天的价格
        start_of_2025 = db.query(GoldPrice).filter(
            GoldPrice.date >= datetime(2025, 1, 1)
        ).order_by(GoldPrice.date.asc()).first()

        if latest and start_of_2025:
            ytd_change = ((latest.close_price - start_of_2025.close_price) / start_of_2025.close_price) * 100

            # 计算今日涨跌（与昨日对比）
            yesterday = db.query(GoldPrice).filter(
                GoldPrice.date < latest.date
            ).order_by(GoldPrice.date.desc()).first()

            price_change = 0
            if yesterday:
                price_change = ((latest.close_price - yesterday.close_price) / yesterday.close_price) * 100

            return {
                "current_price": round(latest.close_price, 2),
                "price_change": round(price_change, 2),
                "ytd_change": round(ytd_change, 2)
            }

        # 没有行情数据时返回 None。原实现返回 2800.00 / +0.5% / +15.0%
        # 这组写死的数字，它们会被拼进 prompt 当作「当前市场数据」，
        # 模型很可能直接引用 —— 等于用编造的行情喂出编造的分析。
        logger.warning(f"[{self.__class__.__name__}] 数据库里没有可用金价，prompt 中标注为暂无数据")
        return None

    def analyze(self, db: Session) -> Dict[str, Any]:
        """执行分析 - 使用MiMo 联网搜索"""
        # 使用MiMo 联网搜索获取最新看空因素
        try:
            logger.info("[BearishFactor] 使用MiMo 联网搜索看空因素...")
            search_result = self._search_bearish_factors()
            
            # 检查搜索结果是否有效
            if search_result.get("bearish_factors") and len(search_result["bearish_factors"]) > 0:
                logger.info(f"[BearishFactor] 成功获取 {len(search_result['bearish_factors'])} 个看空因素")
                search_result["last_updated"] = timeutil.now_str()
                search_result["data_source"] = "MiMo 联网搜索"
                return search_result
            else:
                logger.warning("[BearishFactor] 搜索结果为空，使用备用方案")
                
        except Exception as e:
            logger.error(f"[BearishFactor] MiMo 搜索失败: {e}")
        
        # 备用方案：使用传统方式分析
        return self._analyze_with_traditional_llm(db)
    
    def _search_bearish_factors(self) -> Dict[str, Any]:
        """使用 MiMo 搜索看空因素"""
        prompt = """请搜索并分析当前黄金市场的看空因素。

请搜索最新的黄金市场新闻和分析报告，识别出5个最重要的看空因子：

1. 美联储政策相关（升息预期、推迟降息等）
2. 技术性回调/获利了结压力
3. 地缘政治风险缓和
4. 美元走强因素
5. 全球经济改善/避险需求减弱

请严格按照以下JSON格式返回：

{
    "bearish_factors": [
        {
            "id": "rate-hike",
            "title": "美联储升息预期",
            "subtitle": "降息时点可能推迟",
            "description": "详细描述该因素如何压制金价，基于最新新闻...",
            "details": [
                "具体要点1：基于最新数据",
                "具体要点2：基于最新数据",
                "具体要点3：基于最新数据",
                "具体要点4：基于最新数据"
            ],
            "impact": "high"
        }
    ],
    "analysis_summary": "基于实时搜索的综合分析总结...",
    "search_time": "2026-02-01"
}

注意事项：
1. 必须返回有效的JSON格式
2. 每个因子的id必须是：rate-hike, profit-taking, geopolitical-ease, dollar-strength, global-growth
3. impact只能是：high, medium, low
4. description和details必须基于搜索到的最新新闻内容
5. 确保5个因子都有数据
"""
        
        result = self.web_search_service.search_json(prompt)
        if not result.get("available"):
            # 联网搜索不可用（密钥缺失 / 插件未开通 / 凭证无权调用）时返回空结果，
            # 交给 analyze() 回退到数据库与 RSS 新闻。绝不编造因子 ——
            # 迁移前这里会把「搜索失败: ...」当成分析结果返回给上层。
            return {
                "bearish_factors": [],
                "analysis_summary": f"联网搜索不可用: {result.get('reason')}",
            }
        return result
    
    def _analyze_with_traditional_llm(self, db: Session) -> Dict[str, Any]:
        """使用传统LLM分析（备用方案）"""
        # 1. 获取24小时内新闻
        news = self.fetch_recent_news(db, hours=24)

        # 如果数据库没有新闻，尝试从网络获取
        if not news:
            web_news = self.fetch_news_from_web()
            if web_news:
                news_content = "\n".join([
                    f"[{n.get('source', '未知')}] {n.get('title', '')}"
                    for n in web_news[:15]
                ])
            else:
                news_content = "暂无最新新闻数据，将基于当前市场状况进行分析。"
        else:
            news_content = "\n".join([
                f"[{n.source}] {n.title}"
                for n in news[:15]
            ])

        # 2. 获取当前金价数据
        gold_data = self.get_current_gold_data(db)

        # 3. 构建prompt并调用LLM
        current_time = timeutil.now_str()
        prompt = self.prompt_template.format(
            # gold_data 可能为 None（数据库里没有金价）—— 那时如实写「暂无数据」，
            # 而不是解引用一个编造的默认值
            current_price=gold_data["current_price"] if gold_data else "暂无数据",
            price_change=gold_data["price_change"] if gold_data else "暂无数据",
            ytd_change=gold_data["ytd_change"] if gold_data else "暂无数据",
            news_content=news_content,
            current_time=current_time
        )

        # 4. 调用LLM
        try:
            response = self.llm.invoke(prompt)

            # 5. 解析JSON响应
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
                        result = self._get_default_factors()
                else:
                    result = self._get_default_factors()

            return result
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self._get_default_factors()

    def _get_default_factors(self) -> Dict[str, Any]:
        """获取默认看空因子（当LLM调用失败时使用）"""
        return {
            "bearish_factors": [
                {
                    "id": "rate-hike",
                    "title": "美联储升息预期",
                    "subtitle": "降息时点可能推迟",
                    "description": "若美国通胀持续高位运行，美联储可能推迟降息甚至重新升息。升息将提高持有黄金的机会成本，对金价形成压制。",
                    "details": [
                        "关税政策带来的成本传导可能使通胀持续高位",
                        "摩根士丹利预计降息时点推迟至6月和9月",
                        "升息预期升温导致美元走强，压制金价",
                        "实际利率上升降低黄金吸引力"
                    ],
                    "impact": "high"
                },
                {
                    "id": "profit-taking",
                    "title": "获利了结压力",
                    "subtitle": "投机性头寸平仓",
                    "description": "金价快速上涨后积累大量获利盘，技术性回调需求增加。投机性头寸平仓可能引发连锁反应，导致短期剧烈波动。",
                    "details": [
                        "2025年10月金价曾单日暴跌6%",
                        "ETF市场结构失衡放大波动",
                        "散户与机构行为分化加剧震荡",
                        "高价位吸引获利盘出逃"
                    ],
                    "impact": "medium"
                },
                {
                    "id": "geopolitical-ease",
                    "title": "地缘风险缓和",
                    "subtitle": "避险溢价回落",
                    "description": "若俄乌冲突出现停火进展、中美关系缓和等地缘风险降温，黄金的避险溢价将显著回落，可能导致价格调整。",
                    "details": [
                        "俄乌停火谈判若取得进展将降低避险需求",
                        "中美高层互动释放缓和信号",
                        "地缘风险溢价回落导致金价调整",
                        "避险需求常态化程度有限"
                    ],
                    "impact": "medium"
                },
                {
                    "id": "dollar-strength",
                    "title": "美元阶段性走强",
                    "subtitle": "汇率效应压制金价",
                    "description": "美元指数阶段性反弹对金价形成直接压制。美元与黄金通常呈现负相关关系，美元走强时金价往往承压。",
                    "details": [
                        "2025年10月美元指数上涨3.6%压制金价",
                        "美国经济韧性支撑美元",
                        "美元升值使黄金对其他货币持有者更贵",
                        "汇率效应直接影响黄金计价"
                    ],
                    "impact": "medium"
                },
                {
                    "id": "economic-growth",
                    "title": "全球经济改善",
                    "subtitle": "避险需求减弱",
                    "description": "若全球经济回到'金发女孩'状态（适度增长、低通胀），风险资产吸引力上升，黄金避险需求将相应减弱。",
                    "details": [
                        "花旗预计2026年美国经济回到适中成长状态",
                        "全球经济增长预期改善降低避险需求",
                        "风险资产吸引力上升分流资金",
                        "经济向好时黄金配置价值相对下降"
                    ],
                    "impact": "low"
                }
            ],
            "analysis_summary": "基于当前市场状况的综合分析",
            "last_updated": timeutil.now_str()
        }

    def save_to_database(self, db: Session, analysis_result: Dict[str, Any]) -> None:
        """将分析结果保存到数据库"""
        factors = analysis_result.get("bearish_factors", [])

        for factor_data in factors:
            # 检查是否已存在相同id的因子
            existing = db.query(MarketFactor).filter(
                and_(
                    MarketFactor.type == FactorType.BEARISH,
                    MarketFactor.title == factor_data["title"]
                )
            ).first()

            if existing:
                # 更新现有记录
                existing.subtitle = factor_data.get("subtitle", "")
                existing.description = factor_data.get("description", "")
                existing.details = factor_data.get("details", [])
                existing.impact = ImpactLevel(factor_data.get("impact", "medium"))
                existing.updated_at = timeutil.now_naive()
            else:
                # 创建新记录
                new_factor = MarketFactor(
                    type=FactorType.BEARISH,
                    title=factor_data["title"],
                    subtitle=factor_data.get("subtitle", ""),
                    description=factor_data.get("description", ""),
                    details=factor_data.get("details", []),
                    impact=ImpactLevel(factor_data.get("impact", "medium"))
                )
                db.add(new_factor)

        db.commit()


class BearishFactorService:
    """看空因子服务类 - 优化版"""

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = BearishFactorAnalyzer()
        self._cache_key = "bearish_factors"
        self.cache = CacheManager("bearish_factors", ttl=7200)  # 2小时缓存

    def _get_from_memory_cache(self) -> Optional[Dict[str, Any]]:
        """从内存缓存获取数据"""
        global _cache
        with _cache_lock:
            if self._cache_key in _cache:
                cached_data, timestamp = _cache[self._cache_key]
                if time.time() - timestamp < _cache_ttl:
                    return cached_data
        return None

    def _store_result(self, result: Dict[str, Any]) -> None:
        """写入两级缓存：进程内内存 + 文件（供重启/多进程共享）。

        迁移前只写了内存缓存，`self.cache`（CacheManager）虽然被构造却从未使用，
        导致看跌因子的文件缓存完全是死的：服务一重启就只能回退到硬编码默认值，
        而看涨因子却能命中文件缓存 —— 两者行为不一致。
        """
        self._set_memory_cache(result)
        self.cache.set(result)

    def _set_memory_cache(self, data: Dict[str, Any]) -> None:
        """设置内存缓存"""
        global _cache
        with _cache_lock:
            _cache[self._cache_key] = (data, time.time())

    def get_bearish_factors(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        获取看空因子 - 快速响应版本（<50ms）

        优化策略：
        1. 优先从内存缓存读取（<1ms）
        2. 无内存缓存时直接返回默认数据（<10ms）
        3. 后台触发数据库查询和AI分析
        4. use_cache=False时直接执行实时搜索

        Args:
            use_cache: 是否使用缓存（默认True，立即返回缓存数据）

        Returns:
            看空因子分析结果
        """
        # 如果强制刷新，直接执行实时搜索
        if not use_cache:
            logger.info("[BearishFactor] 强制刷新，执行实时搜索...")
            try:
                result = self.analyzer.analyze(self.db)
                self.analyzer.save_to_database(self.db, result)
                self._store_result(result)
                result["metadata"] = {
                    "cached": False,
                    "cache_source": "realtime_search",
                    "generated_at": timeutil.now_iso(),
                    "message": "基于MiMo 联网搜索的最新数据"
                }
                return result
            except Exception as e:
                logger.error(f"[BearishFactor] 实时搜索失败: {e}")
                # 如果实时搜索失败，返回缓存数据
                pass
        
        # 1. 首先尝试内存缓存（最快，<1ms）
        memory_cache = self._get_from_memory_cache()
        if memory_cache:
            memory_cache["metadata"] = {
                "cached": True,
                "cache_source": "memory",
                "generated_at": timeutil.now_iso()
            }
            return memory_cache

        # 2. 其次尝试文件缓存（支持进程重启与多进程共享）
        cached_data = self.cache.get()
        if cached_data:
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": timeutil.now_iso()
            }
            return cached_data

        # 3. 都未命中时直接返回默认数据并触发后台更新
        # 不查询数据库，避免阻塞
        default_data = self._get_default_response()

        # 触发后台分析（包括数据库查询和AI分析）
        self._trigger_background_analysis()

        return default_data

    def _get_default_response(self) -> Dict[str, Any]:
        """无缓存时立刻返回的响应 —— **内容为空**。

        同 BullishFactorService：这里以前返回写死的看跌因子（还带着
        「2025年10月金价曾单日暴跌6%」这类具体历史数字），属于编造数据。
        """
        return {
            "bearish_factors": [],
            "analysis_summary": "",
            "last_updated": timeutil.now_str(),
            "metadata": {
                "cached": False,
                "status": "analyzing",
                "message": "AI分析进行中，首次加载可能需要1-2分钟",
            },
        }

    _ANALYSIS_KEY = "bearish_factors"

    def _trigger_background_analysis(self) -> None:
        """触发后台分析（不阻塞，同一服务同时只跑一个）。"""
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            return
        try:
            _executor.submit(self._guarded_background_task)
        except Exception as e:
            single_flight.end(self._ANALYSIS_KEY)
            logger.error(f"[BearishFactor] 触发后台分析失败: {e}")

    def _guarded_background_task(self) -> None:
        """执行后台任务，结束后释放单飞占位。"""
        try:
            self._background_analysis_task()
        finally:
            single_flight.end(self._ANALYSIS_KEY)


    def _background_analysis_task(self) -> None:
        """后台分析任务"""
        try:
            # 创建新的数据库会话
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                result = self.analyzer.analyze(db)
                self.analyzer.save_to_database(db, result)
                # 更新内存缓存
                self._store_result(result)
                logger.info(f"[BearishFactor] 后台分析完成，时间: {timeutil.now()}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[BearishFactor] 后台分析失败: {e}")

    async def refresh_analysis_async(self) -> Dict[str, Any]:
        """
        异步刷新分析 - 用于强制刷新场景

        使用线程池执行AI分析，不阻塞主线程
        """
        loop = asyncio.get_event_loop()

        # 在线程池中执行分析
        result = await loop.run_in_executor(
            _executor,
            partial(self._analyze_with_new_db)
        )

        return result

    def _analyze_with_new_db(self) -> Dict[str, Any]:
        """使用新数据库会话执行分析"""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            result = self.analyzer.analyze(db)
            self.analyzer.save_to_database(db, result)
            self._store_result(result)
            return result
        finally:
            db.close()

    def refresh_analysis_sync(self) -> Dict[str, Any]:
        """同步刷新分析（阻塞，仅用于定时任务）。

        若同服务已有分析在跑（例如启动预热触发的后台任务），直接跳过 ——
        它产出的就是同一份结果，重复执行只是多花一次 LLM 费用。
        """
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            logger.warning("[BearishFactor] 已有分析在执行，跳过本次刷新")
            return self.cache.get() or {}
        try:
            result = self.analyzer.analyze(self.db)
            self.analyzer.save_to_database(self.db, result)
            self._store_result(result)
            return result
        finally:
            single_flight.end(self._ANALYSIS_KEY)

    def _get_factor_id(self, title: str) -> str:
        """根据标题获取因子ID"""
        id_map = {
            "升息": "rate-hike",
            "加息": "rate-hike",
            "美联储": "rate-hike",
            "获利": "profit-taking",
            "平仓": "profit-taking",
            "地缘": "geopolitical-ease",
            "风险缓和": "geopolitical-ease",
            "美元": "dollar-strength",
            "经济": "economic-growth",
            "全球": "economic-growth"
        }

        for key, value in id_map.items():
            if key in title:
                return value

        return "other"
