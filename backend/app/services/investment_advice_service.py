"""投资建议分析服务 - 优化版（支持快速缓存响应）"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
import asyncio

from app.services.news_service import format_news_for_prompt
from app.utils import timeutil
from app.models.news import GoldNews
from app.models.gold_price import GoldPrice
from app.config import settings
from app.services.cache_manager import CacheManager, AI_ANALYSIS_CACHE_TTL
from app.services.single_flight import single_flight
from app.services.llm_provider import get_chat_llm
import json
import logging
from loguru import logger

logger = logging.getLogger(__name__)

# 全局线程池
_executor = ThreadPoolExecutor(max_workers=2)


class InvestmentAdviceAnalyzer:
    """使用LangChain Agent分析市场数据，生成个性化投资建议"""

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        """延迟创建 LLM 实例（供应商由 llm_provider 工厂统一决定）"""
        if self._llm is None:
            self._llm = get_chat_llm(temperature=0.7, max_tokens=4096)
        return self._llm

    def _fetch_recent_news(self, db: Session, hours: int = 24) -> List[GoldNews]:
        """获取最近 N 小时**发布**的新闻。

        原实现按 `created_at`（入库时刻）过滤与排序：
          - 过滤：一条三天前发布、刚刚抓到的新闻会被算进来，
            而两小时前发布、昨天抓到的会被排除 —— 窗口没有意义；
          - 排序：抓取是每 2 小时**批量**插入的，同一批的 `created_at` 几乎相同，
            于是「最近 20 条」实际是这一批里的任意 20 条。
        而且 `created_at` 是数据库生成的（库服务器时间），按红线也不该拿来比。

        统一走 `NewsService.get_recent_news()` —— 其余四个服务用的就是它。
        """
        from app.services.news_service import NewsService

        return NewsService(db).get_recent_news(hours=hours)[:20]

    def _fetch_latest_price(self, db: Session) -> Optional[GoldPrice]:
        """获取最新金价"""
        return db.query(GoldPrice).order_by(GoldPrice.date.desc()).first()

    def _fetch_recent_prices(self, db: Session, days: int = 10) -> List[GoldPrice]:
        """获取最近N天的价格数据"""
        cutoff_date = timeutil.now_naive() - timedelta(days=days)
        return db.query(GoldPrice).filter(
            GoldPrice.date >= cutoff_date
        ).order_by(GoldPrice.date.desc()).limit(days).all()

    def _fetch_ytd_data(self, db: Session) -> Dict[str, Any]:
        """获取2025年至今的数据"""
        start_of_year = datetime(2025, 1, 1)
        
        start_price = db.query(GoldPrice).filter(
            GoldPrice.date >= start_of_year
        ).order_by(GoldPrice.date.asc()).first()
        
        current_price = self._fetch_latest_price(db)
        
        period_high = db.query(GoldPrice).filter(
            GoldPrice.date >= start_of_year
        ).order_by(GoldPrice.close_price.desc()).first()
        
        period_low = db.query(GoldPrice).filter(
            GoldPrice.date >= start_of_year
        ).order_by(GoldPrice.close_price.asc()).first()
        
        if start_price and current_price:
            ytd_change = ((current_price.close_price - start_price.close_price) / start_price.close_price) * 100
            volatility_range = ((period_high.close_price - period_low.close_price) / period_low.close_price) * 100 if period_high and period_low else 0
            
            return {
                "current_price": current_price.close_price,
                "start_price": start_price.close_price,
                "ytd_change": ytd_change,
                "period_high": period_high.close_price if period_high else current_price.close_price,
                "period_low": period_low.close_price if period_low else current_price.close_price,
                "volatility_range": volatility_range
            }
        
        # 没有行情数据时返回 None。原实现返回 2800/2650 这组写死的价格，
        # 会被拼进 prompt 当作「实时金价数据」，模型可能直接引用。
        logger.warning("[InvestmentAdvice] 数据库里没有可用金价，prompt 中标注为暂无数据")
        return None

    def _format_news(self, news_list: List[GoldNews]) -> str:
        """格式化新闻内容。

        统一走 `news_service.format_news_for_prompt` —— 这里原先自己拼一份，
        用的是 `created_at`（入库时刻）而不是 `published_at`（发布时刻）。
        """
        return format_news_for_prompt(news_list, limit=10)

    def _format_prices(self, prices: List[GoldPrice]) -> str:
        """格式化价格数据"""
        if not prices:
            return "暂无价格数据"
        
        formatted = []
        for price in prices:
            formatted.append(f"- {price.date.strftime('%Y-%m-%d')}: ${price.close_price:.2f}")
        return "\n".join(formatted)

    def analyze(
        self,
        db: Session,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict]
    ) -> Dict[str, Any]:
        """分析市场数据并生成投资建议"""
        try:
            recent_news = self._fetch_recent_news(db)
            ytd_data = self._fetch_ytd_data(db)
            recent_prices = self._fetch_recent_prices(db)
            
            price_block = (
                f"- 当前金价: ${ytd_data['current_price']:.2f} 美元/盎司\n"
                f"- 2025年至今涨幅: {ytd_data['ytd_change']:+.2f}%\n"
                f"- 期间最高: ${ytd_data['period_high']:.2f}\n"
                f"- 期间最低: ${ytd_data['period_low']:.2f}\n"
                f"- 波动区间: {ytd_data['volatility_range']:.2f}%"
            ) if ytd_data else "暂无行情数据（数据库里没有可用的金价记录）"

            news_content = self._format_news(recent_news)
            prices_content = self._format_prices(recent_prices)
            bullish_content = json.dumps(bullish_factors, ensure_ascii=False, indent=2) if bullish_factors else "暂无数据"
            bearish_content = json.dumps(bearish_factors, ensure_ascii=False, indent=2) if bearish_factors else "暂无数据"
            institution_content = json.dumps(institution_predictions, ensure_ascii=False, indent=2) if institution_predictions else "暂无数据"
            
            prompt_template = f"""你是一位资深的黄金投资顾问，拥有20年以上的贵金属市场分析经验。你的投资风格偏向保守稳健，注重风险控制和长期价值投资。

你的任务是基于当前市场数据，为不同风险偏好的投资者生成具体、实用、保守的投资策略建议。

## 当前市场数据

### 1. 实时金价数据
{price_block}

### 2. 市场状态
{market_status}

### 3. 近期价格走势（最近10天）
{prices_content}

### 4. 看涨因子分析
{bullish_content}

### 5. 看跌因子分析
{bearish_content}

### 6. 机构预测汇总
{institution_content}

### 7. 24小时内相关新闻
{news_content}

## 你的任务

请基于以上数据，生成三个层级的投资策略建议。你的建议必须：
1. **保守稳健** - 优先考虑资本保全，而非追求高收益
2. **具体可操作** - 给出明确的配置比例、入场价位、止损设置
3. **风险导向** - 充分提示每种策略的风险和适用条件
4. **结合当前市场** - 根据当前金价位置和市场状态调整建议

请严格按照以下JSON格式返回分析结果：

{{
    "market_assessment": {{
        "current_position": "当前金价处于什么位置（高位/中位/低位）",
        "risk_level": "当前市场风险等级（low/medium/high）",
        "recommended_approach": "总体建议（积极/谨慎/观望）",
        "key_considerations": ["当前投资需要重点关注的3个因素"]
    }},
    "strategies": [
        {{
            "type": "conservative",
            "title": "保守配置策略",
            "description": "适合风险厌恶型投资者，追求资产保值和稳定收益",
            "allocation": "资产配置的X-Y%",
            "timeframe": "建议持有周期",
            "risk_level": "low",
            "entry_strategy": {{
                "current_price_assessment": "对当前价位的评估",
                "recommended_entry_range": "建议入场价位区间",
                "entry_timing": "入场时机建议（立即/等待回调/分批）",
                "position_building": "具体建仓方案（如：分3批，每批间隔X美元）"
            }},
            "exit_strategy": {{
                "profit_target": "建议止盈价位或涨幅",
                "stop_loss": "建议止损价位或跌幅",
                "rebalancing_trigger": "触发再平衡的条件"
            }},
            "pros": ["该策略的3-4个优势"],
            "cons": ["该策略的3-4个风险/劣势"],
            "suitable_for": ["适合该策略的投资者特征"],
            "execution_steps": ["具体执行步骤1", "具体执行步骤2", "具体执行步骤3"]
        }},
        {{
            "type": "balanced",
            "title": "均衡配置策略",
            "description": "适合有一定经验的投资者，在风险和收益之间寻求平衡",
            "allocation": "资产配置的X-Y%",
            "timeframe": "建议持有周期",
            "risk_level": "medium",
            "entry_strategy": {{
                "current_price_assessment": "对当前价位的评估",
                "recommended_entry_range": "建议入场价位区间",
                "entry_timing": "入场时机建议",
                "position_building": "具体建仓方案"
            }},
            "exit_strategy": {{
                "profit_target": "建议止盈价位或涨幅",
                "stop_loss": "建议止损价位或跌幅",
                "rebalancing_trigger": "触发再平衡的条件"
            }},
            "pros": ["该策略的3-4个优势"],
            "cons": ["该策略的3-4个风险/劣势"],
            "suitable_for": ["适合该策略的投资者特征"],
            "execution_steps": ["具体执行步骤1", "具体执行步骤2", "具体执行步骤3"]
        }},
        {{
            "type": "opportunistic",
            "title": "机会型策略",
            "description": "适合风险承受能力较强、能够承受短期波动的投资者，捕捉市场机会",
            "allocation": "资产配置的X-Y%（保守建议，不超过10%）",
            "timeframe": "建议持有周期",
            "risk_level": "high",
            "entry_strategy": {{
                "current_price_assessment": "对当前价位的评估",
                "recommended_entry_range": "建议入场价位区间",
                "entry_timing": "入场时机建议",
                "position_building": "具体建仓方案"
            }},
            "exit_strategy": {{
                "profit_target": "建议止盈价位或涨幅",
                "stop_loss": "建议止损价位或跌幅",
                "rebalancing_trigger": "触发再平衡的条件"
            }},
            "pros": ["该策略的3-4个优势"],
            "cons": ["该策略的3-4个风险/劣势"],
            "suitable_for": ["适合该策略的投资者特征"],
            "execution_steps": ["具体执行步骤1", "具体执行步骤2", "具体执行步骤3"]
        }}
    ],
    "core_principles": [
        {{
            "title": "风险管理",
            "description": "基于当前市场状况的风险管理建议"
        }},
        {{
            "title": "仓位控制",
            "description": "具体的仓位控制原则"
        }},
        {{
            "title": "再平衡策略",
            "description": "何时以及如何调整持仓"
        }},
        {{
            "title": "心理准备",
            "description": "投资者应该有的心态准备"
        }}
    ],
    "risk_warning": "针对当前市场的风险提示",
    "disclaimer": "标准免责声明"
}}

重要提示：
1. 所有建议必须基于提供的市场数据，不能编造
2. 配置比例要保守，建议不超过资产的15-20%
3. 必须给出具体的入场价位区间，而非模糊建议
4. 必须明确止损和止盈设置
5. 风险提示要充分且具体"""
            
            response = self.llm.invoke(prompt_template)
            
            try:
                content = response.content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content.strip()
                
                result = json.loads(json_str)
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {e}")
                return self.get_default_advice()
                
        except Exception as e:
            logger.error(f"投资建议分析失败: {e}")
            return self.get_default_advice()

    def get_default_advice(self) -> Dict[str, Any]:
        """分析不可用时返回的结构 —— **内容为空**。

        这里以前返回三档写死的策略，还带着「等待金价回调至2700-2750美元区间」
        这类具体点位。编造投资点位比编造新闻更危险，直接删掉。
        """
        return {
            "market_assessment": {},
            "strategies": [],
            "core_principles": [],
            "risk_warning": "",
            "disclaimer": "",
        }


class InvestmentAdviceService:
    """投资建议服务 - 优化版（支持快速缓存响应）"""

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = InvestmentAdviceAnalyzer()
        self.cache = CacheManager("investment_advice", ttl=AI_ANALYSIS_CACHE_TTL)

    def get_investment_advice(
        self,
        market_status: str = "",
        bullish_factors: List[Dict] = None,
        bearish_factors: List[Dict] = None,
        institution_predictions: List[Dict] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        获取投资建议 - 快速响应版本（<50ms）

        优化策略：
        1. 优先从文件缓存读取（<10ms）
        2. 无缓存时返回默认数据并触发后台分析
        3. use_cache=False时直接执行 MiMo 分析

        Args:
            market_status: 市场状态
            bullish_factors: 看涨因子
            bearish_factors: 看跌因子
            institution_predictions: 机构预测
            use_cache: 是否使用缓存（默认True，立即返回缓存数据）

        Returns:
            投资建议分析结果
        """
        # 如果强制刷新，直接执行 MiMo 分析
        if not use_cache:
            logger.info("[InvestmentAdvice] 强制刷新，执行 MiMo 实时分析...")
            try:
                result = self.analyzer.analyze(
                    self.db,
                    market_status,
                    bullish_factors or [],
                    bearish_factors or [],
                    institution_predictions or []
                )
                self.cache.set(result)
                result["metadata"] = {
                    "cached": False,
                    "cache_source": "mimo_realtime",
                    "generated_at": timeutil.now_iso(),
                    "data_sources": ["实时金价数据", "市场因子分析", "机构预测", "24小时新闻"],
                    "analysis_method": "MiMo LLM 实时分析"
                }
                return result
            except Exception as e:
                logger.error(f"[InvestmentAdvice] MiMo 分析失败: {e}")
                # 如果分析失败，返回缓存数据
                pass
        
        # 1. 首先尝试文件缓存（最快，支持多进程共享）
        cached_data = self.cache.get()
        if cached_data:
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": timeutil.now_iso(),
                "data_sources": ["实时金价数据", "市场因子分析", "机构预测", "24小时新闻"],
                "analysis_method": "MiMo LLM 综合分析"
            }
            return cached_data

        # 2. 无缓存时，返回默认数据并触发后台更新
        #
        # 这里必须用 analyzer.get_default_advice()：它的结构与 analyze() 一致
        # （market_assessment / strategies / core_principles / risk_warning / disclaimer）。
        # 原实现调用的是 _get_default_response() —— 一份结构完全不同的历史遗留
        # （strategy / allocation / actions / expected_return），
        # 导致缓存未命中时接口返回的内容里有 4 个前端依赖的字段是 undefined：
        # 页面显示内置兜底策略、市场评估一片空白、免责声明消失。
        default_data = self.analyzer.get_default_advice()
        # analyzer 的默认值不带 metadata，这里补上 ——
        # 前端靠它判断「这是占位内容还是本次分析结果」。
        default_data["metadata"] = {
            "cached": False,
            "status": "analyzing",
            "message": "AI分析进行中，首次加载可能需要1-2分钟",
            "data_sources": ["实时金价数据", "市场因子分析", "机构预测", "24小时新闻"],
            "analysis_method": "MiMo LLM 综合分析",
        }
        
        # 触发后台分析
        self._trigger_background_analysis(
            market_status,
            bullish_factors or [],
            bearish_factors or [],
            institution_predictions or []
        )
        
        return default_data

    _ANALYSIS_KEY = "investment_advice"

    def _trigger_background_analysis(
        self,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict]
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
                institution_predictions
            )
        except Exception as e:
            single_flight.end(self._ANALYSIS_KEY)
            logger.error(f"[InvestmentAdvice] 触发后台分析失败: {e}")

    def _guarded_background_task(self, *args) -> None:
        """执行后台任务，结束后释放单飞占位。"""
        try:
            self._background_analysis_task(*args)
        finally:
            single_flight.end(self._ANALYSIS_KEY)


    def _background_analysis_task(
        self,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict]
    ) -> None:
        """后台分析任务"""
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                result = self.analyzer.analyze(
                    db,
                    market_status,
                    bullish_factors,
                    bearish_factors,
                    institution_predictions
                )
                # 更新文件缓存
                self.cache.set(result)
                logger.info(f"[InvestmentAdvice] 后台分析完成，时间: {timeutil.now()}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[InvestmentAdvice] 后台分析失败: {e}")

    def refresh_analysis_sync(
        self,
        market_status: str = "",
        bullish_factors: List[Dict] = None,
        bearish_factors: List[Dict] = None,
        institution_predictions: List[Dict] = None
    ) -> Dict[str, Any]:
        """同步刷新分析（阻塞，仅用于定时任务）。

        若同服务已有分析在跑（例如启动预热触发的后台任务），直接跳过 ——
        它产出的就是同一份结果，重复执行只是多花一次 LLM 费用。
        """
        if not single_flight.try_begin(self._ANALYSIS_KEY):
            logger.warning("[InvestmentAdvice] 已有分析在执行，跳过本次刷新")
            return self.cache.get() or {}
        try:
            result = self.analyzer.analyze(
                self.db,
                market_status,
                bullish_factors or [],
                bearish_factors or [],
                institution_predictions or []
            )
            self.cache.set(result)
            return result
        finally:
            single_flight.end(self._ANALYSIS_KEY)

    async def refresh_analysis_async(
        self,
        market_status: str = "",
        bullish_factors: List[Dict] = None,
        bearish_factors: List[Dict] = None,
        institution_predictions: List[Dict] = None
    ) -> Dict[str, Any]:
        """异步刷新分析（非阻塞）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            self.refresh_analysis_sync,
            market_status,
            bullish_factors,
            bearish_factors,
            institution_predictions
        )
