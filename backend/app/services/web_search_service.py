"""联网搜索服务 —— 小米 MiMo。

## 为什么重写

迁移前这里是 `zhipu_service.py`，有两个硬伤：

1. **构造即崩溃**：`get_zhipu_service()` 在 `__init__` 里直接构造
   `OpenAI(api_key=settings.ZHIPU_API_KEY)`。缺少智谱密钥时 openai SDK 会
   抛 `OpenAIError: Missing credentials`，而它是在各分析服务 `__init__` 里被调用的，
   于是 `/bullish-factors-ai`、`/bearish-factors-ai`、
   `/institution-predictions-ai`、`/investment-advice-ai`、`/market-summary-ai`
   **全部 500**。
2. **失败即编造**：搜索失败时把 `"搜索失败: {异常}"` 当成正常分析结果往上传，
   上层无法区分「真的搜到了」和「其实什么都没搜到」。

## 本实现的三条约束

1. 构造绝不抛异常；密钥缺失只是「不可用」，不是「崩溃」。
2. 搜索失败时返回 `available=False` 并带上原因，**绝不编造内容**。
3. 调用方在 `available=False` 时应回退到数据库 / RSS 新闻。

## 已知限制（实测）

Token Plan 的 `tp-` key 调用 MiMo 的 `web_search` 工具会返回
HTTP 400 `Param Incorrect`（已用 scripts/smoke_mimo.py 二分排除参数写法问题）。
也就是说当前凭证大概率拿不到联网搜索，此时本服务会明确报告不可用。
"""
from __future__ import annotations

import json

from typing import Any, Dict, Optional

from app.utils import timeutil
from app.config import settings
from app.services import llm_provider

__all__ = ["WebSearchService", "get_web_search_service", "extract_json_object"]

def extract_json_object(content: str) -> Optional[Dict[str, Any]]:
    """从模型输出里取出 JSON 对象。

    容忍 markdown 代码块与前后多余文字 —— 与迁移前各服务里重复的
    「先直接 parse、失败再抠花括号」策略保持一致，但只此一份。
    """
    if not content:
        return None

    text = content.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]

    try:
        parsed = json.loads(text.strip())
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start, end = content.find("{"), content.rfind("}") + 1
    if start != -1 and end > start:
        try:
            parsed = json.loads(content[start:end])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None

class WebSearchService:
    """基于 MiMo `web_search` 工具的联网搜索服务。"""

    def __init__(self) -> None:
        # 刻意不构造任何客户端：密钥缺失时构造 openai 客户端会抛异常，
        # 而本类是在各分析服务的 __init__ 里被创建的。
        self.model = settings.MIMO_SEARCH_MODEL

    @property
    def is_available(self) -> bool:
        """是否具备发起搜索的前提条件（已配置密钥）。"""
        return llm_provider.is_configured()

    # ------------------------------------------------------------------ #
    # 底层调用
    # ------------------------------------------------------------------ #
    def _chat_with_search(self, prompt: str, max_tokens: int = 4096) -> tuple[bool, str, str]:
        """执行一次带联网搜索的对话。

        Returns:
            (是否成功, 正文, 失败原因)
        """
        if not self.is_available:
            return False, "", "未配置 MIMO_API_KEY"

        try:
            client = llm_provider.get_search_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                tools=[llm_provider.build_web_search_tool()],
                temperature=0.3,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            if not content.strip():
                return False, "", "搜索返回空内容"
            return True, content, ""
        except Exception as exc:  # 网络、鉴权、插件未开通、参数不合法等
            return False, "", f"{type(exc).__name__}: {exc}"

    # ------------------------------------------------------------------ #
    # 对外接口
    # ------------------------------------------------------------------ #
    def search_json(self, prompt: str, max_tokens: int = 4096) -> Dict[str, Any]:
        """执行联网搜索并把结果解析为 JSON。

        失败时返回 ``{"available": False, "reason": ...}``，
        **不会**把错误文本伪装成分析结果。
        """
        ok, content, reason = self._chat_with_search(prompt, max_tokens=max_tokens)
        if not ok:
            return {
                "available": False,
                "reason": reason,
                "search_time": timeutil.today_str(),
            }

        parsed = extract_json_object(content)
        if parsed is None:
            return {
                "available": False,
                "reason": "搜索结果无法解析为 JSON",
                "raw_content": content,
                "search_time": timeutil.today_str(),
            }

        parsed["available"] = True
        parsed.setdefault("search_time", timeutil.today_str())
        return parsed

    def search_institution_predictions(self) -> Dict[str, Any]:
        """搜索四大机构对黄金的最新预测。

        返回结构：``institutions`` / ``analysis_summary`` / ``available`` / ``reason``。
        调用方必须检查 ``available``，不能只看 ``institutions`` 是否为空。
        """
        prompt = """请搜索并整理以下四家主流机构对黄金价格的最新预测：
1. 高盛 (Goldman Sachs)
2. 瑞银 (UBS)
3. 摩根士丹利 (Morgan Stanley)
4. 花旗 (Citi)

对于每家机构提供：
- 目标价格（美元）
- 时间框架（如2026年底、2026年中、2026年Q3等）
- 评级（看涨/看跌/中性）
- 核心理由（一句话总结）
- 关键要点（4个支撑论据）

请严格按照以下JSON格式返回：

{
    "institutions": [
        {
            "name": "机构全名",
            "logo": "机构缩写",
            "rating": "bullish 或 bearish 或 neutral",
            "target_price": 目标价（美元，数字）,
            "timeframe": "时间框架",
            "reasoning": "核心理由（一句话）",
            "key_points": ["要点1", "要点2", "要点3", "要点4"]
        }
    ],
    "analysis_summary": "机构预测汇总（一句话）"
}

注意：
1. 必须返回有效的JSON格式
2. target_price必须是数字
3. rating只能是：bullish, bearish, neutral
4. 确保四家机构都有数据
5. 只报告搜索到的真实内容；若某家机构没有最新预测，请标注"暂无最新预测"，不要凭印象编造目标价
"""
        result = self.search_json(prompt)
        if not result.get("available"):
            return {
                "institutions": [],
                "analysis_summary": f"联网搜索不可用：{result.get('reason', '未知原因')}",
                "available": False,
                "reason": result.get("reason"),
                "search_time": result.get("search_time"),
            }
        result.setdefault("institutions", [])
        return result

# 单例（构造无副作用，可以安全缓存）
_web_search_service: Optional[WebSearchService] = None

def get_web_search_service() -> WebSearchService:
    """获取联网搜索服务实例。"""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service
