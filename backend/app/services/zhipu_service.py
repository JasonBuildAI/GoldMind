"""智谱AI服务 - 用于实时搜索和数据获取"""
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from app.config import settings


class ZhipuService:
    """智谱AI服务类 - 支持Web Search功能"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.ZHIPU_API_KEY,
            base_url=settings.ZHIPU_BASE_URL
        )
        self.model = settings.ZHIPU_MODEL
    
    def search_institution_predictions(self) -> Dict[str, Any]:
        """
        搜索四大机构对黄金的最新预测
        
        Returns:
            包含机构预测数据的字典
        """
        prompt = """请搜索并整理以下四家主流机构对黄金价格的最新预测：
1. 高盛 (Goldman Sachs)
2. 瑞银 (UBS)  
3. 摩根士丹利 (Morgan Stanley)
4. 花旗 (Citi)

请搜索2026年最新的机构预测报告和分析师观点，对于每家机构提供：
- 目标价格（美元）
- 时间框架（如2026年底、2026年中、2026年Q3等）
- 评级（看涨/看跌/中性）
- 核心理由（一句话总结）
- 关键要点（4个支撑论据）

请严格按照以下JSON格式返回：

{
    "institutions": [
        {
            "name": "高盛 (Goldman Sachs)",
            "logo": "GS",
            "rating": "bullish",
            "target_price": 5400,
            "timeframe": "2026年底",
            "reasoning": "...",
            "key_points": ["...", "...", "...", "..."]
        }
    ],
    "analysis_summary": "基于实时搜索的机构预测汇总",
    "search_time": "2026-02-01"
}

注意：
1. 必须返回有效的JSON格式
2. target_price必须是数字
3. rating只能是：bullish, bearish, neutral
4. 确保四家机构都有数据
5. 如果某家机构没有最新预测，请标注"暂无最新预测"
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
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
                # 如果解析失败，返回原始内容包装
                return {
                    "institutions": [],
                    "analysis_summary": "搜索完成但解析失败",
                    "raw_content": content,
                    "search_time": "2026-02-01"
                }
                
        except Exception as e:
            print(f"智谱AI搜索失败: {e}")
            return {
                "institutions": [],
                "analysis_summary": f"搜索失败: {str(e)}",
                "search_time": "2026-02-01"
            }
    
    def search_gold_news(self, query: str = "黄金价格走势 2026") -> str:
        """
        搜索黄金相关新闻
        
        Args:
            query: 搜索关键词
            
        Returns:
            搜索结果的文本摘要
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": f"搜索关于'{query}'的最新新闻，并总结关键信息"
                }],
                tools=[{
                    "type": "web_search",
                    "web_search": {
                        "enable": True,
                        "search_result": True
                    }
                }],
                temperature=0.5,
                max_tokens=2048
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"新闻搜索失败: {e}")
            return f"搜索失败: {str(e)}"


# 单例模式
_zhipu_service: Optional[ZhipuService] = None


def get_zhipu_service() -> ZhipuService:
    """获取智谱AI服务实例"""
    global _zhipu_service
    if _zhipu_service is None:
        _zhipu_service = ZhipuService()
    return _zhipu_service
