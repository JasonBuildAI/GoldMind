"""投资建议分析服务 - 优化版（支持快速缓存响应）"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
import asyncio

from app.models.news import GoldNews
from app.models.gold_price import GoldPrice
from app.config import settings
from app.services.cache_manager import CacheManager
import json
import logging

logger = logging.getLogger(__name__)

# 延迟导入langchain_openai（避免启动时慢）
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


class InvestmentAdviceAnalyzer:
    """使用LangChain Agent分析市场数据，生成个性化投资建议"""

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

    def _fetch_recent_news(self, db: Session, hours: int = 24) -> List[GoldNews]:
        """获取最近的新闻"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return db.query(GoldNews).filter(
            GoldNews.created_at >= cutoff_time
        ).order_by(GoldNews.created_at.desc()).limit(20).all()

    def _fetch_latest_price(self, db: Session) -> Optional[GoldPrice]:
        """获取最新金价"""
        return db.query(GoldPrice).order_by(GoldPrice.date.desc()).first()

    def _fetch_recent_prices(self, db: Session, days: int = 10) -> List[GoldPrice]:
        """获取最近N天的价格数据"""
        cutoff_date = datetime.now() - timedelta(days=days)
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
        
        return {
            "current_price": 2800.0,
            "start_price": 2650.0,
            "ytd_change": 5.66,
            "period_high": 2800.0,
            "period_low": 2650.0,
            "volatility_range": 5.66
        }

    def _format_news(self, news_list: List[GoldNews]) -> str:
        """格式化新闻内容"""
        if not news_list:
            return "暂无新闻数据"
        
        formatted = []
        for news in news_list[:10]:
            formatted.append(f"- [{news.created_at.strftime('%Y-%m-%d %H:%M')}] {news.title}")
        return "\n".join(formatted)

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
            
            news_content = self._format_news(recent_news)
            prices_content = self._format_prices(recent_prices)
            bullish_content = json.dumps(bullish_factors, ensure_ascii=False, indent=2) if bullish_factors else "暂无数据"
            bearish_content = json.dumps(bearish_factors, ensure_ascii=False, indent=2) if bearish_factors else "暂无数据"
            institution_content = json.dumps(institution_predictions, ensure_ascii=False, indent=2) if institution_predictions else "暂无数据"
            
            prompt_template = f"""你是一位资深的黄金投资顾问，拥有20年以上的贵金属市场分析经验。你的投资风格偏向保守稳健，注重风险控制和长期价值投资。

你的任务是基于当前市场数据，为不同风险偏好的投资者生成具体、实用、保守的投资策略建议。

## 当前市场数据

### 1. 实时金价数据
- 当前金价: ${ytd_data['current_price']:.2f} 美元/盎司
- 2025年至今涨幅: {ytd_data['ytd_change']:+.2f}%
- 期间最高: ${ytd_data['period_high']:.2f}
- 期间最低: ${ytd_data['period_low']:.2f}
- 波动区间: {ytd_data['volatility_range']:.2f}%

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
                return self._get_default_advice()
                
        except Exception as e:
            logger.error(f"投资建议分析失败: {e}")
            return self._get_default_advice()

    def _get_default_advice(self) -> Dict[str, Any]:
        """获取默认投资建议"""
        return {
            "market_assessment": {
                "current_position": "当前市场数据不足，无法准确评估",
                "risk_level": "medium",
                "recommended_approach": "建议观望，等待更明确的市场信号",
                "key_considerations": ["关注美联储政策动向", "观察地缘政治风险变化", "监测美元指数走势"]
            },
            "strategies": [
                {
                    "type": "conservative",
                    "title": "保守配置策略",
                    "description": "适合风险厌恶型投资者，追求资产保值",
                    "allocation": "资产配置的5-10%",
                    "timeframe": "1-3年",
                    "risk_level": "low",
                    "entry_strategy": {
                        "current_price_assessment": "建议等待回调后再入场",
                        "recommended_entry_range": "等待金价回调至2700-2750美元区间",
                        "entry_timing": "分批建仓，每次回调5%时加仓",
                        "position_building": "分4批建仓，每批25%，间隔2-4周"
                    },
                    "exit_strategy": {
                        "profit_target": "年度收益目标8-12%",
                        "stop_loss": "单笔亏损不超过本金的5%",
                        "rebalancing_trigger": "金价涨幅超过20%时减仓一半"
                    },
                    "pros": ["风险可控，适合保守投资者", "无需频繁操作", "长期对冲通胀"],
                    "cons": ["短期收益有限", "资金占用时间长", "可能错过快速上涨机会"],
                    "suitable_for": ["风险厌恶型投资者", "长期资产配置者", "退休规划人群"],
                    "execution_steps": ["等待回调至目标区间", "分批建仓，控制仓位", "设置止盈止损", "定期评估调整"]
                },
                {
                    "type": "balanced",
                    "title": "均衡配置策略",
                    "description": "适合有一定经验的投资者，平衡风险与收益",
                    "allocation": "资产配置的8-12%",
                    "timeframe": "6-12个月",
                    "risk_level": "medium",
                    "entry_strategy": {
                        "current_price_assessment": "可小仓位试水",
                        "recommended_entry_range": "2750-2800美元区间",
                        "entry_timing": "分批建仓，结合技术指标",
                        "position_building": "分3批建仓，每批33%，根据技术信号调整"
                    },
                    "exit_strategy": {
                        "profit_target": "阶段收益目标15-20%",
                        "stop_loss": "单笔亏损不超过本金的8%",
                        "rebalancing_trigger": "达到目标收益或跌破关键支撑位"
                    },
                    "pros": ["灵活应对市场变化", "收益潜力较好", "风险相对可控"],
                    "cons": ["需要一定的市场判断能力", "需要关注市场动态", "可能面临短期波动"],
                    "suitable_for": ["有一定经验的投资者", "能承受中等波动的投资者", "有时间的投资者"],
                    "execution_steps": ["分析技术形态", "小仓位试探", "根据走势加仓或止损", "动态调整持仓"]
                },
                {
                    "type": "opportunistic",
                    "title": "机会型策略",
                    "description": "适合风险承受能力强的投资者，捕捉短期机会",
                    "allocation": "资产配置的3-5%（严格限制）",
                    "timeframe": "1-3个月",
                    "risk_level": "high",
                    "entry_strategy": {
                        "current_price_assessment": "仅适合极小部分资金参与",
                        "recommended_entry_range": "严格等待明确突破信号",
                        "entry_timing": "仅在关键技术位突破时",
                        "position_building": "单笔投入，严格止损"
                    },
                    "exit_strategy": {
                        "profit_target": "短期目标10-15%",
                        "stop_loss": "严格止损，亏损不超过5%",
                        "rebalancing_trigger": "达到目标或触发止损立即离场"
                    },
                    "pros": ["可能获得较高短期收益", "资金利用效率高"],
                    "cons": ["风险极高", "需要专业知识和经验", "容易受情绪影响", "可能快速亏损"],
                    "suitable_for": ["专业投资者", "风险承受能力极强", "有充足时间盯盘"],
                    "execution_steps": ["严格筛选入场时机", "小仓位参与", "设置严格止损", "及时止盈离场"]
                }
            ],
            "core_principles": [
                {"title": "风险管理", "description": "永远把风险控制放在第一位，不要投入无法承受损失的资金"},
                {"title": "仓位控制", "description": "黄金配置不超过总资产的15%，单品种不超过10%"},
                {"title": "再平衡", "description": "每季度评估一次，根据市场变化调整配置比例"},
                {"title": "长期视角", "description": "黄金适合长期配置，避免频繁交易"}
            ],
            "risk_warning": "黄金市场波动较大，投资有风险，入市需谨慎。以上建议仅供参考，不构成投资建议。",
            "disclaimer": "投资者应根据自身风险承受能力、投资目标和财务状况做出独立判断。过往表现不代表未来收益。"
        }


class InvestmentAdviceService:
    """投资建议服务 - 优化版（支持快速缓存响应）"""

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = InvestmentAdviceAnalyzer()
        self.cache = CacheManager("investment_advice", ttl=7200)  # 2小时缓存

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
        3. use_cache=False时直接执行DeepSeek分析

        Args:
            market_status: 市场状态
            bullish_factors: 看涨因子
            bearish_factors: 看跌因子
            institution_predictions: 机构预测
            use_cache: 是否使用缓存（默认True，立即返回缓存数据）

        Returns:
            投资建议分析结果
        """
        # 如果强制刷新，直接执行DeepSeek分析
        if not use_cache:
            print("[InvestmentAdvice] 强制刷新，执行DeepSeek实时分析...")
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
                    "cache_source": "deepseek_realtime",
                    "generated_at": datetime.now().isoformat(),
                    "data_sources": ["实时金价数据", "市场因子分析", "机构预测", "24小时新闻"],
                    "analysis_method": "LangChain Agent + DeepSeek LLM 实时分析"
                }
                return result
            except Exception as e:
                print(f"[InvestmentAdvice] DeepSeek分析失败: {e}")
                # 如果分析失败，返回缓存数据
                pass
        
        # 1. 首先尝试文件缓存（最快，支持多进程共享）
        cached_data = self.cache.get()
        if cached_data:
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": datetime.now().isoformat(),
                "data_sources": ["实时金价数据", "市场因子分析", "机构预测", "24小时新闻"],
                "analysis_method": "LangChain Agent + DeepSeek LLM"
            }
            return cached_data

        # 2. 无缓存时，返回默认数据并触发后台更新
        default_data = self._get_default_response()
        
        # 触发后台分析
        self._trigger_background_analysis(
            market_status,
            bullish_factors or [],
            bearish_factors or [],
            institution_predictions or []
        )
        
        return default_data

    def _get_default_response(self) -> Dict[str, Any]:
        """获取默认响应（用于无缓存时快速返回）"""
        return {
            "strategy": "保守型投资策略",
            "allocation": {
                "gold_etf": "30-40%",
                "physical_gold": "20-30%",
                "gold_stocks": "10-20%",
                "cash": "20-30%"
            },
            "actions": [
                {
                    "type": "buy",
                    "description": "在回调时分批买入黄金ETF",
                    "priority": "高"
                },
                {
                    "type": "hold",
                    "description": "持有现有黄金仓位，等待突破",
                    "priority": "中"
                },
                {
                    "type": "watch",
                    "description": "关注美联储政策动向和地缘政治风险",
                    "priority": "高"
                }
            ],
            "risk_warning": "黄金市场波动较大，建议控制仓位在总资产的30%以内",
            "time_horizon": "中长期（6-12个月）",
            "expected_return": "预期年化收益率8-15%",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "metadata": {
                "cached": False,
                "status": "analyzing",
                "message": "AI分析进行中，首次加载可能需要1-2分钟",
                "data_sources": ["实时金价数据", "市场因子分析", "机构预测", "24小时新闻"],
                "analysis_method": "LangChain Agent + DeepSeek LLM"
            }
        }

    def _trigger_background_analysis(
        self,
        market_status: str,
        bullish_factors: List[Dict],
        bearish_factors: List[Dict],
        institution_predictions: List[Dict]
    ) -> None:
        """触发后台分析（不阻塞）"""
        try:
            _executor.submit(
                self._background_analysis_task,
                market_status,
                bullish_factors,
                bearish_factors,
                institution_predictions
            )
        except Exception as e:
            print(f"[InvestmentAdvice] 触发后台分析失败: {e}")

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
                print(f"[InvestmentAdvice] 后台分析完成，时间: {datetime.now()}")
            finally:
                db.close()
        except Exception as e:
            print(f"[InvestmentAdvice] 后台分析失败: {e}")

    def refresh_analysis_sync(
        self,
        market_status: str = "",
        bullish_factors: List[Dict] = None,
        bearish_factors: List[Dict] = None,
        institution_predictions: List[Dict] = None
    ) -> Dict[str, Any]:
        """同步刷新分析（阻塞，仅用于手动刷新）"""
        result = self.analyzer.analyze(
            self.db,
            market_status,
            bullish_factors or [],
            bearish_factors or [],
            institution_predictions or []
        )
        self.cache.set(result)
        return result

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
