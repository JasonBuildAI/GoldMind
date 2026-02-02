"""市场分析 Agent"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class MarketAnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.prompt_template = """
你是一位专业的黄金市场分析师。请根据以下信息进行分析：

当前市场数据：
{market_data}

最新新闻：
{news}

请分析：
1. 当前市场的主要看涨因素
2. 当前市场的主要看跌因素
3. 价格走势预测
4. 投资建议

请以JSON格式返回分析结果，格式如下：
{{
    "bullish_factors": [
        {{
            "title": "因素标题",
            "subtitle": "副标题",
            "description": "详细描述",
            "details": ["要点1", "要点2"],
            "impact": "high/medium/low"
        }}
    ],
    "bearish_factors": [
        {{
            "title": "因素标题",
            "subtitle": "副标题",
            "description": "详细描述",
            "details": ["要点1", "要点2"],
            "impact": "high/medium/low"
        }}
    ],
    "prediction": {{
        "target_price": 5000,
        "timeframe": "2026年底",
        "confidence": 0.8,
        "reasoning": "预测理由"
    }},
    "advice": "投资建议"
}}
"""
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        market_data = input_data.get('market_data', {})
        news = input_data.get('news', [])
        
        news_text = "\n".join([f"- {n.get('title', '')}" for n in news[:10]])
        
        prompt = self.prompt_template.format(
            market_data=str(market_data),
            news=news_text
        )
        
        response = self.llm.invoke(prompt)
        
        import json
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            content = response.content
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != 0:
                result = json.loads(content[start:end])
            else:
                result = {
                    "bullish_factors": [],
                    "bearish_factors": [],
                    "prediction": None,
                    "advice": "分析失败"
                }
        
        return result
