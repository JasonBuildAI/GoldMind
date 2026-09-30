"""缓存时长必须与调度器的刷新间隔对齐。

为什么：分析结果的缓存过期时，**一个用户请求会触发一次按需的付费 LLM 分析**
（见各服务的 `get_xxx(use_cache=True)`）。而调度器本来就会按
`UPDATE_AI_ANALYSIS_CRON` 刷新同一份结果。

所以：

    TTL >= 刷新间隔    ->  缓存过期时调度器几乎已经写好了新结果，不会多花钱
    TTL <  刷新间隔    ->  每个周期都白白多触发一次付费分析

原实现里机构预测的 TTL 是 **3600（1 小时）**，而调度器每 **2 小时**才刷新一次 ——
每两个小时的周期里，第 1 小时结束时就会有一次用户请求触发额外分析。
注释还写着「实时数据更频繁更新」，但刷新节奏根本不是 1 小时。
"""
from app.config import settings

import pytest

from app.services.cache_manager import AI_ANALYSIS_CACHE_TTL, REALTIME_PRICE_CACHE_TTL


def _cron_hours(expr: str) -> list[int]:
    """取出 cron 的小时字段，展开成具体小时列表。"""
    fields = expr.split()
    assert len(fields) >= 2, f"cron 表达式不像 5/6 段式：{expr!r}"
    hour_field = fields[1]
    hours: list[int] = []
    for part in hour_field.split(","):
        if part == "*":
            return list(range(24))
        if "/" in part:
            base, step = part.split("/")
            start = 0 if base == "*" else int(base)
            hours.extend(range(start, 24, int(step)))
        elif "-" in part:
            lo, hi = part.split("-")
            hours.extend(range(int(lo), int(hi) + 1))
        else:
            hours.append(int(part))
    return sorted(set(hours))


def _max_gap_hours(hours: list[int]) -> int:
    """相邻两次触发之间的最大间隔（小时），按一天循环。"""
    assert hours, "小时字段解析为空"
    if len(hours) == 1:
        return 24
    gaps = [b - a for a, b in zip(hours, hours[1:])]
    gaps.append(24 - hours[-1] + hours[0])  # 跨零点
    return max(gaps)


@pytest.mark.unit
def test_cron_hour_parser_handles_the_real_expression():
    """先确认解析器对项目里真实的 cron 表达式是对的。

    （本会话吃过亏：夹具和被测代码用同一个错误假设，测试永远绿。
    所以解析器本身也要有判别力测试。）
    """
    assert _cron_hours("0 0,2,4,6,8,10,12,14,16,18,20,22 * * *") == list(range(0, 24, 2))
    assert _max_gap_hours(list(range(0, 24, 2))) == 2

    assert _cron_hours("30 6 * * *") == [6]
    assert _max_gap_hours([6]) == 24

    assert _cron_hours("0 */4 * * *") == [0, 4, 8, 12, 16, 20]
    assert _max_gap_hours([0, 4, 8, 12, 16, 20]) == 4


@pytest.mark.unit
def test_analysis_ttl_covers_the_refresh_interval():
    """分析缓存不能比刷新间隔短。"""
    interval_hours = _max_gap_hours(_cron_hours(settings.UPDATE_AI_ANALYSIS_CRON))
    interval_seconds = interval_hours * 3600

    assert AI_ANALYSIS_CACHE_TTL >= interval_seconds, (
        f"分析缓存 TTL 是 {AI_ANALYSIS_CACHE_TTL}s，而调度器每 "
        f"{interval_hours}h 才刷新一次 —— 缓存一过期就会有用户请求触发"
        f"一次额外的付费分析。TTL 至少要 {interval_seconds}s。"
    )


@pytest.mark.unit
def test_realtime_ttl_is_much_shorter_than_analysis_ttl():
    """行情缓存和分析缓存是两种节奏，不该混用同一个值。"""
    assert REALTIME_PRICE_CACHE_TTL < AI_ANALYSIS_CACHE_TTL
    # 行情要「实时」，不该缓存超过几分钟
    assert REALTIME_PRICE_CACHE_TTL <= 300


@pytest.mark.unit
def test_every_analysis_service_uses_the_shared_ttl():
    """五个分析服务必须用同一个常量，不许再各写各的数字。

    这条正是问题的来源：机构预测曾经单独写了 3600，与其他四个的 7200 不一致。
    """
    import re
    from pathlib import Path

    services = Path(__file__).resolve().parents[2] / "app" / "services"
    offenders = []
    for path in services.glob("*_service.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"ttl=(\d+)", text):
            offenders.append(f"{path.name}: ttl={match.group(1)}")
        for match in re.finditer(r"_cache_ttl\s*=\s*(\d+)", text):
            offenders.append(f"{path.name}: _cache_ttl={match.group(1)}")

    assert not offenders, (
        "这些地方把 TTL 写成了裸数字，应改用 AI_ANALYSIS_CACHE_TTL：\n  "
        + "\n  ".join(offenders)
    )
