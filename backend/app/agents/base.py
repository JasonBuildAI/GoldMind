"""LangChain Agent 基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from app.config import settings


class BaseAgent(ABC):
    def __init__(self):
        self.llm = self._create_llm()
    
    def _create_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            model="deepseek-chat",
            openai_api_key=settings.DEEPSEEK_API_KEY,
            openai_api_base=settings.DEEPSEEK_BASE_URL,
            temperature=0.7,
            max_tokens=4096
        )
    
    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
