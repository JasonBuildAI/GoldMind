"""看涨因子分析服务 - 优化版（支持智谱AI实时搜索）"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from concurrent.futures import ThreadPoolExecutor
import asyncio
from functools import partial

from app.models.news import GoldNews
from app.models.analysis import MarketFactor, FactorType, ImpactLevel
from app.config import settings
from app.services.cache_manager import CacheManager
from app.services.zhipu_service import get_zhipu_service
import json

# 全局线程池（所有服务共享）
_executor = ThreadPoolExecutor(max_workers=4)

# 延迟导入langchain_openai（避免启动时慢）
ChatOpenAI = None

def _get_chat_openai():
    """延迟加载ChatOpenAI类"""
    global ChatOpenAI
    if ChatOpenAI is None:
        from langchain_openai import ChatOpenAI as _ChatOpenAI
        ChatOpenAI = _ChatOpenAI
    return ChatOpenAI


class BullishFactorAnalyzer:
    """使用智谱AI实时搜索分析黄金市场看涨因子"""
    
    def __init__(self):
        self._llm = None
        self.zhipu_service = get_zhipu_service()
        self.prompt_template = """你是一位专业的黄金市场分析师，专注于分析影响黄金价格上涨的因素。

当前金价数据：
- 当前价格: {current_price} 美元/盎司
- 今日涨跌: {price_change}%
- 2025年至今涨幅: {ytd_change}%

以下是从24小时内收集的黄金相关新闻资讯：
{news_content}

请根据以上新闻，分析当前黄金市场的看涨因素。你需要识别出5个最重要的看涨因子，每个因子应包含：

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
6. 如果没有相关新闻支撑某个因子，请基于当前市场常识合理推断
"""

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

    def fetch_recent_news(self, db: Session, hours: int = 24) -> List[GoldNews]:
        """获取最近24小时内的新闻"""
        since = datetime.now() - timedelta(hours=hours)
        return db.query(GoldNews).filter(
            and_(
                GoldNews.published_at >= since,
                GoldNews.published_at <= datetime.now()
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
                        'published_at': datetime.now()
                    })
            except Exception as e:
                print(f"获取 {source} 新闻失败: {e}")
        
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
        
        return {
            "current_price": 2800.00,
            "price_change": 0.5,
            "ytd_change": 15.0
        }
    
    def analyze(self, db: Session) -> Dict[str, Any]:
        """执行分析 - 使用智谱AI实时搜索"""
        # 使用智谱AI实时搜索获取最新看涨因素
        try:
            print("[BullishFactor] 使用智谱AI实时搜索看涨因素...")
            search_result = self._search_bullish_factors()
            
            # 检查搜索结果是否有效
            if search_result.get("bullish_factors") and len(search_result["bullish_factors"]) > 0:
                print(f"[BullishFactor] 成功获取 {len(search_result['bullish_factors'])} 个看涨因素")
                search_result["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                search_result["data_source"] = "智谱AI实时搜索"
                return search_result
            else:
                print("[BullishFactor] 搜索结果为空，使用备用方案")
                
        except Exception as e:
            print(f"[BullishFactor] 智谱AI搜索失败: {e}")
        
        # 备用方案：使用传统方式分析
        return self._analyze_with_traditional_llm(db)
    
    def _search_bullish_factors(self) -> Dict[str, Any]:
        """使用智谱AI搜索看涨因素"""
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
        
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=settings.ZHIPU_API_KEY,
                base_url=settings.ZHIPU_BASE_URL
            )
            
            response = client.chat.completions.create(
                model=settings.ZHIPU_MODEL,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                tools=[{
                    "type": "web_search",
                    "web_search": {
                        "enable": True,
                        "search_result": True
                    }
                }],
                temperature=0.3,
                max_tokens=4096
            )
            
            content = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 清理可能的markdown代码块
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                result = json.loads(content.strip())
                return result
            except json.JSONDecodeError:
                # 尝试从文本中提取JSON
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end > start:
                    try:
                        result = json.loads(content[start:end])
                        return result
                    except:
                        pass
                
                return {
                    "bullish_factors": [],
                    "analysis_summary": "解析失败",
                    "raw_content": content
                }
                
        except Exception as e:
            print(f"搜索看涨因素失败: {e}")
            return {
                "bullish_factors": [],
                "analysis_summary": f"搜索失败: {str(e)}"
            }
    
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
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt = self.prompt_template.format(
            current_price=gold_data["current_price"],
            price_change=gold_data["price_change"],
            ytd_change=gold_data["ytd_change"],
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
            print(f"LLM调用失败: {e}")
            return self._get_default_factors()
    
    def _get_default_factors(self) -> Dict[str, Any]:
        """获取默认看涨因子（当LLM调用失败时使用）"""
        return {
            "bullish_factors": [
                {
                    "id": "fed-policy",
                    "title": "美联储降息周期",
                    "subtitle": "货币政策转向宽松",
                    "description": "美联储持续降息推动实际利率下行，黄金作为非孳息资产的吸引力增强。",
                    "details": [
                        "美联储维持宽松货币政策",
                        "实际利率处于低位",
                        "市场预期继续降息",
                        "持有黄金机会成本降低"
                    ],
                    "impact": "high"
                },
                {
                    "id": "central-bank",
                    "title": "全球央行持续购金",
                    "subtitle": "去美元化趋势加速",
                    "description": "全球央行持续增持黄金储备，推动黄金需求增长。",
                    "details": [
                        "新兴市场央行大幅增持",
                        "储备多元化需求强劲",
                        "年度购金量创新高",
                        "长期支撑金价走势"
                    ],
                    "impact": "high"
                },
                {
                    "id": "dollar-credit",
                    "title": "美元信用动摇",
                    "subtitle": "美债规模持续攀升",
                    "description": "美国债务规模不断扩大，市场对美元信用产生担忧。",
                    "details": [
                        "美债规模突破历史新高",
                        "债务占GDP比重上升",
                        "财政可持续性受质疑",
                        "避险资金流入黄金"
                    ],
                    "impact": "high"
                },
                {
                    "id": "geopolitical",
                    "title": "地缘政治风险",
                    "subtitle": "避险需求持续升温",
                    "description": "全球地缘政治局势紧张，推动避险资金流入黄金市场。",
                    "details": [
                        "地区冲突持续",
                        "贸易摩擦加剧",
                        "政治不确定性增加",
                        "避险需求支撑金价"
                    ],
                    "impact": "medium"
                },
                {
                    "id": "supply-demand",
                    "title": "供需失衡支撑",
                    "subtitle": "矿产金产量见顶",
                    "description": "黄金供应增长受限，而需求持续强劲，供需缺口支撑价格。",
                    "details": [
                        "矿产金产量增长缓慢",
                        "生产成本持续上升",
                        "投资需求保持旺盛",
                        "供需基本面偏紧"
                    ],
                    "impact": "medium"
                }
            ],
            "analysis_summary": "基于当前市场状况的综合分析",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                existing.updated_at = datetime.now()
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
        self.cache = CacheManager("bullish_factors", ttl=7200)  # 2小时缓存
    
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
            print("[BullishFactor] 强制刷新，执行实时搜索...")
            try:
                result = self.analyzer.analyze(self.db)
                self.analyzer.save_to_database(self.db, result)
                self.cache.set(result)
                result["metadata"] = {
                    "cached": False,
                    "cache_source": "realtime_search",
                    "generated_at": datetime.now().isoformat(),
                    "message": "基于智谱AI实时搜索的最新数据"
                }
                return result
            except Exception as e:
                print(f"[BullishFactor] 实时搜索失败: {e}")
                # 如果实时搜索失败，返回缓存数据
                pass
        
        # 1. 首先尝试缓存（支持多进程共享）
        cached_data = self.cache.get()
        if cached_data:
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": datetime.now().isoformat()
            }
            return cached_data
        
        # 2. 无缓存时，直接返回默认数据并触发后台更新
        default_data = self._get_default_response()
        
        # 触发后台分析
        self._trigger_background_analysis()
        
        return default_data
    
    def _get_default_response(self) -> Dict[str, Any]:
        """获取默认响应（用于无缓存时快速返回）"""
        return {
            "bullish_factors": self.analyzer._get_default_factors()["bullish_factors"],
            "analysis_summary": "正在分析最新数据，请稍后刷新查看AI分析结果",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "metadata": {
                "cached": False,
                "status": "analyzing",
                "message": "AI分析进行中，首次加载可能需要1-2分钟"
            }
        }
    
    def _trigger_background_analysis(self) -> None:
        """触发后台分析（不阻塞）"""
        try:
            # 提交到线程池执行
            _executor.submit(self._background_analysis_task)
        except Exception as e:
            print(f"[BullishFactor] 触发后台分析失败: {e}")

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
                print(f"[BullishFactor] 后台分析完成，时间: {datetime.now()}")
            finally:
                db.close()
        except Exception as e:
            print(f"[BullishFactor] 后台分析失败: {e}")

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
        """同步刷新分析（阻塞，仅用于定时任务）"""
        result = self.analyzer.analyze(self.db)
        self.analyzer.save_to_database(self.db, result)
        self.cache.set(result)
        return result
    
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
