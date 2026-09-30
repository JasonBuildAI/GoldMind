"""Agent 基类。

注意：本包（app/agents/）当前没有被任何 router 或 service 实例化，
属于历史遗留代码。保留是为了不打断既有引用；如需清理请单独提交。
LLM 一律经 app/services/llm_provider.py 构造，不要在此直接实例化客户端。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from app.services.llm_provider import get_chat_llm


class BaseAgent(ABC):
    def __init__(self):
        self.llm = self._create_llm()

    def _create_llm(self):
        """构造 LLM（供应商由 llm_provider 工厂统一决定）。"""
        return get_chat_llm(temperature=0.7, max_tokens=4096)

    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
