"""首轮分析只有一个触发者：启动引导（`app/bootstrap.py` 第 8 步）。

回归背景（2026-10-03 真实冷启动验收抓到）：`app/main.py` 里还留着一个旧版
`warmup_cache()` —— 启动 5 秒后直接给看涨 / 看跌 / 机构 / 投资建议四个分析
服务发后台任务。它跑在数据回填之前：抢跑的分析可能在空数据上产出结果并写入
门控指纹，把引导阶段的分析错误地跳过；其中对投资建议的调用还带着必填参数
缺失的真实报错（`_trigger_background_analysis() missing 4 required positional
arguments`），每次启动都在日志里留下一条 ERROR。2.0.2 删除它，首轮分析统一由
引导第 8 步触发：数据就绪后跑、受输入指纹门控与每日预算约束。

变异验证（commit body 有记录）：把 `warmup_cache` 或它的 `asyncio.create_task`
调用加回 `app/main.py`，本测试必红。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import bootstrap


def _main_source() -> str:
    import app.main as main

    return Path(main.__file__).read_text(encoding="utf-8")


@pytest.mark.unit
def test_main_does_not_prewarm_analyses_before_bootstrap():
    source = _main_source()

    assert "def warmup_cache" not in source, (
        "启动预热又回来了：它会抢在数据回填之前触发分析并写入门控指纹，"
        "首轮分析应交由引导的 analyses 阶段。"
    )
    assert "create_task" not in source, "main.py 不应再起任何分析用的后台任务"


@pytest.mark.unit
def test_bootstrap_owns_the_first_analysis_round():
    keys = [key for key, _, _ in bootstrap.STEPS]

    assert "analyses" in keys, "引导必须保留首轮分析阶段"
    assert keys[-1] == "analyses", "首轮分析必须是引导的最后一步：数据就绪之后"
    assert "bootstrap.start_background" in _main_source(), (
        "lifespan 必须通过 bootstrap.start_background 启动引导"
    )
