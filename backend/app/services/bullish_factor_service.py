"""看涨因子分析服务 - 优化版（联网搜索可选，默认走数据库 / RSS）"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from concurrent.futures import ThreadPoolExecutor
import asyncio
from functools import partial

from app.services.news_service import format_news_for_prompt
from app.utils import timeutil
from app.models.news import GoldNews
from app.models.analysis import MarketFactor, FactorType, ImpactLevel
from app.config import settings
from app.services.cache_manager import CacheManager, AI_ANALYSIS_CACHE_TTL
from app.services.single_flight import single_flight
from app.services.llm_provider import (
    describe_completion,
    get_chat_llm,
    retry_on_content_filter,
)
from app.services.web_search_service import get_web_search_service
import json
from loguru import logger

# 全局线程池（所有服务共享）
_executor = ThreadPoolExecutor(max_workers=4)


class BullishFactorAnalyzer:
    """使用联网搜索分析黄金市场看涨因子（不可用时回退数据库 / RSS）"""
    
    def __init__(self):
        self._llm = None
        self.web_search_service = get_web_search_service()
        self.prompt_template = """你是一位专业的黄金市场分析师，专注于分析影响黄金价格上涨的因素。

当前金价数据：
- 当前价格: {current_price} 美元/盎司
- 今日涨跌: {price_change}%
- 2025年至今涨幅: {ytd_change}%

以下是从24小时内收集的黄金相关新闻资讯：
{news_content}

请根据以上新闻，分析当前黄金市场的看涨因素。识别出最重要的看涨因子（**最多 5 个**），每个因子应包含：

1. 美联储政策相关
2. 全球央行购金动态
3. 美元信用/美债问题
4. 地缘政治风险
5. 供需基本面

请严格按照以下JSON格式返回分析结果：

{{
    "bullish_factors": [
        {{
            "id": "fed-policy",
            "title": "美联储降息周期",
            "subtitle": "货币政策转向宽松",
            "description": "详细描述该因素如何支撑金价上涨...",
            "details": [
                "具体要点1",
                "具体要点2",
                "具体要点3",
                "具体要点4"
            ],
            "impact": "high"
        }},
        {{
            "id": "central-bank",
            "title": "全球央行持续购金",
            "subtitle": "去美元化趋势加速",
            "description": "详细描述...",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "high"
        }},
        {{
            "id": "dollar-credit",
            "title": "美元信用动摇",
            "subtitle": "美债规模持续攀升",
            "description": "详细描述...",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "high"
        }},
        {{
            "id": "geopolitical",
            "title": "地缘政治风险",
            "subtitle": "避险需求持续升温",
            "description": "详细描述...",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "medium"
        }},
        {{
            "id": "supply-demand",
            "title": "供需失衡支撑",
            "subtitle": "矿产金产量见顶",
            "description": "详细描述...",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "medium"
        }}
    ],
    "analysis_summary": "基于24小时新闻的综合分析总结...",
    "last_updated": "{current_time}"
}}

注意事项：
1. 必须返回有效的JSON格式
2. 每个因子的id必须是以下之一：fed-policy, central-bank, dollar-credit, geopolitical, supply-demand
3. impact只能是：high, medium, low
4. description应该基于新闻内容进行总结
5. details数组必须包含4个具体要点
6. **每个因子都必须有新闻支撑**。如果新闻不足以支撑 5 个因子，就只返回有支撑的那些 ——
   宁可少给几个，也不要为了凑满数量而凭常识编造。
   这条是项目红线，见 docs/00-产品方向.md 第四节。
"""

    @property
    def llm(self):
        """延迟创建 LLM 实例（供应商由 llm_provider 工厂统一决定）"""
        if self._llm is None:
            self._llm = get_chat_llm(temperature=0.7)
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
        """执行分析 - 尝试联网搜索，不可用时回退数据库 / RSS"""
        # 联网搜索获取最新看涨因素（默认关闭，见 LLM_SEARCH_ENABLED）
        try:
            logger.info("[BullishFactor] 尝试联网搜索看涨因素...")
            search_result = self._search_bullish_factors()
            
            # 检查搜索结果是否有效
            if search_result.get("bullish_factors") and len(search_result["bullish_factors"]) > 0:
                logger.info(f"[BullishFactor] 成功获取 {len(search_result['bullish_factors'])} 个看涨因素")
                search_result["last_updated"] = timeutil.now_str()
                search_result["data_source"] = "联网搜索"
                return search_result
            else:
                logger.warning("[BullishFactor] 搜索结果为空，使用备用方案")
                
        except Exception as e:
            logger.error(f"[BullishFactor] 联网搜索失败: {e}")
        
        # 备用方案：使用传统方式分析
        return self._analyze_with_traditional_llm(db)
    
    def _search_bullish_factors(self) -> Dict[str, Any]:
        """使用联网搜索查找看涨因素"""
        prompt = """请搜索并分析当前黄金市场的看涨因素。

请搜索最新的黄金市场新闻和分析报告，识别出5个最重要的看涨因子：

1. 美联储政策相关（降息预期、货币政策等）
2. 全球央行购金动态（各国央行增持黄金情况）
3. 美元信用/美债问题（美元走势、债务规模等）
4. 地缘政治风险（地区冲突、贸易摩擦等）
5. 供需基本面（矿产供应、投资需求等）

请严格按照以下JSON格式返回：

{
    "bullish_factors": [
        {
            "id": "fed-policy",
            "title": "美联储降息周期预期强化",
            "subtitle": "市场押注宽松周期开启，实际利率下行",
            "description": "详细描述该因素如何支撑金价上涨，基于最新新闻...",
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
2. 每个因子的id必须是：fed-policy, central-bank, dollar-credit, geopolitical, supply-demand
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
                "bullish_factors": [],
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
                news_content = format_news_for_prompt(web_news)
            else:
                # **一点新闻都没有 —— 不调 LLM。**
                #
                # 原实现这时塞一句「暂无最新新闻数据，将基于当前市场状况进行分析」，
                # 等于请模型用自己的记忆去补 —— 红线第 1 条明确禁止
                #（docs/00-产品方向.md 第四节）。产出的因子与真实分析长得一模一样，
                # 用户无从分辨。
                #
                # 而且这也省下一次没有依据的付费调用。
                logger.warning(
                    f"[{self.__class__.__name__}] 24 小时内没有任何新闻，"
                    "不调用 LLM（没有依据可分析）"
                )
                return self._get_default_factors()
        else:
            news_content = format_news_for_prompt(news)
        
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
            response = retry_on_content_filter(self.llm, prompt)
            
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
                        logger.error(
                            "[BullishFactor] JSON 解析失败"
                            f"（{describe_completion(response)}）"
                        )
                        result = self._get_default_factors()
                else:
                    logger.error(
                        "[BullishFactor] 输出里没有 JSON"
                        f"（{describe_completion(response)}）"
                    )
                    result = self._get_default_factors()
            
            return result
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self._get_default_factors()
    
    def _get_default_factors(self) -> Dict[str, Any]:
        """LLM 不可用 / 输出无法解析时返回的结构 —— **内容为空**。

        这里以前返回一组写死的看涨因子（「美联储降息周期」「美联储升息预期」…），
        每条都带具体描述与 impact。第 2 轮清掉的是**Service 类**里那份
        `_get_default_response()`，**Analyzer 类里这份漏掉了** —— 而它才是
        LLM 调用失败、JSON 解析失败、返回空内容这三条路径的落点。

        也就是说：模型一旦出问题，页面照样会显示一份看起来完整的分析，
        用户完全无从分辨。那违反红线第 1 条
        （「不为了好看而展示编造的数据 —— 宁可显示「数据不可用」」）。

        现在返回空列表 + 状态，由前端显示「正在分析中」或「暂不可用」。
        """
        return {
            "bullish_factors": [],
            "analysis_summary": "",
            "last_updated": timeutil.now_str(),
        }
    
    def save_to_database(self, db: Session, analysis_result: Dict[str, Any]) -> None:
        """将分析结果保存到数据库"""
        factors = analysis_result.get("bullish_factors", [])

        for factor_data in factors:
            # 检查是否已存在相同id的因子
            existing = db.query(MarketFactor).filter(
                and_(
                    MarketFactor.type == FactorType.BULLISH,
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
                    type=FactorType.BULLISH,
                    title=factor_data["title"],
                    subtitle=factor_data.get("subtitle", ""),
                    description=factor_data.get("description", ""),
                    details=factor_data.get("details", []),
                    impact=ImpactLevel(factor_data.get("impact", "medium"))
                )
                db.add(new_factor)
        
        db.commit()


class BullishFactorService:
    """看涨因子服务类 - 优化版"""
    
    def __init__(self, db: Session):
        self.db = db
        self.analyzer = BullishFactorAnalyzer()
        self.cache = CacheManager("bullish_factors", ttl=AI_ANALYSIS_CACHE_TTL)
    
    def get_bullish_factors(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        获取看涨因子 - 快速响应版本（<50ms）
        
        优化策略：
        1. 优先从缓存读取（<10ms）
        2. 无缓存时直接返回默认数据（<10ms）
        3. 后台触发AI分析
        4. use_cache=False时直接执行实时搜索
        
        Args:
            use_cache: 是否使用缓存（默认True，立即返回缓存数据）

        Returns:
            看涨因子分析结果
        """
        # 如果强制刷新，直接执行实时搜索
        if not use_cache:
            logger.info("[BullishFactor] 强制刷新，执行实时搜索...")
            try:
                result = self.analyzer.analyze(self.db)
                self.analyzer.save_to_database(self.db, result)
                self.cache.set(result)
                result["metadata"] = {
                    "cached": False,
                    "cache_source": "realtime_search",
                    "generated_at": timeutil.now_iso(),
                    "message": "基于联网搜索的最新数据"
                }
                return result
            except Exception as e:
                logger.error(f"[BullishFactor] 实时搜索失败: {e}")
                # 如果实时搜索失败，返回缓存数据
                pass
        
        # 1. 首先尝试缓存（支持多进程共享）
        cached_data = self.cache.get()
        if cached_data:
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": timeutil.now_iso()
            }
            return cached_data
        
        # 2. 无缓存时，直接返回默认数据并触发后台更新
        default_data = self._get_default_response()
        
        # 触发后台分析
        self._trigger_background_analysis()
        
        return default_data
    
    def _get_default_response(self) -> Dict[str, Any]:
        """无缓存时立刻返回的响应 —— **内容为空**。

        这里以前返回一组写死的看涨因子，让页面在分析跑完前看起来「有内容」。
        那违反项目红线：「不为了好看而展示编造的数据 —— 宁可显示「数据不可用」」。
        编造的因子与真实分析在结构上完全一样，用户无从分辨。

        现在只回一个状态：前端据此显示「正在分析中」，而不是把内置文案当结论。
        """
        return {
            "bullish_factors": [],
            "analysis_summary": "",
            "last_updated": timeutil.now_str(),
            "metadata": {
                "cached": False,
                "status": "analyzing",
                "message": "AI分析进行中，首次加载可能需要1-2分钟",
            },
        }
    
    # 单飞去重用的键：同一服务同时只允许一个后台分析在跑
    _ANALYSIS_KEY = "bullish_factors"

    def _trigger_background_analysis(self) -> None:
        """触发后台分析（不阻塞，同一服务同时只跑一个）。

        原实现每次触发都往线程池塞一个任务：N 个并发请求会把同一次分析重复执行
        N 遍，每一遍都真实调用付费 LLM。
        """
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            return
        try:
            _executor.submit(self._guarded_background_task)
        except Exception as e:
            single_flight.end(self._ANALYSIS_KEY)
            logger.error(f"[BullishFactor] 触发后台分析失败: {e}")

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
                # 更新缓存
                self.cache.set(result)
                logger.info(f"[BullishFactor] 后台分析完成，时间: {timeutil.now()}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[BullishFactor] 后台分析失败: {e}")

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
            self.cache.set(result)
            return result
        finally:
            db.close()

    def refresh_analysis_sync(self) -> Dict[str, Any]:
        """同步刷新分析（阻塞，仅用于定时任务）。

        若同服务已有分析在跑（例如启动预热触发的后台任务），直接跳过 ——
        它产出的就是同一份结果，重复执行只是多花一次 LLM 费用。
        """
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            logger.warning("[BullishFactor] 已有分析在执行，跳过本次刷新")
            return self.cache.get() or {}
        try:
            result = self.analyzer.analyze(self.db)
            self.analyzer.save_to_database(self.db, result)
            self.cache.set(result)
            return result
        finally:
            single_flight.end(self._ANALYSIS_KEY)
    
    def _get_factor_id(self, title: str) -> str:
        """根据标题获取因子ID"""
        id_map = {
            "美联储": "fed-policy",
            "央行": "central-bank",
            "美元": "dollar-credit",
            "地缘": "geopolitical",
            "供需": "supply-demand",
            "供应": "supply-demand"
        }
        
        for key, value in id_map.items():
            if key in title:
                return value
        
        return "other"
