"""机构预测分析服务"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from concurrent.futures import ThreadPoolExecutor
import asyncio

from app.models.news import GoldNews
from app.models.analysis import InstitutionView
from app.config import settings
from app.services.cache_manager import CacheManager
from app.services.zhipu_service import get_zhipu_service
import json

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


class InstitutionPredictionAnalyzer:
    """使用智谱AI实时搜索抓取四大机构最新预测"""

    def __init__(self):
        self._llm = None
        self.zhipu_service = get_zhipu_service()
        self.prompt_template = """你是一位专业的金融市场数据分析师，专注于追踪华尔街顶级投行对黄金价格的最新预测。

你的任务是搜索并整理以下四家主流机构对黄金的最新预测：
1. 高盛 (Goldman Sachs)
2. 瑞银 (UBS)
3. 摩根士丹利 (Morgan Stanley)
4. 花旗 (Citi)

以下是从24小时内收集的黄金相关新闻资讯：
{news_content}

请根据以上新闻，提取或推断这四家机构的最新黄金预测。对于每家机构，请提供：

1. **目标价格** - 具体的美元价格（数字）
2. **时间框架** - 如"2026年底"、"2026年9月"、"2026年中"、"长期展望"等
3. **评级** - bullish(看涨) / bearish(看跌) / neutral(中性)
4. **核心理由** - 一句话总结该机构的主要观点
5. **关键要点** - 4个支撑该预测的核心论据

请严格按照以下JSON格式返回分析结果：

{{
    "institutions": [
        {{
            "name": "高盛 (Goldman Sachs)",
            "logo": "GS",
            "rating": "bullish",
            "target_price": 5400,
            "timeframe": "2026年底",
            "reasoning": "坚定看涨，将目标价从4900美元上调至5400美元",
            "key_points": [
                "私人投资者与央行需求持续增长",
                "结构性买盘（央行、ETF）提供坚实支撑",
                "预计2026年央行月均购金70吨",
                "美联储降息周期将推动金价上行"
            ]
        }},
        {{
            "name": "瑞银 (UBS)",
            "logo": "UBS",
            "rating": "bullish",
            "target_price": 5000,
            "timeframe": "2026年9月",
            "reasoning": "预计上半年触及5000美元，长期看好",
            "key_points": [
                "去美元化需求支撑长期金价",
                "地缘政治不确定性持续",
                "上半年或触及5000美元关口",
                "美联储降息趋缓后可能小幅回落"
            ]
        }},
        {{
            "name": "摩根士丹利 (Morgan Stanley)",
            "logo": "MS",
            "rating": "neutral",
            "target_price": 4500,
            "timeframe": "2026年中",
            "reasoning": "预计降息推迟至年中，短期震荡",
            "key_points": [
                "美国强劲消费推迟降息时点",
                "预计6月和9月降息",
                "关税传导效应支撑通胀",
                "上半年美元可能维持强势"
            ]
        }},
        {{
            "name": "花旗 (Citi)",
            "logo": "C",
            "rating": "bearish",
            "target_price": 2700,
            "timeframe": "长期展望",
            "reasoning": "若美国经济回到'金发女孩'状态，金价可能回落",
            "key_points": [
                "2026年美国经济或回归适中成长",
                "避险需求将随之减弱",
                "基准预测与牛市观点相反",
                "短期曾上调目标至4000美元"
            ]
        }}
    ],
    "analysis_summary": "基于24小时新闻的机构预测汇总",
    "last_updated": "{current_time}"
}}

注意事项：
1. 必须返回有效的JSON格式
2. rating只能是：bullish, bearish, neutral
3. target_price必须是数字（美元）
4. 如果新闻中没有某家机构的最新预测，请基于该机构历史观点和市场常识合理推断
5. key_points数组必须包含4个具体要点
6. 确保四家机构都有数据
"""

    @property
    def llm(self):
        """延迟创建LLM实例"""
        if self._llm is None:
            ChatOpenAIClass = _get_chat_openai()
            self._llm = ChatOpenAIClass(
                model="deepseek-chat",
                openai_api_key=settings.DEEPSEEK_API_KEY,
                openai_api_base=settings.DEEPSEEK_BASE_URL,
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

    def analyze(self, db: Session) -> Dict[str, Any]:
        """执行分析 - 使用智谱AI实时搜索"""
        # 使用智谱AI实时搜索获取最新机构预测
        try:
            print("[InstitutionPrediction] 使用智谱AI实时搜索机构预测...")
            search_result = self.zhipu_service.search_institution_predictions()
            
            # 检查搜索结果是否有效
            if search_result.get("institutions") and len(search_result["institutions"]) > 0:
                print(f"[InstitutionPrediction] 成功获取 {len(search_result['institutions'])} 家机构预测")
                search_result["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                search_result["data_source"] = "智谱AI实时搜索"
                return search_result
            else:
                print("[InstitutionPrediction] 搜索结果为空，使用备用方案")
                
        except Exception as e:
            print(f"[InstitutionPrediction] 智谱AI搜索失败: {e}")
        
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

        # 2. 构建prompt并调用LLM
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                        result = self._get_default_predictions()
                else:
                    result = self._get_default_predictions()

            return result
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return self._get_default_predictions()

    def _get_default_predictions(self) -> Dict[str, Any]:
        """获取默认机构预测（当LLM调用失败时使用）"""
        return {
            "institutions": [
                {
                    "name": "高盛 (Goldman Sachs)",
                    "logo": "GS",
                    "rating": "bullish",
                    "target_price": 5400,
                    "timeframe": "2026年底",
                    "reasoning": "坚定看涨，将目标价从4900美元上调至5400美元",
                    "key_points": [
                        "私人投资者与央行需求持续增长",
                        "结构性买盘（央行、ETF）提供坚实支撑",
                        "预计2026年央行月均购金70吨",
                        "美联储降息周期将推动金价上行"
                    ]
                },
                {
                    "name": "瑞银 (UBS)",
                    "logo": "UBS",
                    "rating": "bullish",
                    "target_price": 5000,
                    "timeframe": "2026年9月",
                    "reasoning": "预计上半年触及5000美元，长期看好",
                    "key_points": [
                        "去美元化需求支撑长期金价",
                        "地缘政治不确定性持续",
                        "上半年或触及5000美元关口",
                        "美联储降息趋缓后可能小幅回落"
                    ]
                },
                {
                    "name": "摩根士丹利 (Morgan Stanley)",
                    "logo": "MS",
                    "rating": "neutral",
                    "target_price": 4500,
                    "timeframe": "2026年中",
                    "reasoning": "预计降息推迟至年中，短期震荡",
                    "key_points": [
                        "美国强劲消费推迟降息时点",
                        "预计6月和9月降息",
                        "关税传导效应支撑通胀",
                        "上半年美元可能维持强势"
                    ]
                },
                {
                    "name": "花旗 (Citi)",
                    "logo": "C",
                    "rating": "bearish",
                    "target_price": 2700,
                    "timeframe": "长期展望",
                    "reasoning": "若美国经济回到'金发女孩'状态，金价可能回落",
                    "key_points": [
                        "2026年美国经济或回归适中成长",
                        "避险需求将随之减弱",
                        "基准预测与牛市观点相反",
                        "短期曾上调目标至4000美元"
                    ]
                }
            ],
            "analysis_summary": "基于当前市场状况的机构预测汇总",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def save_to_database(self, db: Session, analysis_result: Dict[str, Any]) -> None:
        """将分析结果保存到数据库"""
        institutions = analysis_result.get("institutions", [])

        for inst_data in institutions:
            # 检查是否已存在相同机构的预测
            existing = db.query(InstitutionView).filter(
                InstitutionView.institution_name == inst_data["name"]
            ).first()

            if existing:
                # 更新现有记录
                existing.rating = inst_data.get("rating", "neutral")
                existing.target_price = inst_data.get("target_price", 0)
                existing.timeframe = inst_data.get("timeframe", "")
                existing.reasoning = inst_data.get("reasoning", "")
                existing.key_points = inst_data.get("key_points", [])
                existing.updated_at = datetime.now()
            else:
                # 创建新记录
                new_view = InstitutionView(
                    institution_name=inst_data["name"],
                    logo=inst_data.get("logo", ""),
                    rating=inst_data.get("rating", "neutral"),
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
        self.cache = CacheManager("institution_predictions", ttl=3600)  # 1小时缓存（实时数据更频繁更新）
        self.zhipu_service = get_zhipu_service()

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
            print("[InstitutionPrediction] 强制刷新，执行实时搜索...")
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
                print(f"[InstitutionPrediction] 实时搜索失败: {e}")
                # 如果实时搜索失败，返回缓存数据
                pass
        
        # 1. 首先尝试文件缓存（最快，支持多进程共享）
        cached_data = self.cache.get()
        if cached_data:
            cached_data["metadata"] = {
                "cached": True,
                "cache_source": "file",
                "generated_at": datetime.now().isoformat()
            }
            return cached_data

        # 2. 检查数据库中是否有最近2小时内的数据
        two_hours_ago = datetime.now() - timedelta(hours=2)
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
                "last_updated": recent_views[0].updated_at.strftime("%Y-%m-%d %H:%M:%S") if recent_views else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "metadata": {
                    "cached": True,
                    "cache_source": "database",
                    "generated_at": datetime.now().isoformat()
                }
            }
            # 更新文件缓存
            self.cache.set(result)
            return result

        # 3. 无缓存时，返回默认数据并触发后台更新
        default_data = self._get_default_response()
        self._trigger_background_analysis()
        return default_data

    def _get_default_response(self) -> Dict[str, Any]:
        """获取默认响应（用于无缓存时快速返回）"""
        return {
            "institutions": [
                {
                    "name": "高盛 (Goldman Sachs)",
                    "logo": "GS",
                    "rating": "看涨",
                    "target_price": "2,800-3,000美元",
                    "timeframe": "12个月",
                    "reasoning": "美联储降息周期和央行购金需求将支撑金价上涨",
                    "key_points": ["降息预期", "央行购金", "避险需求"]
                },
                {
                    "name": "瑞银 (UBS)",
                    "logo": "UBS",
                    "rating": "看涨",
                    "target_price": "2,900美元",
                    "timeframe": "2025年底",
                    "reasoning": "地缘政治风险和美元走弱利好黄金",
                    "key_points": ["地缘风险", "美元走弱", "投资需求"]
                },
                {
                    "name": "摩根士丹利 (Morgan Stanley)",
                    "logo": "MS",
                    "rating": "中性偏涨",
                    "target_price": "2,750美元",
                    "timeframe": "6个月",
                    "reasoning": "实际利率下行支撑金价，但需关注美元走势",
                    "key_points": ["实际利率", "美元走势", "通胀预期"]
                },
                {
                    "name": "花旗 (Citi)",
                    "logo": "C",
                    "rating": "看涨",
                    "target_price": "3,000美元",
                    "timeframe": "2025年中",
                    "reasoning": "美国债务问题和货币贬值担忧推动黄金需求",
                    "key_points": ["债务问题", "货币贬值", "避险资产"]
                }
            ],
            "analysis_summary": "正在分析最新机构预测数据，请稍后刷新查看AI分析结果",
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
            _executor.submit(self._background_analysis_task)
        except Exception as e:
            print(f"[InstitutionPrediction] 触发后台分析失败: {e}")

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
                print(f"[InstitutionPrediction] 后台分析完成，时间: {datetime.now()}")
            finally:
                db.close()
        except Exception as e:
            print(f"[InstitutionPrediction] 后台分析失败: {e}")

    def refresh_analysis_sync(self) -> Dict[str, Any]:
        """同步刷新分析（阻塞，仅用于手动刷新）"""
        result = self.analyzer.analyze(self.db)
        self.analyzer.save_to_database(self.db, result)
        self.cache.set(result)
        return result

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
