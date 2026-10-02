"""投资建议分析服务 - 优化版（支持快速缓存响应）"""
from typing import List, Dict, Any, Optional
from datetime import timedelta
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
import asyncio

from app.services.news_service import NEWS_PROMPT_LIMIT, format_news_for_prompt
from app.services.analysis_input import CAPABILITY_NOTE, load_analysis_news
from app.utils import timeutil
from app.models.gold_price import GoldPrice
from app.config import settings
from app.services import llm_gate
from app.services.cache_manager import CacheManager, AI_ANALYSIS_CACHE_TTL
from app.services.single_flight import single_flight
from app.services.institution_prediction_service import usable_institution_predictions
from app.services.llm_provider import (
    describe_completion,
    get_chat_llm,
    invoke_with_retries,
)
import json
import logging
from loguru import logger

logger = logging.getLogger(__name__)

# 全局线程池
_executor = ThreadPoolExecutor(max_workers=2)


# 输入指纹门控的键：必须与 Service._ANALYSIS_KEY 一致（守卫逐对断言）。
GATE_KEY = "investment_advice"


class InvestmentAdviceAnalyzer:
    """使用LangChain Agent分析市场数据，生成个性化投资建议"""

    def __init__(self):
        self._llm = None
        # 输入未变时跳过重算、直接复用 Service 写的同一份缓存（同 key、同 TTL）。
        self.cache = CacheManager(GATE_KEY, ttl=AI_ANALYSIS_CACHE_TTL)

    @property
    def llm(self):
        """延迟创建 LLM 实例（供应商由 llm_provider 工厂统一决定）"""
        if self._llm is None:
            self._llm = get_chat_llm(temperature=0.7)
        return self._llm

    def _fetch_recent_news(self, db: Session, hours: int = 24) -> List[Dict]:
        """最近 N 小时的统一分析新闻输入（消息板块 + gold_news，去重合并）。

        历史：原实现按 `created_at`（入库时刻）过滤与排序，窗口与顺序都不对；
        后来统一走 `NewsService.get_recent_news()`（按发布时刻）。2026-10-02
        起再进一步：与消息板块的高权威条目合并
        （`analysis_input.load_analysis_news`），央行 / 通讯社的消息首次进入
        这条链路。最多取 20 条，最终进 prompt 的条数由 NEWS_PROMPT_LIMIT 管。
        """
        return load_analysis_news(db, hours=hours, limit=20)

    def _fetch_recent_prices(self, db: Session, days: int = 10) -> List[GoldPrice]:
        """获取最近N天的价格数据"""
        cutoff_date = timeutil.now_naive() - timedelta(days=days)
        return db.query(GoldPrice).filter(
            GoldPrice.date >= cutoff_date
        ).order_by(GoldPrice.date.desc()).limit(days).all()

    def _fetch_window_data(self, db: Session):
        """按**滚动 12 个月**取价格统计（口径的唯一实现在 price_window）。

        原实现写死 ``datetime(2025, 1, 1)``：进入 2026 年后，所谓「年内涨幅」
        实际是最近 21 个月的涨幅，被当成事实写进 prompt。窗口现在锚定在数据里
        最新的一条价格上，跨年不失效；数据不足 12 个月时如实标注实际长度。
        没有行情数据时返回 None（不造数）。
        """
        from app.services.price_window import compute_price_window

        window = compute_price_window(db)
        if window is None:
            logger.warning("[InvestmentAdvice] 数据库里没有可用金价，prompt 中标注为暂无数据")
        return window

    @staticmethod
    def _format_window_block(window) -> str:
        """把窗口统计拼成 prompt 里的一段。涨跌幅与高低振幅分名，禁止混用。"""
        return (
            f"- 当前金价（最新收盘）: ${window.end_price:.2f} 美元/盎司\n"
            f"- {window.label}涨跌（首尾收盘比较，{window.window_start.isoformat()} 至 "
            f"{window.window_end.isoformat()}）: {window.change_pct:+.2f}%\n"
            f"- 期间最高: ${window.high:.2f}（{window.high_date.isoformat()}）\n"
            f"- 期间最低: ${window.low:.2f}（{window.low_date.isoformat()}）\n"
            f"- 高低振幅: {window.amplitude_pct:.2f}%（(最高−最低)/最低，非波动率、非年化）"
        )

    def _format_news(self, news_list: List[Dict]) -> str:
        """格式化新闻内容。

        统一走 `news_service.format_news_for_prompt` —— 这里原先自己拼一份，
        用的是 `created_at`（入库时刻）而不是 `published_at`（发布时刻）。
        """
        return format_news_for_prompt(news_list, limit=NEWS_PROMPT_LIMIT)

    def _format_prices(self, prices: List[GoldPrice]) -> str:
        """格式化价格数据"""
        if not prices:
            return "暂无价格数据"
        
        formatted = []
        for price in prices:
            formatted.append(f"- {price.date.strftime('%Y-%m-%d')}: ${price.close_price:.2f}")
        return "\n".join(formatted)

    def has_analyzable_inputs(
        self,
        db: Session,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict],
    ) -> bool:
        """是否存在任何值得分析的输入。

        四类输入（多空因子 / 可核实机构预测 / 近期新闻）全空时，LLM 没有任何
        依据可依 —— 调用它只会得到编造的策略与点位。此时整条链路直接降级。
        """
        if bullish_factors or bearish_factors:
            return True
        if usable_institution_predictions(institution_predictions):
            return True
        return bool(self._fetch_recent_news(db))

    def insufficient_data_advice(self, window) -> Dict[str, Any]:
        """降级结果：只给行情统计与「数据不足」说明，不给任何策略与点位。"""
        snapshot = None
        if window is not None:
            snapshot = {
                "label": window.label,
                "window_start": window.window_start.isoformat(),
                "window_end": window.window_end.isoformat(),
                "latest_price": round(window.end_price, 2),
                "change_pct": round(window.change_pct, 2),
                "high": round(window.high, 2),
                "low": round(window.low, 2),
                "amplitude_pct": round(window.amplitude_pct, 2),
                "full_window": window.full_window,
            }
        detail = (
            "当前没有可分析的数据输入（多空因子 / 可核实机构预测 / 近期新闻均为空），"
            "因此不生成任何策略与点位建议，也不调用模型。"
        )
        return {
            "analysis_status": "insufficient_data",
            "market_assessment": {},
            "strategies": [],
            "core_principles": [],
            "risk_warning": detail,
            "disclaimer": "行情统计不构成投资建议。",
            "price_snapshot": snapshot,
        }

    def analyze(
        self,
        db: Session,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict],
        *,
        force: bool = False,
    ) -> Dict[str, Any]:
        """分析市场数据并生成投资建议。

        `force=True`（用户显式刷新）跳过输入指纹门控。
        """
        try:
            recent_news = self._fetch_recent_news(db)
            window = self._fetch_window_data(db)
            recent_prices = self._fetch_recent_prices(db)
            
            price_block = (
                self._format_window_block(window)
            ) if window else "暂无行情数据（数据库里没有可用的金价记录）"

            news_content = self._format_news(recent_news)
            prices_content = self._format_prices(recent_prices)

            if not (
                bullish_factors
                or bearish_factors
                or usable_institution_predictions(institution_predictions)
                or recent_news
            ):
                logger.info("[InvestmentAdvice] 缺少可分析输入，跳过 LLM，返回数据不足说明")
                return self.insufficient_data_advice(window)

            bullish_content = json.dumps(bullish_factors, ensure_ascii=False, indent=2) if bullish_factors else "暂无数据"
            bearish_content = json.dumps(bearish_factors, ensure_ascii=False, indent=2) if bearish_factors else "暂无数据"
            usable_institutions = usable_institution_predictions(institution_predictions)
            institution_content = json.dumps(usable_institutions, ensure_ascii=False, indent=2) if usable_institutions else "暂无数据"
            
            prompt_template = f"""你是一位资深的黄金投资顾问，拥有20年以上的贵金属市场分析经验。你的投资风格偏向保守稳健，注重风险控制和长期价值投资。

{CAPABILITY_NOTE}

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
2. **具体可操作** - 在数据支持的前提下给出配置比例与点位；数据不足时如实说明
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
3. 入场价位区间只能来自数据可支持的位置；数据不足时如实写「数据不足，无法给出区间」，不得为了满足格式编造精确数字
4. 止盈 / 止损同理：给不出可靠依据时如实说明，不得编造
5. 风险提示要充分且具体"""
            
            # 输入指纹门控（2.0.2 第 19 条）：该 prompt 全部由数据组成，
            # 没有逐次易变的时间戳，因此 volatile 为空。
            fingerprint = llm_gate.prompt_fingerprint(prompt_template)
            if not force:
                skipped = llm_gate.gate.skip_if_unchanged(
                    GATE_KEY, fingerprint, self.cache
                )
                if skipped is not None:
                    return skipped

            response = invoke_with_retries(self.llm, prompt_template)
            
            try:
                content = response.content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content.strip()
                
                result = json.loads(json_str)
                # 只有真正调用并解析成功才记录指纹：失败路径下次仍要重试。
                llm_gate.gate.record(GATE_KEY, fingerprint)
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {e}（{describe_completion(response)}）")
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

    def _build_metadata(
        self, result: Dict[str, Any], *, cached: bool, cache_source: str
    ) -> Dict[str, Any]:
        """统一的 metadata 装配；降级结果如实标注 insufficient_data。

        否则前端只能看到空数组，会把「数据不足」错报成「暂不可用」。
        """
        if result.get("analysis_status") == "insufficient_data":
            return {
                "cached": cached,
                "status": "insufficient_data",
                "cache_source": "insufficient_data",
                "message": result.get("risk_warning") or "",
                "generated_at": timeutil.now_iso(),
                "data_sources": ["行情统计"],
                "analysis_method": "确定性降级（未调用 LLM）",
            }
        return {
            "cached": cached,
            "cache_source": cache_source,
            "generated_at": timeutil.now_iso(),
            "data_sources": ["实时金价数据", "市场因子分析", "机构预测", "24小时新闻"],
            "analysis_method": "LLM 实时分析" if cache_source == "llm_realtime" else "LLM 综合分析",
        }

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
        3. use_cache=False时直接执行实时 LLM 分析

        Args:
            market_status: 市场状态
            bullish_factors: 看涨因子
            bearish_factors: 看跌因子
            institution_predictions: 机构预测
            use_cache: 是否使用缓存（默认True，立即返回缓存数据）

        Returns:
            投资建议分析结果
        """
        # 降级语义：四类输入全空时不调 LLM、不读旧缓存 —— 没有任何依据时，
        # 模型能给出的只有编造；此时只返回行情统计 +「数据不足」说明。
        if not self.analyzer.has_analyzable_inputs(
            self.db,
            bullish_factors or [],
            bearish_factors or [],
            institution_predictions or [],
        ):
            logger.info("[InvestmentAdvice] 缺少可分析输入，跳过 LLM，返回数据不足说明")
            degraded = self.analyzer.insufficient_data_advice(
                self.analyzer._fetch_window_data(self.db)
            )
            degraded["metadata"] = self._build_metadata(
                degraded, cached=False, cache_source="insufficient_data"
            )
            return degraded

        # 如果强制刷新，直接执行实时 LLM 分析
        if not use_cache:
            logger.info("[InvestmentAdvice] 强制刷新，执行实时 LLM 分析...")
            try:
                result = self.analyzer.analyze(
                    self.db,
                    market_status,
                    bullish_factors or [],
                    bearish_factors or [],
                    institution_predictions or [],
                    force=True,
                )
                self.cache.set(result)
                result["metadata"] = self._build_metadata(
                    result, cached=False, cache_source="llm_realtime"
                )
                return result
            except Exception as e:
                logger.error(f"[InvestmentAdvice] 实时分析失败: {e}")
                # 如果分析失败，返回缓存数据
                pass
        
        # 1. 首先尝试文件缓存（最快，支持多进程共享）
        cached_data = self.cache.get()
        if cached_data:
            cached_data["metadata"] = self._build_metadata(
                cached_data, cached=True, cache_source="file"
            )
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
            "analysis_method": "LLM 综合分析",
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
        institution_predictions: List[Dict],
        force: bool = False
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
                force
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
        institution_predictions: List[Dict],
        force: bool = False
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
                    institution_predictions,
                    force=force,
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
        institution_predictions: List[Dict] = None,
        *,
        force: bool = False
    ) -> Dict[str, Any]:
        """同步刷新分析（阻塞，仅用于定时任务）。

        若同服务已有分析在跑（例如启动预热触发的后台任务），直接跳过 ——
        它产出的就是同一份结果，重复执行只是多花一次 LLM 费用。
        默认受输入指纹门控：输入没变就不重算（force=True 可绕过）。
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
                institution_predictions or [],
                force=force,
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
        institution_predictions: List[Dict] = None,
        *,
        force: bool = True
    ) -> Dict[str, Any]:
        """异步刷新分析 —— 用户显式刷新（POST /refresh），默认不受指纹门控限制。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor,
            partial(self.refresh_analysis_sync, force=force),
            market_status,
            bullish_factors,
            bearish_factors,
            institution_predictions
        )
