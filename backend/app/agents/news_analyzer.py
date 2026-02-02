"""新闻分析 Agent"""
from typing import Dict, Any
from app.agents.base import BaseAgent


class NewsAnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.prompt_template = """
你是一位金融新闻分析师。请分析以下黄金相关新闻的情感和重要性：

{news_list}

请对每条新闻进行分析，以JSON格式返回：
[
    {{
        "title": "新闻标题",
        "sentiment": "positive/negative/neutral",
        "importance": "high/medium/low",
        "keywords": ["关键词1", "关键词2"],
        "impact_summary": "对黄金市场的影响概述"
    }}
]
"""
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        news_list = input_data.get('news', [])
        
        news_text = "\n".join([
            f"{i+1}. {n.get('title', '')}"
            for i, n in enumerate(news_list[:20])
        ])
        
        prompt = self.prompt_template.format(news_list=news_text)
        
        response = self.llm.invoke(prompt)
        
        import json
        try:
            content = response.content
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end != 0:
                result = json.loads(content[start:end])
            else:
                result = []
        except json.JSONDecodeError:
            result = []
        
        return {"analysis": result}
